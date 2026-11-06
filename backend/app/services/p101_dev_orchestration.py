"""Injected orchestration only. No authentication implementation or SQL writer.

Every port assertion is trusted integration input, not cryptographic evidence.
No port, clock, writer, HTTP route or production authority is installed here.
"""

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
import json
from threading import Lock
from typing import Callable, ContextManager, Protocol

from sqlalchemy.orm import Session

from app.core.authorization import AuthorizationEffect, Permission, decide_authorization
from app.core.caller_session import CurrentCaller, SessionReference
from app.p101_dev.adapter import IndustrialSnapshot, evaluate_snapshot
from app.p101_dev.contracts import Abstained, Computed, DeclaredProvenance, Rejected, Result
from app.p101_dev_loader import load_snapshot


class OrchestrationError(ValueError):
    def __init__(self):
        super().__init__("P101_DEV_ORCHESTRATION_REFUSED")


def _deny():
    try:
        raise OrchestrationError() from None
    except OrchestrationError as error:
        error.__cause__ = error.__context__ = None
        error.__suppress_context__ = True
        raise


def _require(condition):
    if not condition:
        _deny()


def _utc(value):
    _require(type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None)
    return value.astimezone(timezone.utc)


class PersistenceState(StrEnum):
    REFUSED = "refused"
    COMMIT_CONFIRMED = "commit_confirmed"
    ROLLBACK_CONFIRMED = "rollback_confirmed"
    UNCERTAIN = "uncertain"


class DuplicatePrediction(ValueError):
    """Port asserts unique reservation refused before inserting a prediction."""


@dataclass(frozen=True, slots=True, repr=False)
class PredictionDraft:
    computed: Computed

    def values(self, *, created_at: datetime) -> dict:
        """Fresh business-column mapping; metadata alone never permits writing."""
        r = self.computed
        return dict(equipment_id=r.asset.equipment_id, sensor_id=r.asset.sensor_id,
            measurement_id=r.target.measurement_id, prediction_type="anomaly", score=r.score,
            level=None, is_alert=r.is_alert, model_name=r.model_name, model_version=r.model_version,
            horizon_hours=None, details=r.details,
            predicted_at=datetime.fromisoformat(r.target.timestamp.replace("Z", "+00:00")),
            created_at=_utc(created_at))


@dataclass(frozen=True, slots=True, repr=False)
class PreparedPrediction:
    snapshot: IndustrialSnapshot
    draft: PredictionDraft
    reference: SessionReference
    actor: tuple[int, str, str]
    prepared_at: datetime
    key: str
    _token: object = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class AnalysisOutcome:
    result: Result
    prepared: PreparedPrediction | None
    real_attested: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True, repr=False)
class PersistenceReport:
    state: PersistenceState
    prediction_id: int | None = None
    cleanup_failed: bool = False
    real_attested: bool = field(default=False, init=False)


class OrchestrationPort(Protocol):
    """No implementation supplied. Context owners alone manage transactions.

    read: verified caller-owned DEV-2 READ ONLY snapshot, completed on exit.
    write: NEW RW transaction, destination checked; exceptions roll back, never
    suppress and never auto-commit. current_caller: verify live session and fresh
    local state IN the supplied transaction; in write, retain authority locks.
    lock_and_reload: lock/re-read parents, target AND whole candidate window,
    preventing mutation/phantoms through finish; return actual observed_at=now.
    reserve_and_stage: atomic uniqueness by key, INSERT only, no internal commit.
    finish: explicit confirmed commit/rollback or uncertainty, no retries. Exit
    after finish does resource cleanup only. Doubles do not prove these contracts.
    """
    def read(self) -> ContextManager[Session]: ...
    def write(self) -> ContextManager[Session]: ...
    def current_caller(self, session: Session, *, reference: SessionReference, now: datetime) -> CurrentCaller: ...
    def lock_and_reload(self, session: Session, *, plan: PreparedPrediction, authorization, now: datetime) -> IndustrialSnapshot: ...
    def reserve_and_stage(self, session: Session, *, key: str, draft: PredictionDraft, created_at: datetime) -> int: ...
    def finish(self, session: Session) -> PersistenceState: ...


