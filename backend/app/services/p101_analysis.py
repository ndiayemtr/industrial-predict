"""Opt-in, non-persisting application adapter. No provider or SQL runtime installed.

The trusted deployment must supply live session verification, a destination-
verified connection context and a provenance verifier bound to the exact request.
Typed declarations alone are not evidence. This adapter never creates an engine.
"""

from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app import p101_dev_loader as reader
from app.core.authorization import AuthorizationEffect, Permission, decide_authorization
from app.core.caller_session import CurrentCaller, CallerForbidden, CallerUnauthenticated
from app.p101_dev.contracts import Computed, Abstained, DeclaredProvenance
from app.schemas.p101_analysis import ComputedAnalysis, AbstainedAnalysis, RejectedAnalysis
from app.services.p101_dev_orchestration import P101DevOrchestrator, OrchestrationError
from app.services.p101_operator_diagnostic import (
    _native_idle, _native_connection, LOCK_TIMEOUT_MS, STATEMENT_TIMEOUT_MS,
)


class AnalysisUnavailable(ValueError):
    def __init__(self):
        super().__init__('P101_ANALYSIS_UNAVAILABLE')


def _closed(*args, **kwargs):
    raise AnalysisUnavailable()


class P101AnalysisService:
    def __init__(self, *, caller_provider, connection_context, provenance_verifier,
                 clock=lambda: datetime.now(timezone.utc)):
        if not all(callable(method) for method in (
            getattr(caller_provider, 'current_caller', None), connection_context,
            provenance_verifier, clock,
        )):
            raise AnalysisUnavailable()
        self.provider = caller_provider
        self.connection_context = connection_context
        self.provenance_verifier = provenance_verifier
        self.clock = clock

    def _caller(self, reference, company_id, now):
        caller = self.provider.current_caller(reference=reference, now=now)
        if type(caller) is not CurrentCaller:
            raise CallerUnauthenticated()
        caller.__post_init__()
        if caller.session_reference != reference or caller.refreshed_at != now:
            raise CallerUnauthenticated()
        decision = decide_authorization(identity=caller.identity, memberships=caller.memberships,
                                        company_id=company_id, permission=Permission.PREDICTIONS_ANALYZE)
        if decision.effect is not AuthorizationEffect.ALLOW:
            raise CallerForbidden()
        return caller

    @contextmanager
    def _read(self):
        # Context must use the installed, destination-verified runtime. No DSN here.
        with self.connection_context() as connection:
            if (not isinstance(connection, Connection) or connection.closed or connection.invalidated
                    or connection.in_transaction() or connection.in_nested_transaction()):
                raise AnalysisUnavailable()
            native = _native_idle(connection)
            connection = connection.execution_options(isolation_level='REPEATABLE READ')
            if _native_idle(connection) is not native:
                raise AnalysisUnavailable()
            tx = connection.begin()
            try:
                connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                connection.execute(text("SELECT set_config('statement_timeout', :v, true)"), {'v': f'{STATEMENT_TIMEOUT_MS}ms'})
                connection.execute(text("SELECT set_config('lock_timeout', :v, true)"), {'v': f'{LOCK_TIMEOUT_MS}ms'})
                proof = connection.execute(text("SELECT current_setting('transaction_isolation') AS isolation, "
                    "current_setting('transaction_read_only') AS read_only, "
                    "(SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_timeout_ms, "
                    "(SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_timeout_ms")).mappings().one()
                if dict(proof) != dict(isolation='repeatable read', read_only='on',
                                      statement_timeout_ms=STATEMENT_TIMEOUT_MS, lock_timeout_ms=LOCK_TIMEOUT_MS):
                    raise AnalysisUnavailable()
                if _native_connection(connection) is not native:
                    raise AnalysisUnavailable()
                with Session(bind=connection, autoflush=False, join_transaction_mode='rollback_only') as session:
                    with session.begin():
                        yield session
                        if _native_connection(connection) is not native:
                            raise AnalysisUnavailable()
            finally:
                if tx.is_active:
                    tx.rollback()

    def analyze(self, *, reference, equipment_id, request):
        now = self.clock()
        # Check authentication and authorization before acquiring a SQL resource.
        self._caller(reference, request.company_id, now)
        provenance = None
        scope_denied = False
        authority_failure = None

        def refreshed_caller(session, *, reference, now):
            nonlocal authority_failure
            try:
                return self._caller(reference, request.company_id, now)
            except (CallerUnauthenticated, CallerForbidden) as error:
                authority_failure = type(error)
                raise

        def scoped_loader(session, **arguments):
            nonlocal provenance, scope_denied
            connection = reader._transaction(session)[0]
            chains = connection.execute(reader.CHAIN_SQL.where(reader.n.c.id == request.sensor_id).limit(2)).mappings().all()
            if len(chains) != 1 or any(chains[0][key] != value for key, value in (
                ('company_id', request.company_id), ('site_company_id', request.company_id),
                ('site_id', request.site_id), ('equipment_site_id', request.site_id),
                ('equipment_id', equipment_id), ('sensor_equipment_id', equipment_id),
                ('sensor_id', request.sensor_id),
            )):
                scope_denied = True
                raise CallerForbidden()
            # Mandatory trusted server verifier, never a request DTO/boolean.
            provenance = self.provenance_verifier(session=session, equipment_id=equipment_id,
                request=request, now=now)
            if (type(provenance) is not DeclaredProvenance or provenance.synthetic is not False
                    or not provenance.evidence):
                raise AnalysisUnavailable()
            return reader.load_snapshot(session, **(arguments | {'provenance': provenance}))

        port = SimpleNamespace(read=self._read,
            current_caller=refreshed_caller,
            write=_closed, lock_and_reload=_closed, reserve_and_stage=_closed, finish=_closed)
        orchestrator = P101DevOrchestrator(port=port, clock=lambda: now, loader=scoped_loader)
        try:
            outcome = orchestrator.analyze(reference=reference, company_id=request.company_id,
                equipment_id=equipment_id, sensor_id=request.sensor_id,
                target_measurement_id=request.target_measurement_id, event_cutoff=request.cutoff_utc,
                provenance=None)  # Replaced by server-verified provenance before loader call.
        except OrchestrationError:
            if authority_failure is not None:
                raise authority_failure() from None
            if scope_denied:
                raise CallerForbidden() from None
            raise AnalysisUnavailable() from None
        result = outcome.result
        base = dict(equipment_id=equipment_id, target_measurement_id=request.target_measurement_id,
                    provenance_source=provenance.source_id)
        if type(result) is Computed:
            return ComputedAnalysis(**base, score=result.score, is_alert=result.is_alert,
                                    reference_ids=list(result.reference_ids), statistics=asdict(result.statistics))
        if type(result) is Abstained:
            return AbstainedAnalysis(**base, reason=result.code.value, reference_count=result.reference_count)
        return RejectedAnalysis(**base, reason=result.code.value, field=result.field)
