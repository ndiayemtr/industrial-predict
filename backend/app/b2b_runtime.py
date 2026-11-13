"""Explicit runtime binding to existing OIDC/session/authorization components.

No config discovery, engine creation, account creation or default grants.
"""

from contextlib import contextmanager, asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
import logging
import httpx

from sqlalchemy import event, select, text

from app.application_session_store import PostgresApplicationSessionStore, SessionStoreRejected, SessionStoreUnavailable
from app.core.authorization import AccountState, Permission, AuthorizationEffect, decide_authorization
from app.core.caller_session import (
    CallerUnauthenticated, CallerForbidden, CallerProviderUnavailable, Reason,
    IdentityEvidence, IdentityAssurance, admit_caller,
)
from app.core.database_runtime import SqlRuntime
from app.core.identity import LocalIdentityLink
from app.core.oidc_client import GoogleOidcClient, OidcClientRejected, OidcClientUnavailable
from app.models.professional_account import ExternalIdentityRecord, LocalUserRecord
from app.models.equipment import Equipment
from app.models.site import Site
from app.models.sensor import Sensor


class SqlIdentityLookup:
    def __init__(self, runtime):
        self.runtime = runtime

    def find_by_external_identity(self, *, issuer, subject):
        with self.runtime.session() as db:
            db.execute(text('SET LOCAL search_path = public'))
            rows = db.execute(select(ExternalIdentityRecord.issuer, ExternalIdentityRecord.subject,
                ExternalIdentityRecord.user_id, LocalUserRecord.state).join(LocalUserRecord,
                ExternalIdentityRecord.user_id == LocalUserRecord.id).where(
                ExternalIdentityRecord.issuer == issuer, ExternalIdentityRecord.subject == subject)).all()
            return tuple(LocalIdentityLink(row.issuer, row.subject, row.user_id, AccountState(row.state)) for row in rows)


class GoogleSessionLogin:
    """Backend callback completion, not a token-decoding or browser DTO shortcut.

    The existing client consumes durable state/browser binding before exchange.
    Session secrets are returned only by the store after confirmed commit.
    HTTPS callback/cookie delivery must be bound by the approved deployment.
    """
    def __init__(self, *, client, runtime, clock=lambda: datetime.now(timezone.utc)):
        if type(client) is not GoogleOidcClient or type(runtime) is not SqlRuntime or not callable(clock):
            raise CallerProviderUnavailable()
        self.client, self.runtime, self.clock = client, runtime, clock

    def begin(self, *, return_target):
        start = self.client._transactions.create(return_target=return_target)
        return start, self.client.authorization_url(start)

    def complete_callback(self, *, state, browser_binding, code, client_secret):
        try:
            result = self.client.complete_callback(state=state, browser_binding=browser_binding,
                                                  code=code, client_secret=client_secret)
        except OidcClientUnavailable:
            raise CallerProviderUnavailable() from None
        except OidcClientRejected:
            raise CallerUnauthenticated() from None
        if not result.professional_email_verified:
            raise CallerForbidden()
        evidence = IdentityEvidence(result.external_identity, IdentityAssurance.PROFESSIONAL_VERIFIED)
        identity_provider = SimpleNamespace(verified_identity=lambda: evidence)
        lookup = SqlIdentityLookup(self.runtime)
        admission = SimpleNamespace(admit=lambda: admit_caller(provider=identity_provider, lookup=lookup))
        store = PostgresApplicationSessionStore(self.runtime, admission_provider=admission, clock=self.clock)
        try:
            return store.create()
        except SessionStoreRejected:
            raise CallerForbidden() from None