class P101DevOrchestrator:
    def __init__(self, *, port: OrchestrationPort, clock: Callable[[], datetime], loader=load_snapshot):
        _require(callable(clock) and callable(loader))
        _require(all(callable(getattr(port, method, None)) for method in (
            "read", "write", "current_caller", "lock_and_reload", "reserve_and_stage", "finish")))
        self._port, self._clock, self._loader = port, clock, loader
        self._pending, self._attempted, self._lock = {}, set(), Lock()

    def _caller(self, session, reference, now, company_id):
        caller = self._port.current_caller(session, reference=reference, now=now)
        _require(type(caller) is CurrentCaller)
        caller.__post_init__()
        _require(caller.session_reference == reference and caller.refreshed_at == now)
        decision = decide_authorization(identity=caller.identity, memberships=caller.memberships,
                                        company_id=company_id, permission=Permission.PREDICTIONS_ANALYZE)
        _require(decision.effect is AuthorizationEffect.ALLOW)
        return caller, decision

    def prepare(self, *, reference: SessionReference, company_id: int, equipment_id: int,
                sensor_id: int, target_measurement_id: int, event_cutoff: datetime,
                provenance: DeclaredProvenance) -> AnalysisOutcome:
        completed = False
        try:
            _require(type(reference) is SessionReference)
            reference.__post_init__()
            now = _utc(self._clock())
            with self._port.read() as session:
                caller, decision = self._caller(session, reference, now, company_id)
                snapshot = self._loader(session, authorization=decision, equipment_id=equipment_id,
                    sensor_id=sensor_id, target_measurement_id=target_measurement_id,
                    event_cutoff=event_cutoff, observed_at=now, provenance=provenance)
                _require(type(snapshot) is IndustrialSnapshot and snapshot.chain.company_id == company_id
                    and snapshot.chain.equipment_id == equipment_id and snapshot.chain.sensor_id == sensor_id
                    and snapshot.target.id == target_measurement_id and _utc(snapshot.observed_at) == now)
                result = evaluate_snapshot(snapshot)
                _require(type(result) in (Computed, Abstained, Rejected))
                read_transaction = session.get_bind().get_transaction()
                _require(read_transaction is not None and read_transaction.is_active)
                completed = True
            _require(completed)  # A suppressing/failed read context cannot prepare a plan.
            _require(not read_transaction.is_active)
            if type(result) is not Computed:
                return AnalysisOutcome(result, None)
            r = result
            key = sha256(json.dumps([r.asset.company_id, r.asset.equipment_id, r.asset.sensor_id,
                r.target.measurement_id, r.model_name, r.model_version], separators=(",", ":")).encode()).hexdigest()
            actor = (caller.identity.user_id, caller.identity.issuer, caller.identity.subject)
            plan = PreparedPrediction(snapshot, PredictionDraft(result), reference, actor, now, key, object())
            with self._lock:
                self._pending[plan._token] = (plan, session, read_transaction)
            return AnalysisOutcome(result, plan)
        except Exception:
            pass
        _deny()

    def persist(self, plan: PreparedPrediction) -> PersistenceReport:
        """Optional injected write simulation/path. One attempt per plan in this instance.

        No persistence implementation exists here. Never wire an unqualified port.
        An uncertain plan cannot be replayed in this instance, but real durable
        uniqueness across instances/restarts is the port's mandatory responsibility.
        """
        _require(type(plan) is PreparedPrediction)
        with self._lock:
            entry = self._pending.get(plan._token)
            _require(plan._token not in self._attempted and entry is not None and entry[0] is plan)
            del self._pending[plan._token]
            self._attempted.add(plan._token)
        state, prediction_id, staged = PersistenceState.REFUSED, None, False
        cleanup_failed = False
        try:
            now = _utc(self._clock())
            _require(now >= plan.prepared_at)
            with self._port.write() as session:
                _require(isinstance(session, Session) and session is not entry[1]
                    and session.is_active and session.in_transaction() and not session.in_nested_transaction())
                write_transaction = session.get_bind().get_transaction()
                _require(write_transaction is not None and write_transaction.is_active
                    and write_transaction is not entry[2] and not entry[2].is_active)
                caller, decision = self._caller(session, plan.reference, now, plan.snapshot.chain.company_id)
                _require((caller.identity.user_id, caller.identity.issuer, caller.identity.subject) == plan.actor)
                current = self._port.lock_and_reload(session, plan=plan, authorization=decision, now=now)
                _require(type(current) is IndustrialSnapshot and _utc(current.observed_at) == now)
                # Compare source content using the ORIGINAL observation context;
                # the fresh write observation time was independently checked above.
                checked = evaluate_snapshot(replace(current, observed_at=plan.snapshot.observed_at))
                _require(type(checked) is Computed
                    and checked.input_sha256 == plan.draft.computed.input_sha256
                    and checked.details_sha256 == plan.draft.computed.details_sha256)
                staged = True
                state = PersistenceState.UNCERTAIN
                try:
                    candidate_id = self._port.reserve_and_stage(session, key=plan.key, draft=plan.draft, created_at=now)
                except DuplicatePrediction:
                    # This exception has a no-insert contract ONLY at this boundary.
                    staged, state = False, PersistenceState.REFUSED
                    _deny()
                _require(type(candidate_id) is int and candidate_id > 0)
                acknowledgement = self._port.finish(session)
                _require(type(acknowledgement) is PersistenceState and acknowledgement is not PersistenceState.REFUSED)
                state = acknowledgement
                if state is PersistenceState.COMMIT_CONFIRMED:
                    prediction_id = candidate_id
        except Exception:
            cleanup_failed = state in (PersistenceState.COMMIT_CONFIRMED, PersistenceState.ROLLBACK_CONFIRMED)
            if not cleanup_failed:
                state = PersistenceState.UNCERTAIN if staged else PersistenceState.REFUSED
        return PersistenceReport(state, prediction_id, cleanup_failed)
