"""Private, read-only operator diagnostic for real P101 measurements.

Not imported by the HTTP application. The caller supplies an already verified
PostgreSQL SQLAlchemy Connection; this function owns one bounded READ ONLY
REPEATABLE READ transaction and never owns/closes the supplied connection.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, SessionTransactionOrigin
from psycopg import Connection as PsycopgConnection
from psycopg.pq import TransactionStatus

from app.core.authorization import AuthorizationDecision, AuthorizationEffect, Permission
from app.models import Company, Site, Equipment, Sensor, Measurement
from app.p101_dev.adapter import evaluate_snapshot
from app.p101_dev.contracts import (
    Abstained, AbstentionCode, Computed, DeclaredProvenance, Rejected, RejectionCode,
)
from app.p101_dev_loader import load_snapshot


# Match the existing application transaction limits (lock_timeout=5s,
# statement_timeout=15s). These are per lock wait/instruction, not total runtime.
LOCK_TIMEOUT_MS = 5000
STATEMENT_TIMEOUT_MS = 15000


def _native_connection(connection: Connection):
    """Return the actual psycopg connection, rejecting hidden native state."""
    try:
        if connection.dialect.driver != "psycopg" or connection.dialect.is_async is not False:
            raise ValueError
        proxy = connection.connection
        native = proxy.driver_connection
        if (proxy.dbapi_connection is not native or not isinstance(native, PsycopgConnection)
                or native.closed is not False or native.broken is not False
                or native.autocommit is not False):
            raise ValueError
        return native
    except Exception:
        raise DiagnosticRefused('NATIVE_CONNECTION_UNAVAILABLE') from None


def _native_idle(connection: Connection):
    native = _native_connection(connection)
    try:
        if native.info.transaction_status is not TransactionStatus.IDLE:
            raise DiagnosticRefused('NATIVE_CONNECTION_NOT_IDLE')
    except DiagnosticRefused:
        raise
    except Exception:
        raise DiagnosticRefused('NATIVE_CONNECTION_UNAVAILABLE') from None
    return native


@dataclass(frozen=True, slots=True)
class SensorDiagnostic:
    sensor_id: int
    sensor_type: str
    unit: str
    target_measurement_id: int | None
    target_timestamp_utc: str | None
    window_measurement_count: int
    quality_counts: tuple[tuple[str, int], ...]
    first_timestamp_utc: str | None
    last_timestamp_utc: str | None
    result: Computed | Abstained | Rejected | None
    outcome_code: str | None = None

    @property
    def status(self) -> str:
        # A sensor with no target has no evaluator result; keep that distinction
        # explicit and never manufacture a measurement ID to build Abstained.
        return self.result.status if self.result is not None else "abstained"


@dataclass(frozen=True, slots=True)
class OperatorDiagnostic:
    company_id: int
    site_id: int
    equipment_id: int
    cutoff_utc: str
    sensors: tuple[SensorDiagnostic, ...]


class DiagnosticRefused(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__('P101_OPERATOR_DIAGNOSTIC_REFUSED')


def diagnose(connection: Connection, *, company_id: int, site_id: int, equipment_id: int,
             cutoff_utc: datetime, provenance: DeclaredProvenance) -> OperatorDiagnostic:
    """Run P101 for latest existing targets at/before cutoff, one per sensor.

    Selection and quality summaries are read in the same physical snapshot used
    by the existing loader/evaluator. Abstentions/rejections never get repaired.
    """
    if (not isinstance(connection, Connection) or connection.closed or connection.invalidated
            or connection.in_transaction() or connection.in_nested_transaction()):
        raise DiagnosticRefused('CONNECTION_NOT_IDLE')
    if (type(LOCK_TIMEOUT_MS) is not int or not 0 < LOCK_TIMEOUT_MS <= 2147483647
            or type(STATEMENT_TIMEOUT_MS) is not int or not 0 < STATEMENT_TIMEOUT_MS <= 2147483647):
        raise DiagnosticRefused('INVALID_SQL_TIMEOUT')
    native = _native_idle(connection)
    if any(type(value) is not int or value < 1 or value > 2147483647
           for value in (company_id, site_id, equipment_id)):
        raise DiagnosticRefused('INVALID_SCOPE')
    if (type(cutoff_utc) is not datetime or cutoff_utc.tzinfo is None
            or cutoff_utc.utcoffset() != timedelta(0) or type(provenance) is not DeclaredProvenance
            or provenance.synthetic):
        raise DiagnosticRefused('INVALID_CUTOFF_OR_PROVENANCE')
    cutoff = cutoff_utc.astimezone(timezone.utc)
    authorization = AuthorizationDecision(AuthorizationEffect.ALLOW, company_id, Permission.PREDICTIONS_ANALYZE)
    try:
        connection = connection.execution_options(isolation_level='REPEATABLE READ')
        if _native_idle(connection) is not native:
            raise DiagnosticRefused('NATIVE_CONNECTION_CHANGED')
        transaction = connection.begin()
        try:
            connection.exec_driver_sql('SET TRANSACTION READ ONLY')
            connection.execute(text("SELECT set_config('lock_timeout', :timeout, true)"),
                               {'timeout': f'{LOCK_TIMEOUT_MS}ms'})
            connection.execute(text("SELECT set_config('statement_timeout', :timeout, true)"),
                               {'timeout': f'{STATEMENT_TIMEOUT_MS}ms'})
            with Session(bind=connection, autoflush=False, join_transaction_mode='rollback_only') as session:
                with session.begin():
                    status = connection.execute(text("""
                        SELECT current_setting('transaction_isolation') AS isolation,
                               current_setting('transaction_read_only') AS read_only,
                               (SELECT setting::int FROM pg_settings WHERE name='lock_timeout') AS lock_timeout_ms,
                               (SELECT setting::int FROM pg_settings WHERE name='statement_timeout') AS statement_timeout_ms
                    """)).mappings().one()
                    if status != {'isolation': 'repeatable read', 'read_only': 'on',
                                  'lock_timeout_ms': LOCK_TIMEOUT_MS,
                                  'statement_timeout_ms': STATEMENT_TIMEOUT_MS}:
                        raise DiagnosticRefused('TRANSACTION_GUARD_MISMATCH')
                    if _native_connection(connection) is not native:
                        raise DiagnosticRefused('NATIVE_CONNECTION_CHANGED')
                    chain = (Company.__table__.join(Site.__table__, Site.company_id == Company.id)
                        .join(Equipment.__table__, Equipment.site_id == Site.id))
                    scope = connection.execute(select(Company.id, Site.id, Equipment.id).select_from(chain).where(
                        Company.id == company_id, Site.id == site_id, Equipment.id == equipment_id).limit(2)).all()
                    if len(scope) != 1:
                        raise DiagnosticRefused('SCOPE_NOT_FOUND_OR_AMBIGUOUS')
                    sensors = connection.execute(select(Sensor.id, Sensor.sensor_type, Sensor.unit).where(
                        Sensor.equipment_id == equipment_id).order_by(Sensor.id).limit(101)).mappings().all()
                    if len(sensors) > 100:
                        raise DiagnosticRefused('SENSOR_LIMIT')
                    reports = []
                    for sensor in sensors:
                        target_row = connection.execute(select(Measurement.id, Measurement.timestamp).where(
                            Measurement.sensor_id == sensor['id'], Measurement.timestamp <= cutoff)
                            .order_by(Measurement.timestamp.desc(), Measurement.id.desc()).limit(1)).mappings().first()
                        if target_row is None:
                            reports.append(SensorDiagnostic(sensor['id'], sensor['sensor_type'], sensor['unit'],
                                None, None, 0, (), None, None, None,
                                AbstentionCode.INSUFFICIENT_HISTORY.value))
                            continue
                        target_at = target_row['timestamp'].astimezone(timezone.utc)
                        lower = target_at - timedelta(days=10)
                        rows = connection.execute(select(Measurement.timestamp, Measurement.quality).where(
                            Measurement.sensor_id == sensor['id'], Measurement.timestamp >= lower,
                            Measurement.timestamp <= target_at).order_by(Measurement.timestamp, Measurement.id)
                            .limit(5001)).all()
                        if len(rows) > 5000:
                            raise DiagnosticRefused('MEASUREMENT_WINDOW_LIMIT')
                        quality = Counter(row.quality for row in rows)
                        snapshot = load_snapshot(session, authorization=authorization, equipment_id=equipment_id,
                            sensor_id=sensor['id'], target_measurement_id=target_row['id'], event_cutoff=cutoff,
                            observed_at=datetime.now(timezone.utc), provenance=provenance)
                        if _native_connection(connection) is not native:
                            raise DiagnosticRefused('NATIVE_CONNECTION_CHANGED')
                        result = evaluate_snapshot(snapshot)
                        if _native_connection(connection) is not native:
                            raise DiagnosticRefused('NATIVE_CONNECTION_CHANGED')
                        reports.append(SensorDiagnostic(sensor['id'], sensor['sensor_type'], sensor['unit'],
                            target_row['id'], target_at.isoformat(), len(rows), tuple(sorted(quality.items())),
                            rows[0].timestamp.astimezone(timezone.utc).isoformat() if rows else None,
                            rows[-1].timestamp.astimezone(timezone.utc).isoformat() if rows else None, result))
            transaction.rollback()
        except Exception:
            if transaction.is_active:
                transaction.rollback()
            raise
        return OperatorDiagnostic(company_id, site_id, equipment_id, cutoff.isoformat(), tuple(reports))
    except DiagnosticRefused:
        raise
    except Exception:
        raise DiagnosticRefused('DIAGNOSTIC_UNAVAILABLE') from None
