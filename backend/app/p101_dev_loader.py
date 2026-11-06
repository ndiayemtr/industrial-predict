"""Injected SQL reader, outside the pure p101_dev package. No engine or lifecycle.

An AuthorizationDecision is a trusted upstream assertion, NOT authentication.
Never construct it from browser IDs. The caller owns the connection/transaction,
destination verification, live B2B session and fresh authorization. Before any
future prediction write, recheck authorization AND industrial relationships.
"""

from datetime import datetime, timedelta, timezone
from enum import StrEnum

from psycopg import Connection as PsycopgConnection
from psycopg.pq import TransactionStatus

from sqlalchemy import MetaData, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, SessionTransactionOrigin

from app.core.authorization import AuthorizationDecision, AuthorizationEffect, Permission, POLICY_VERSION
from app.models import Company, Site, Equipment, Sensor, Measurement
from app.p101_dev.adapter import IndustrialChain, IndustrialMeasurement, IndustrialSnapshot
from app.p101_dev.contracts import DeclaredProvenance


class LoadCode(StrEnum):
    INVALID_REQUEST = "INVALID_REQUEST"
    SESSION_CONTRACT = "SESSION_CONTRACT"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    CHAIN_NOT_FOUND = "CHAIN_NOT_FOUND"
    TARGET_NOT_FOUND = "TARGET_NOT_FOUND"
    INCOHERENT_ROWS = "INCOHERENT_ROWS"
    CANDIDATE_LIMIT = "CANDIDATE_LIMIT"
    UNAVAILABLE = "UNAVAILABLE"


class SnapshotLoadError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__("P101_DEV_LOAD_REJECTED")


def _require(condition, code):
    if not condition:
        raise SnapshotLoadError(code)


def _id(value):
    return type(value) is int and 1 <= value <= 2147483647


def _aware(value):
    return type(value) is datetime and value.tzinfo is not None and value.utcoffset() is not None


def _utc(value):
    _require(_aware(value), LoadCode.INCOHERENT_ROWS)
    return value.astimezone(timezone.utc)


def _driver(connection):
    """Sync psycopg 3 only; inspect native state, never change it or connect."""
    try:
        _require(connection.dialect.driver == "psycopg" and connection.dialect.is_async is False,
                 LoadCode.SESSION_CONTRACT)
        proxy = connection.connection
        driver = proxy.driver_connection
        _require(proxy.dbapi_connection is driver and isinstance(driver, PsycopgConnection), LoadCode.SESSION_CONTRACT)
        _require(driver.closed is False and driver.broken is False, LoadCode.SESSION_CONTRACT)
        # Identity checks deliberately reject integer 0, mocks and unknown signals.
        _require(driver.autocommit is False and driver.info.transaction_status is TransactionStatus.INTRANS,
                 LoadCode.SESSION_CONTRACT)
        return driver
    except Exception:
        raise SnapshotLoadError(LoadCode.SESSION_CONTRACT) from None


TRANSACTION_SQL = text("SELECT current_setting('transaction_isolation') AS isolation, "
                       "current_setting('transaction_read_only') AS read_only")

# Private, public-qualified copies; no reflection/DDL or shared metadata mutation.
_metadata = MetaData()
c, s, e, n, m = (model.__table__.to_metadata(_metadata, schema="public")
                 for model in (Company, Site, Equipment, Sensor, Measurement))
CHAIN_SQL = select(
    c.c.id.label("company_id"), s.c.id.label("site_id"), s.c.company_id.label("site_company_id"),
    e.c.id.label("equipment_id"), e.c.site_id.label("equipment_site_id"),
    n.c.id.label("sensor_id"), n.c.equipment_id.label("sensor_equipment_id"), n.c.sensor_type, n.c.unit,
).select_from(n.join(e, n.c.equipment_id == e.c.id).join(s, e.c.site_id == s.c.id)
              .join(c, s.c.company_id == c.c.id))
MEASUREMENT_SQL = select(m.c.id, m.c.sensor_id, m.c.timestamp, m.c.value, m.c.quality)


def _transaction(session):
    _require(isinstance(session, Session), LoadCode.SESSION_CONTRACT)
    _require(session.is_active and session.in_transaction() and not session.in_nested_transaction(), LoadCode.SESSION_CONTRACT)
    tx = session.get_transaction()
    _require(tx is not None and tx.is_active and tx.origin is SessionTransactionOrigin.BEGIN, LoadCode.SESSION_CONTRACT)
    _require(not session.autoflush and not session.new and not session.dirty and not session.deleted, LoadCode.SESSION_CONTRACT)
    _require(session.join_transaction_mode == "rollback_only", LoadCode.SESSION_CONTRACT)
    connection = session.get_bind()
    _require(isinstance(connection, Connection), LoadCode.SESSION_CONTRACT)
    _require(all(session.get_bind(mapper=model) is connection for model in (Company, Site, Equipment, Sensor, Measurement)), LoadCode.SESSION_CONTRACT)
    _require(connection.dialect.name == "postgresql" and not connection.closed and not connection.invalidated,
             LoadCode.SESSION_CONTRACT)
    _require(not connection.get_execution_options().get("schema_translate_map"), LoadCode.SESSION_CONTRACT)
    _require(connection.in_transaction() and not connection.in_nested_transaction(), LoadCode.SESSION_CONTRACT)
    physical = connection.get_transaction()
    _require(physical is not None and physical.is_active, LoadCode.SESSION_CONTRACT)
    driver = _driver(connection)
    isolation = connection.get_isolation_level()
    _require(isolation in ("REPEATABLE READ", "SERIALIZABLE"), LoadCode.SESSION_CONTRACT)
    _require(_driver(connection) is driver, LoadCode.SESSION_CONTRACT)
    proof = connection.execute(TRANSACTION_SQL).mappings().one()
    _require(proof == {"isolation": isolation.lower(), "read_only": "on"}, LoadCode.SESSION_CONTRACT)
    _require(_driver(connection) is driver, LoadCode.SESSION_CONTRACT)
    return connection, tx, physical, isolation, driver