class B2BRouteRuntime:
    def __init__(self, *, sql, sessions, clock=lambda: datetime.now(timezone.utc), provenance_verifier=None):
        if (type(sql) is not SqlRuntime or type(sessions) is not PostgresApplicationSessionStore
                or sessions._runtime is not sql or not callable(clock)
                or sql.engine.echo or not sql.engine.hide_parameters
                or sql.engine.logger.isEnabledFor(logging.DEBUG)):
            raise CallerProviderUnavailable()
        self.sql, self.sessions, self.clock = sql, sessions, clock
        self.analysis = None
        if provenance_verifier is not None:
            from app.services.p101_analysis import P101AnalysisService
            self.analysis = P101AnalysisService(caller_provider=self,
                connection_context=sql.engine.connect, provenance_verifier=provenance_verifier, clock=clock)

    def _caller(self, db, reference, now):
        try:
            return self.sessions.current_caller_in_transaction(db, reference=reference, now=now)
        except SessionStoreRejected as error:
            if error.reason is Reason.ACCOUNT_INACTIVE:
                raise CallerForbidden() from None
            raise CallerUnauthenticated() from None
        except Exception:
            raise CallerProviderUnavailable() from None

    @staticmethod
    def _allowed(caller, company, permissions):
        return all(decide_authorization(identity=caller.identity, memberships=caller.memberships,
            company_id=company, permission=permission).effect is AuthorizationEffect.ALLOW for permission in permissions)

    def _configure(self, db):
        if (self.sql.engine.echo or not self.sql.engine.hide_parameters
                or self.sql.engine.logger.isEnabledFor(logging.DEBUG)
                or db.autoflush or db.new or db.dirty or db.deleted or db.in_transaction()):
            raise CallerProviderUnavailable()
        db.connection(execution_options={'isolation_level': 'READ COMMITTED'})
        db.execute(text("SET LOCAL statement_timeout = '15s'"))
        db.execute(text("SET LOCAL lock_timeout = '5s'"))
        db.execute(text('SET LOCAL search_path = public'))

    def current_caller(self, *, reference, now):
        with self.sql.session() as db:
            self._configure(db)
            return self._caller(db, reference, now)

    @contextmanager
    def authorized_equipment(self, *, reference, equipment_id, permissions, write=False):
        with self.sql.session() as db:
            self._configure(db)
            caller = self._caller(db, reference, self.clock())
            companies = [member.company_id for member in caller.memberships
                         if self._allowed(caller, member.company_id, permissions)]
            if not companies:
                raise CallerForbidden()
            # Resource metadata is read only WITHIN already authorized companies.
            scope = db.execute(select(Equipment.id, Equipment.site_id, Site.company_id)
                .join(Site, Equipment.site_id == Site.id).where(Equipment.id == equipment_id,
                    Site.company_id.in_(companies)).with_for_update(read=True, of=(Equipment, Site))).one_or_none()
            if scope is None or scope.id != equipment_id or scope.company_id not in companies:
                raise CallerForbidden()
            def before_commit(session):
                if not write:
                    raise CallerForbidden()
                refreshed = self._caller(session, reference, self.clock())
                if (refreshed.identity != caller.identity
                        or not self._allowed(refreshed, scope.company_id, permissions)):
                    raise CallerForbidden()
            event.listen(db, 'before_commit', before_commit)
            try:
                yield db, scope
            finally:
                event.remove(db, 'before_commit', before_commit)

    def analyze(self, *, reference, equipment_id, request):
        if self.analysis is not None:
            return self.analysis.analyze(reference=reference, equipment_id=equipment_id, request=request)
        # Identity alone never supplies physical-data provenance.
        with self.authorized_equipment(reference=reference, equipment_id=equipment_id,
                                       permissions=(Permission.PREDICTIONS_ANALYZE,)) as (db, scope):
            if scope.company_id != request.company_id or scope.site_id != request.site_id:
                raise CallerForbidden()
            sensor = db.execute(select(Sensor.id).where(Sensor.id == request.sensor_id,
                Sensor.equipment_id == equipment_id)).scalar_one_or_none()
            if sensor is None:
                raise CallerForbidden()
            raise CallerProviderUnavailable()  # No provenance verifier installed.


def install_b2b_runtime(app, *, runtime):
    """Explicit deployment step, only against the already installed SQL runtime."""
    if type(runtime) is not B2BRouteRuntime or getattr(app.state, 'sql_runtime', None) is not runtime.sql:
        raise CallerProviderUnavailable()
    app.state.b2b_runtime = runtime


def create_route_runtime(*, sql, clock=lambda: datetime.now(timezone.utc), provenance_verifier=None):
    """Validation-only store: issuance remains exclusively in GoogleSessionLogin."""
    def no_admission():
        raise SessionStoreUnavailable()
    sessions = PostgresApplicationSessionStore(sql, admission_provider=SimpleNamespace(admit=no_admission), clock=clock)
    return B2BRouteRuntime(sql=sql, sessions=sessions, clock=clock, provenance_verifier=provenance_verifier)


def install_google_b2b(app, *, sql, config, approved_domains, client_secret_loader,
                       clock=lambda: datetime.now(timezone.utc)):
    """Pre-serve assembly using the SAME approved SQL runtime; no SQL/network I/O.

    Call only after schema, role and destination qualification. No discovery,
    migration, account/grant creation or provenance verifier is supplied here.
    """
    from app.oidc_transaction_store import PostgresTransactionStore
    from app.api.routes.b2b_login import create_google_login_router
    if (getattr(app.state, 'sql_runtime', None) is not sql
            or getattr(app.state, 'b2b_runtime', None) is not None):
        raise CallerProviderUnavailable()
    # Concrete deployment transport: authenticated TLS, no environment proxies or retries.
    transport = httpx.HTTPTransport(verify=True, retries=0, trust_env=False)
    try:
        client = GoogleOidcClient(config=config, approved_domains=approved_domains, transport=transport,
            clock=clock, store=PostgresTransactionStore(sql), allowed_return_targets=('predictions',))
        login = GoogleSessionLogin(client=client, runtime=sql, clock=clock)
        router = create_google_login_router(login=login, client_secret_loader=client_secret_loader)
        runtime = create_route_runtime(sql=sql, clock=clock)
    except Exception:
        transport.close()
        raise
    install_b2b_runtime(app, runtime=runtime)
    app.include_router(router)
    previous_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        try:
            async with previous_lifespan(application) as state:
                yield state
        finally:
            transport.close()
    app.router.lifespan_context = lifespan
    return runtime
