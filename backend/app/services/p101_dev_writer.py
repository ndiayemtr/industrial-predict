"""Fail-closed PostgreSQL port scaffold. No persistence path is enabled.

Preflight is diagnostic only: its SELECTs neither lock authority nor exclude
phantoms. A successful preflight is NOT a capability to insert or commit.
"""

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from hashlib import sha256
import json
from typing import Callable, ContextManager

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, SessionTransactionOrigin

from app.core.authorization import AuthorizationEffect, Permission, decide_authorization
from app.core.caller_session import CurrentCaller, CurrentCallerProvider, SessionReference
from app.models import Company, Site, Equipment, Sensor, Measurement
from app.models.prediction_record import PredictionRecord
from app.p101_dev.adapter import IndustrialChain, IndustrialSnapshot, evaluate_snapshot
from app.p101_dev.contracts import Computed
from app import p101_dev_loader as reader
from app.services.p101_dev_orchestration import PredictionDraft, PreparedPrediction


class WriterRefused(ValueError):
    def __init__(self):
        super().__init__("P101_DEV_WRITER_REFUSED")


def _require(condition):
    if not condition:
        raise WriterRefused()


def _deny():
    # Raised outside exception handlers; never expose driver/identity diagnostics.
    try:
        raise WriterRefused() from None
    except WriterRefused as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise


@dataclass(frozen=True, slots=True, repr=False)
class PostgreSQLDestination:
    """Server-configured exact target, never derived from browser input or .env."""

    database: str
    session_user: str
    current_user: str
    server_address: str
    server_port: int

    def __post_init__(self):
        _require(all(type(value) is str and value and value == value.strip()
                     for value in (self.database, self.session_user, self.current_user, self.server_address)))
        _require(type(self.server_port) is int and 0 < self.server_port <= 65535)


CONNECTION_SQL = text(
    "SELECT current_database() AS database, session_user AS session_user, "
    "current_user AS current_user, inet_server_addr()::text AS server_address, "
    "inet_server_port() AS server_port, "
    "current_setting('transaction_isolation') AS isolation, "
    "current_setting('transaction_read_only') AS read_only"
)


def _state(session):
    """Inspect an already bound Connection; never Session.connection()/Engine.connect()."""
    _require(isinstance(session, Session) and session.is_active is True)
    _require(session.in_transaction() is True and session.in_nested_transaction() is False)
    tx = session.get_transaction()
    _require(tx is not None and tx.is_active is True and tx.origin is SessionTransactionOrigin.BEGIN)
    _require(session.autoflush is False and not session.new and not session.dirty and not session.deleted)
    _require(session.join_transaction_mode == "rollback_only")
    connection = session.get_bind()
    _require(isinstance(connection, Connection))
    _require(all(session.get_bind(mapper=model) is connection
                 for model in (Company, Site, Equipment, Sensor, Measurement, PredictionRecord)))
    _require(connection.dialect.name == "postgresql" and connection.closed is False
             and connection.invalidated is False)
    options = connection.get_execution_options()
    _require(not options.get("schema_translate_map") and options.get("isolation_level") != "AUTOCOMMIT")
    _require(connection.in_transaction() is True and connection.in_nested_transaction() is False)
    physical = connection.get_transaction()
    _require(physical is not None and physical.is_active is True)
    driver = reader._driver(connection)  # Same sync psycopg/native non-autocommit contract as DEV-2.
    isolation = connection.get_isolation_level()
    _require(isolation == "SERIALIZABLE")
    _require(reader._driver(connection) is driver)
    return connection, tx, physical, driver


def _verify(session, destination):
    before = _state(session)
    proof = before[0].execute(CONNECTION_SQL).mappings().one()
    _require(dict(proof) == dict(database=destination.database, session_user=destination.session_user,
        current_user=destination.current_user, server_address=destination.server_address,
        server_port=destination.server_port, isolation="serializable", read_only="off"))
    after = _state(session)
    _require(all(a is b for a, b in zip(before, after)))
    return before