def _measurement(row, sensor_id):
    _require(set(row) == {"id", "sensor_id", "timestamp", "value", "quality"}, LoadCode.INCOHERENT_ROWS)
    _require(_id(row["id"]) and row["sensor_id"] == sensor_id and _id(row["sensor_id"]), LoadCode.INCOHERENT_ROWS)
    return IndustrialMeasurement(**(row | {"timestamp": _utc(row["timestamp"])}))


def load_snapshot(session: Session, *, authorization: AuthorizationDecision, equipment_id: int,
                  sensor_id: int, target_measurement_id: int, event_cutoff: datetime,
                  observed_at: datetime, provenance: DeclaredProvenance) -> IndustrialSnapshot:
    """Read only, using a caller-owned PG READ ONLY snapshot transaction.

    No begin/commit/rollback/close/flush, no ORM entity reads or identity cache.
    Tables are public-qualified; caller schema redirection is refused.
    No data-quality judgment or statistical calculation belongs to this loader.
    """
    failure = LoadCode.UNAVAILABLE
    try:
        _require(type(authorization) is AuthorizationDecision
                 and authorization.effect is AuthorizationEffect.ALLOW
                 and authorization.permission is Permission.PREDICTIONS_ANALYZE
                 and authorization.policy_version == POLICY_VERSION and _id(authorization.company_id), LoadCode.SCOPE_MISMATCH)
        _require(all(_id(value) for value in (equipment_id, sensor_id, target_measurement_id)), LoadCode.INVALID_REQUEST)
        _require(_aware(event_cutoff) and _aware(observed_at) and type(provenance) is DeclaredProvenance, LoadCode.INVALID_REQUEST)
        event_cutoff, observed_at = _utc(event_cutoff), _utc(observed_at)
        connection, tx, physical, isolation, driver = _transaction(session)
        rows = connection.execute(CHAIN_SQL.where(n.c.id == sensor_id).limit(2)).mappings().all()
        _require(len(rows) == 1, LoadCode.CHAIN_NOT_FOUND)
        chain = IndustrialChain(**dict(rows[0]))
        _require(all(_id(value) for value in (chain.company_id, chain.site_id, chain.site_company_id,
                 chain.equipment_id, chain.equipment_site_id, chain.sensor_id, chain.sensor_equipment_id)), LoadCode.INCOHERENT_ROWS)
        _require(chain.company_id == chain.site_company_id == authorization.company_id
                 and chain.equipment_id == chain.sensor_equipment_id == equipment_id
                 and chain.site_id == chain.equipment_site_id and chain.sensor_id == sensor_id, LoadCode.SCOPE_MISMATCH)
        targets = connection.execute(MEASUREMENT_SQL.where(m.c.id == target_measurement_id,
                                      m.c.sensor_id == sensor_id).limit(2)).mappings().all()
        _require(len(targets) == 1, LoadCode.TARGET_NOT_FOUND)
        target = _measurement(dict(targets[0]), sensor_id)
        _require(target.id == target_measurement_id and _aware(target.timestamp), LoadCode.INCOHERENT_ROWS)
        lower, upper = target.timestamp - timedelta(days=10), min(target.timestamp, event_cutoff)
        references = connection.execute(MEASUREMENT_SQL.where(
            m.c.sensor_id == sensor_id, m.c.id != target_measurement_id,
            m.c.timestamp >= lower, m.c.timestamp <= upper,
        ).order_by(m.c.timestamp.asc(), m.c.id.asc()).limit(33)).mappings().all()
        _require(len(references) <= 32, LoadCode.CANDIDATE_LIMIT)
        candidates = tuple(_measurement(dict(row), sensor_id) for row in references)
        _require(all(_aware(row.timestamp) and lower <= row.timestamp <= upper for row in candidates), LoadCode.INCOHERENT_ROWS)
        end = _transaction(session)
        _require(end[0] is connection and end[1] is tx and end[2] is physical and end[3] == isolation
                 and end[4] is driver,
                 LoadCode.SESSION_CONTRACT)
        return IndustrialSnapshot(chain, target, candidates, event_cutoff, observed_at, provenance)
    except SnapshotLoadError as error:
        failure = error.code if type(error.code) is LoadCode else LoadCode.UNAVAILABLE
    except Exception:
        pass
    # Outside except: driver values, connection details and causes are not exposed.
    try:
        raise SnapshotLoadError(failure) from None
    except SnapshotLoadError as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise
