"""Explicit opt-in PostgreSQL B2B store; no cookies, routes or runtime creation.

The admission provider and injected runtime are SERVER trust boundaries, never
request-selected dependencies. Typed admission is not cryptographic proof.
No permissions are stored or granted. current_caller_in_transaction reloads
memberships under the caller transaction; ordinary read returns only SessionRecord.

All operations lock the local user before the session. Administrative suspension
and identity reassignment must follow the same user-lock ordering. External links
are also locked FOR SHARE while checked. No retry or default runtime is installed.
Clock samples are taken after lock acquisition; both caller and database times
must accept a live session. Expiry during commit remains possible, as for OIDC.
"""

import base64
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import Protocol

from sqlalchemy import func, insert, select, text, update

from app.core.authorization import (AccountState, VerifiedIdentity, CompanyMembership,
                                    MembershipState, Role, Permission)
from app.core.caller_session import (
    AdmissionDecision, Outcome, Reason, SessionPolicy, SessionRecord, SessionReference,
    evaluate_session, record_activity, revoke_session, rotate_session,
    CurrentCaller,
)
from app.core.database_runtime import SqlRuntime
from app.models.application_session import ApplicationSessionRecord, CONTRACT_VERSION
from app.models.professional_account import ExternalIdentityRecord, LocalUserRecord
from app.models.professional_account import MembershipRecord, MembershipPermissionRecord


_TABLE = ApplicationSessionRecord.__table__


class SessionStoreUnavailable(RuntimeError):
    def __init__(self):
        super().__init__("SESSION_STORE_UNAVAILABLE")


class SessionStoreCommitUncertain(RuntimeError):
    def __init__(self):
        super().__init__("SESSION_STORE_COMMIT_UNCERTAIN")


class SessionStoreIncoherent(RuntimeError):
    def __init__(self):
        super().__init__("SESSION_STORE_INCOHERENT")


class SessionStoreRejected(ValueError):
    def __init__(self, reason=Reason.INVALID_STATE):
        self.reason = reason if type(reason) is Reason else Reason.INVALID_STATE
        super().__init__("SESSION_STORE_REJECTED")


class SessionAdmissionProvider(Protocol):
    def admit(self) -> AdmissionDecision:
        """Run approved verification/local admission; never accept a client DTO."""
        ...


@dataclass(frozen=True, slots=True, repr=False)
class IssuedSession:
    """Transient delivery after commit only; do not log, serialize or persist it.

    The caller owns delivery and memory lifetime. No secure memory erasure is
    promised. Losing delivery after commit leaves a session, never an auto-retry.
    """

    secret: str
    csrf_token: str
    record: SessionRecord


def _require(condition):
    if not condition:
        raise SessionStoreIncoherent()


def _token(value):
    if type(value) is not str or len(value) != 43:
        raise SessionStoreRejected()
    valid = False
    try:
        raw = base64.b64decode(value + "=", altchars=b"-_", validate=True)
        valid = len(raw) == 32 and base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii") == value
    except (ValueError, UnicodeError):
        pass
    if not valid:
        raise SessionStoreRejected()
    return value


def _digest(label, value):
    return hashlib.sha256((label + "\0" + _token(value)).encode("ascii")).hexdigest()


def session_reference(secret: str) -> SessionReference:
    """Hash a canonical 32-byte bearer secret; possession is not authorization."""
    return SessionReference(_digest("b2b-session-v1", secret))


def csrf_fingerprint(token: str) -> str:
    return _digest("b2b-csrf-v1", token)


def _generate():
    first, second = secrets.token_bytes(32), secrets.token_bytes(32)
    _require(type(first) is bytes and type(second) is bytes and len(first) == len(second) == 32 and first != second)
    encode = lambda value: base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")
    return encode(first), encode(second)


def _utc(value):
    _require(type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None)
    return value.astimezone(timezone.utc)