class P101PostgreSQLWriter:
    """Injectable OrchestrationPort with an unconditional write barrier.

    read_context owns the existing DEV-2 lifecycle. caller_provider is a trusted
    server dependency (CurrentCallerProvider), never a client-supplied decision.
    No provider or read context is installed by default. Neither dependency is
    called when entering write(). There is no enable flag or injected SQL sink.
    """

    def __init__(self, *, destination: PostgreSQLDestination,
                 caller_provider: CurrentCallerProvider,
                 read_context: Callable[[], ContextManager[Session]]):
        _require(type(destination) is PostgreSQLDestination)
        destination.__post_init__()
        _require(callable(getattr(caller_provider, "current_caller", None)) and callable(read_context))
        self._destination = destination
        self._provider = caller_provider
        self._read_context = read_context

    def read(self):
        return self._read_context()

    def current_caller(self, session, *, reference: SessionReference, now: datetime) -> CurrentCaller:
        try:
            _require(isinstance(session, Session) and type(reference) is SessionReference)
            reference.__post_init__()
            _require(type(now) is datetime and now.tzinfo is not None and now.utcoffset() == timedelta(0))
            caller = self._provider.current_caller(reference=reference, now=now)
            _require(type(caller) is CurrentCaller)
            caller.__post_init__()
            _require(caller.session_reference == reference and caller.refreshed_at == now)
            return caller
        except Exception:
            pass
        _deny()

    def preflight(self, session: Session, *, plan: PreparedPrediction, now: datetime) -> PredictionRecord:
        """Diagnostic SELECTs + transient ORM mapping, no lock, add, flush or commit.

        Caller explicitly supplies an existing SERIALIZABLE RW transaction.
        The returned record has no id and is never attached to the Session.
        It must not be used as authorization for any later persistence action.
        """
        try:
            _require(type(plan) is PreparedPrediction and type(plan.draft) is PredictionDraft
                     and type(plan.draft.computed) is Computed)
            _require(type(now) is datetime and now.tzinfo is not None and now.utcoffset() == timedelta(0)
                     and now >= plan.prepared_at)
            initial = _verify(session, self._destination)
            caller = self.current_caller(session, reference=plan.reference, now=now)
            _require((caller.identity.user_id, caller.identity.issuer, caller.identity.subject) == plan.actor)
            decision = decide_authorization(identity=caller.identity, memberships=caller.memberships,
                company_id=plan.snapshot.chain.company_id, permission=Permission.PREDICTIONS_ANALYZE)
            _require(decision.effect is AuthorizationEffect.ALLOW)
            connection = initial[0]
            rows = connection.execute(reader.CHAIN_SQL.where(reader.n.c.id == plan.snapshot.chain.sensor_id)
                                      .limit(2)).mappings().all()
            _require(len(rows) == 1)
            chain = IndustrialChain(**dict(rows[0]))
            _require(chain == plan.snapshot.chain and chain.company_id == decision.company_id)
            targets = connection.execute(reader.MEASUREMENT_SQL.where(
                reader.m.c.id == plan.snapshot.target.id, reader.m.c.sensor_id == chain.sensor_id)
                .limit(2)).mappings().all()
            _require(len(targets) == 1)
            target = reader._measurement(dict(targets[0]), chain.sensor_id)
            lower = target.timestamp - timedelta(days=10)
            upper = min(target.timestamp, plan.snapshot.event_cutoff)
            rows = connection.execute(reader.MEASUREMENT_SQL.where(
                reader.m.c.sensor_id == chain.sensor_id, reader.m.c.id != target.id,
                reader.m.c.timestamp >= lower, reader.m.c.timestamp <= upper)
                .order_by(reader.m.c.timestamp.asc(), reader.m.c.id.asc()).limit(33)).mappings().all()
            _require(len(rows) <= 32)
            references = tuple(reader._measurement(dict(row), chain.sensor_id) for row in rows)
            _require(all(lower <= row.timestamp <= upper for row in references))
            current = IndustrialSnapshot(chain, target, references, plan.snapshot.event_cutoff,
                                         now, plan.snapshot.provenance)
            _require(replace(current, observed_at=plan.snapshot.observed_at) == plan.snapshot)
            computed = evaluate_snapshot(replace(current, observed_at=plan.snapshot.observed_at))
            # Equality also checks score/statistics/details, not just claimed hashes.
            _require(type(computed) is Computed and computed == plan.draft.computed)
            key = sha256(json.dumps([computed.asset.company_id, computed.asset.equipment_id,
                computed.asset.sensor_id, computed.target.measurement_id, computed.model_name,
                computed.model_version], separators=(",", ":")).encode()).hexdigest()
            _require(plan.key == key)
            final = _verify(session, self._destination)
            _require(all(a is b for a, b in zip(initial, final)))
            return PredictionRecord(**plan.draft.values(created_at=now))
        except Exception:
            pass
        _deny()

    @contextmanager
    def write(self):
        _deny()
        yield  # pragma: no cover -- satisfy ContextManager, never acquire a connection.

    def lock_and_reload(self, session, *, plan, authorization, now):
        _deny()  # No qualified authority/phantom locking implementation exists.

    def reserve_and_stage(self, session, *, key, draft, created_at):
        _deny()  # No durable unique operation reservation exists in the examined model.

    def finish(self, session):
        _deny()  # Never claim an acknowledgement for an operation we cannot commit.