class PostgresApplicationSessionStore:
    def __init__(self, runtime: SqlRuntime, *, admission_provider: SessionAdmissionProvider,
                 clock: Callable[[], datetime], policy: SessionPolicy = SessionPolicy(),
                 require_user_session_administration=None):
        _require(type(runtime) is SqlRuntime and callable(clock)
                 and callable(getattr(admission_provider, "admit", None)))
        _require(type(policy) is SessionPolicy)
        policy.__post_init__()
        # Store whole seconds; never silently truncate a custom policy.
        _require(all(t.microseconds == 0 for t in (policy.idle_timeout, policy.absolute_timeout)))
        _require(policy.absolute_timeout.total_seconds() <= 2147483647)
        _require(require_user_session_administration is None or callable(require_user_session_administration))
        self._runtime, self._admission, self._clock, self._policy = runtime, admission_provider, clock, policy
        self._authorize_user = require_user_session_administration

    def _run(self, operation):
        result, committed, failure, reason = None, False, SessionStoreUnavailable, None
        try:
            engine = self._runtime.engine
            if engine.echo or not engine.hide_parameters or engine.logger.isEnabledFor(logging.DEBUG):
                raise SessionStoreUnavailable()
            with self._runtime.session() as db:
                phase = "work"
                try:
                    db.connection(execution_options={"isolation_level": "READ COMMITTED"})
                    db.execute(text("SET LOCAL lock_timeout = '5s'"))
                    db.execute(text("SET LOCAL statement_timeout = '15s'"))
                    result = operation(db)
                    phase = "commit"
                    db.commit()
                    committed = True
                except Exception as error:
                    if phase == "commit":
                        failure = SessionStoreCommitUncertain
                    elif type(error) in (SessionStoreRejected, SessionStoreIncoherent):
                        failure = type(error)
                        reason = getattr(error, "reason", None)
                    try:
                        db.rollback()
                    except Exception:
                        pass
        except Exception:
            pass
        if committed:
            return result
        # Outside exception handlers: no driver cause, SQL values or issued secrets.
        if failure is SessionStoreRejected:
            raise SessionStoreRejected(reason)
        raise failure()

    def _times(self, db):
        caller = self._clock()
        _require(type(caller) is datetime and caller.tzinfo is not None and caller.utcoffset() == timedelta(0))
        server = _utc(db.execute(select(func.clock_timestamp())).scalar_one())
        return caller, server

    def _lock_user(self, db, user_id, *, require_active=True):
        state = db.execute(select(LocalUserRecord.state).where(
            LocalUserRecord.id == user_id).with_for_update()).scalar_one_or_none()
        if state not in (AccountState.ACTIVE.value, AccountState.SUSPENDED.value):
            raise SessionStoreIncoherent()
        if require_active and state != AccountState.ACTIVE.value:
            raise SessionStoreRejected(Reason.ACCOUNT_INACTIVE)
        return AccountState(state)

    def _external(self, db, *, user_id, external_id=None, identity=None):
        query = select(ExternalIdentityRecord.id, ExternalIdentityRecord.issuer, ExternalIdentityRecord.subject).where(
            ExternalIdentityRecord.user_id == user_id)
        if external_id is not None:
            query = query.where(ExternalIdentityRecord.id == external_id)
        else:
            query = query.where(ExternalIdentityRecord.issuer == identity.issuer,
                                ExternalIdentityRecord.subject == identity.subject)
        row = db.execute(query.with_for_update(read=True)).mappings().one_or_none()
        if row is None:
            raise SessionStoreIncoherent()
        _require(type(row["id"]) is int and row["id"] > 0)
        if identity is not None:
            # Do not let a database collation silently normalize the external key.
            _require((row["issuer"], row["subject"]) == (identity.issuer, identity.subject))
        return row

    def _record(self, db, row):
        record = None
        valid = False
        try:
            record = self._decode_record(db, row)
            valid = True
        except SessionStoreUnavailable:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, SessionStoreIncoherent):
            pass
        _require(valid)
        return record

    def _decode_record(self, db, row):
        _require(row["contract_version"] == CONTRACT_VERSION)
        _require(type(row["csrf_digest"]) is str and len(row["csrf_digest"]) == 64
                 and all(c in "0123456789abcdef" for c in row["csrf_digest"]))
        _require(all(type(row[key]) is int for key in ("user_id", "external_identity_id",
                     "idle_timeout_seconds", "absolute_timeout_seconds")))
        external = self._external(db, user_id=row["user_id"], external_id=row["external_identity_id"])
        identity = VerifiedIdentity(row["user_id"], external["issuer"], external["subject"], AccountState.ACTIVE)
        return SessionRecord(
            SessionReference(row["secret_digest"]), identity,
            *(_utc(row[key]) for key in ("authenticated_at", "created_at", "last_activity_at", "absolute_expires_at")),
            policy=SessionPolicy(timedelta(seconds=row["idle_timeout_seconds"]),
                                 timedelta(seconds=row["absolute_timeout_seconds"])),
            revoked_at=None if row["revoked_at"] is None else _utc(row["revoked_at"]),
            replaced_by=None if row["replaced_by"] is None else SessionReference(row["replaced_by"]),
        )

    def _load(self, db, reference):
        _require(type(reference) is SessionReference)
        reference.__post_init__()
        user_id = db.execute(select(_TABLE.c.user_id).where(
            _TABLE.c.secret_digest == reference.digest)).scalar_one_or_none()
        if user_id is None:
            raise SessionStoreRejected(Reason.SESSION_MISMATCH)
        _require(type(user_id) is int and user_id > 0)
        self._lock_user(db, user_id)
        row = db.execute(select(_TABLE).where(_TABLE.c.secret_digest == reference.digest).with_for_update()).mappings().one_or_none()
        _require(row is not None and row["user_id"] == user_id)
        record = self._record(db, row)
        times = self._times(db)  # After all blocking locks, not before.
        for now in times:
            decision = evaluate_session(record, reference=reference, now=now)
            if decision.outcome is Outcome.INCOHERENT:
                raise SessionStoreIncoherent()
            if decision.outcome is not Outcome.READY:
                raise SessionStoreRejected(decision.reason)
        return row, record, max(times)

    def _values(self, record, *, external_id, csrf_digest):
        return dict(secret_digest=record.reference.digest, csrf_digest=csrf_digest,
                    user_id=record.identity.user_id, external_identity_id=external_id,
                    authenticated_at=record.authenticated_at, created_at=record.created_at,
                    last_activity_at=record.last_activity_at, absolute_expires_at=record.absolute_expires_at,
                    idle_timeout_seconds=int(record.policy.idle_timeout.total_seconds()),
                    absolute_timeout_seconds=int(record.policy.absolute_timeout.total_seconds()),
                    revoked_at=record.revoked_at,
                    replaced_by=None if record.replaced_by is None else record.replaced_by.digest,
                    contract_version=CONTRACT_VERSION)

    def create(self) -> IssuedSession:
        def operation(db):
            admission = self._admission.admit()
            _require(type(admission) is AdmissionDecision and type(admission.outcome) is Outcome)
            if admission.outcome is Outcome.UNAVAILABLE:
                raise SessionStoreUnavailable()
            if admission.outcome is Outcome.INCOHERENT:
                raise SessionStoreIncoherent()
            if admission.outcome is not Outcome.READY:
                raise SessionStoreRejected(admission.reason)
            identity = admission.identity
            _require(type(identity) is VerifiedIdentity and type(identity.user_id) is int and identity.user_id > 0
                     and identity.account_state is AccountState.ACTIVE and admission.reason is Reason.VALID)
            self._lock_user(db, identity.user_id)
            external = self._external(db, user_id=identity.user_id, identity=identity)
            now = max(self._times(db))
            secret, csrf = _generate()
            record = SessionRecord(session_reference(secret), identity, now, now, now,
                                   now + self._policy.absolute_timeout, self._policy)
            db.execute(insert(_TABLE).values(**self._values(record, external_id=external["id"], csrf_digest=csrf_fingerprint(csrf))))
            return IssuedSession(secret, csrf, record)
        return self._run(operation)

    def read(self, reference: SessionReference) -> SessionRecord:
        return self._run(lambda db: self._load(db, reference)[1])

    def current_caller_in_transaction(self, db, *, reference: SessionReference, now: datetime) -> CurrentCaller:
        """Read fresh grants under locks retained by the caller's transaction.

        Reuses session/user/link validation and expiry checks, without committing
        or updating activity. Membership/grant mutation must acquire ordinary
        PostgreSQL row locks; FOR SHARE prevents revocation before caller commit.
        `now` is the server request anchor; _load also checks both clocks after locks.
        """
        _, record, _ = self._load(db, reference)
        decision = evaluate_session(record, reference=reference, now=now)
        if decision.outcome is not Outcome.READY:
            raise SessionStoreRejected(decision.reason)
        rows = db.execute(select(MembershipRecord).where(
            MembershipRecord.user_id == record.identity.user_id)
            .order_by(MembershipRecord.id).with_for_update(read=True)).scalars().all()
        memberships = []
        for row in rows:
            grants = db.execute(select(MembershipPermissionRecord.permission, MembershipPermissionRecord.role).where(
                MembershipPermissionRecord.membership_id == row.id)
                .order_by(MembershipPermissionRecord.permission).with_for_update(read=True)).all()
            _require(all(grant.role == row.role for grant in grants))
            permissions = frozenset(Permission(grant.permission) for grant in grants)
            memberships.append(CompanyMembership(record.identity.user_id, row.company_id,
                MembershipState(row.state), Role(row.role),
                permissions if row.state == MembershipState.ACTIVE.value else frozenset()))
        return CurrentCaller(reference, record.identity, tuple(memberships), now)

    def touch(self, reference: SessionReference) -> SessionRecord:
        def operation(db):
            _, record, now = self._load(db, reference)
            touched = record_activity(record, now=now)
            result = db.execute(update(_TABLE).where(_TABLE.c.secret_digest == reference.digest,
                                _TABLE.c.revoked_at.is_(None)).values(last_activity_at=touched.last_activity_at))
            _require(result.rowcount == 1)
            return touched
        return self._run(operation)

    def revoke(self, reference: SessionReference) -> SessionRecord:
        def operation(db):
            _, record, now = self._load(db, reference)
            revoked = revoke_session(record, now=now)
            result = db.execute(update(_TABLE).where(_TABLE.c.secret_digest == reference.digest,
                                _TABLE.c.revoked_at.is_(None)).values(revoked_at=revoked.revoked_at))
            _require(result.rowcount == 1)
            return revoked
        return self._run(operation)

    def rotate(self, reference: SessionReference) -> IssuedSession:
        def operation(db):
            row, record, now = self._load(db, reference)
            secret, csrf = _generate()
            plan = rotate_session(record, replacement=session_reference(secret), now=now)
            db.execute(insert(_TABLE).values(**self._values(plan.replacement,
                       external_id=row["external_identity_id"], csrf_digest=csrf_fingerprint(csrf))))
            result = db.execute(update(_TABLE).where(_TABLE.c.secret_digest == reference.digest,
                                _TABLE.c.revoked_at.is_(None)).values(revoked_at=plan.invalidated.revoked_at,
                                                                     replaced_by=plan.replacement.reference.digest))
            _require(result.rowcount == 1)
            return IssuedSession(secret, csrf, plan.replacement)
        return self._run(operation)

    def sessions_for_user(self, user_id: int) -> tuple[SessionReference, ...]:
        """Trusted administrative enumeration, NOT an authenticated client API.

        Includes expired but unrevoked rows. Caller must have server authority;
        knowing user_id never grants access. Bulk revocation rechecks under lock.
        """
        self._authorize_administration(user_id)
        def operation(db):
            _require(type(user_id) is int and user_id > 0)
            self._lock_user(db, user_id, require_active=False)
            return tuple(SessionReference(value) for value in db.execute(select(_TABLE.c.secret_digest).where(
                _TABLE.c.user_id == user_id, _TABLE.c.revoked_at.is_(None)).order_by(_TABLE.c.secret_digest)).scalars().all())
        return self._run(operation)

    def revoke_for_user(self, user_id: int) -> int:
        """Trusted administrative operation; also works after account suspension."""
        self._authorize_administration(user_id)
        def operation(db):
            _require(type(user_id) is int and user_id > 0)
            self._lock_user(db, user_id, require_active=False)
            rows = db.execute(select(_TABLE.c.secret_digest, _TABLE.c.last_activity_at).where(
                _TABLE.c.user_id == user_id, _TABLE.c.revoked_at.is_(None)
            ).order_by(_TABLE.c.secret_digest).with_for_update()).mappings().all()
            now = max(self._times(db))
            _require(all(_utc(row["last_activity_at"]) <= now for row in rows))
            result = db.execute(update(_TABLE).where(_TABLE.c.user_id == user_id,
                                _TABLE.c.revoked_at.is_(None)).values(revoked_at=now))
            _require(type(result.rowcount) is int and result.rowcount == len(rows))
            return result.rowcount
        return self._run(operation)

    def _authorize_administration(self, user_id):
        """Server authority callback, never a client bool or an implicit grant."""
        allowed = False
        try:
            if type(user_id) is int and user_id > 0 and self._authorize_user is not None:
                allowed = self._authorize_user(user_id=user_id) is None
        except Exception:
            pass
        if not allowed:
            raise SessionStoreRejected()
