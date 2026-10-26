"""Explicit writer-only Core persistence. No connection or computation at import."""

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, MetaData, String, Table, insert, select, text
from sqlalchemy.exc import IntegrityError

from app.p101_local_demo.contracts import CalculationContext
from app.p101_local_demo.prediction_mapping import (
    PersistenceResult, PredictionError, compare_records, prepare_predictions, validate_writer,
)
from app.p101_local_demo.processing import read_and_evaluate
from app.p101_local_demo.provisioning import lock, transaction
from app.p101_local_demo.reader import IDENTITY_SQL, validate_identity, validate_transport
from app.p101_local_demo.setup_config import ROLES, SetupSettings
from app.p101_persistence.contracts import FIXTURE_SHA256


metadata = MetaData()
prediction_records = Table('prediction_records', metadata,
    Column('id', Integer, primary_key=True), Column('equipment_id', Integer),
    Column('sensor_id', Integer), Column('measurement_id', Integer), Column('prediction_type', String),
    Column('score', Float), Column('level', String), Column('is_alert', Boolean),
    Column('model_name', String), Column('model_version', String), Column('horizon_hours', Float),
    Column('details', JSON), Column('predicted_at', DateTime(timezone=True)),
    Column('created_at', DateTime(timezone=True)), schema='public')

WRITER_SQL = text("""
SELECT m.fixture_sha256, m.bootstrap_sha256,
 NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='p101_local_owner' AND rolcanlogin) AS owner_closed,
 NOT EXISTS(SELECT 1 FROM pg_stat_activity WHERE usename='p101_local_owner') AS no_owner_session,
 has_table_privilege(current_user,'public.prediction_records','SELECT')
 AND has_table_privilege(current_user,'public.prediction_records','INSERT')
 AND NOT has_table_privilege(current_user,'public.prediction_records','UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
 AND NOT has_any_column_privilege(current_user,'public.prediction_records','UPDATE,REFERENCES') AS prediction_rights,
 NOT has_table_privilege(current_user,'local_demo.environment','INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
 AND NOT has_any_column_privilege(current_user,'local_demo.environment','INSERT,UPDATE,REFERENCES') AS marker_immutable,
 EXISTS(SELECT 1 FROM pg_index WHERE indexrelid=to_regclass('public.uq_local_p101_target')
        AND indrelid='public.prediction_records'::regclass AND indisunique AND indisvalid AND indisready) AS unique_index,
 EXISTS(SELECT 1 FROM pg_constraint WHERE conrelid='public.prediction_records'::regclass
        AND conname='ck_local_p101_content' AND contype='c' AND convalidated) AS local_check
FROM local_demo.environment m WHERE m.singleton
""")


def guard_writer(connection, destination):
    import re
    validate_writer(destination)
    validate_transport(connection, destination)
    validate_identity(destination, connection.execute(IDENTITY_SQL).mappings().one())
    row = connection.execute(WRITER_SQL).mappings().one()
    if (row['fixture_sha256'] != FIXTURE_SHA256 or type(row['bootstrap_sha256']) is not str
            or re.fullmatch('[0-9a-f]{64}', row['bootstrap_sha256']) is None
            or any(row[k] is not True for k in ('owner_closed','no_owner_session','prediction_rights',
                                               'marker_immutable','unique_index','local_check'))):
        raise PredictionError('WRITER_GUARD_REJECTED')


def persist_in_transaction(connection, destination, reference, context, created_at):
    """Caller owns the transaction. No commit, rollback, source mutation or retry here."""
    guard_writer(connection, destination)
    lock(connection)  # Same cooperative advisory lock as provisioning/privileged maintenance.
    pair = read_and_evaluate(connection, destination, reference, context)
    plans = prepare_predictions(pair, destination, reference, context, created_at)
    # This fixed local profile permits only the two P101 predictions, not unrelated history.
    rows = tuple(dict(r) for r in connection.execute(select(prediction_records).order_by(
        prediction_records.c.id).limit(3)).mappings())
    if rows:
        return compare_records(rows, plans, pair.identities, destination, reference)
    try:
        rows = tuple(dict(r) for r in connection.execute(insert(prediction_records).values(
            [p.sql_values() for p in plans]).returning(prediction_records)).mappings())
    except IntegrityError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '23505':
            raise PredictionError('UNIQUE_CONFLICT_RETRY_REQUIRES_NEW_TRANSACTION') from None
        raise PredictionError('INSERT_REJECTED') from None
    checked = compare_records(rows, plans, pair.identities, destination, reference)
    return PersistenceResult('inserted', checked.records_json)


def run_predictions(settings, reference, context, *, execute=False, instance=None, created_at=None):
    """One fresh guarded writer transaction; expose success only after its single commit."""
    if type(settings) is not SetupSettings or type(context) is not CalculationContext:
        raise PredictionError('EXPLICIT_INPUTS_REQUIRED')
    destination = settings.destination(ROLES[2])
    validate_writer(destination)
    completed_body = False
    try:
        with transaction(settings, ROLES[2], execute=execute, instance=instance) as connection:
            result = persist_in_transaction(connection, destination, reference, context,
                                            context.prepared_at if created_at is None else created_at)
            completed_body = True
    except Exception as exc:
        if completed_body:
            raise PredictionError('COMMIT_UNCERTAIN_INSPECT_BEFORE_RETRY') from None
        # Existing transaction() sanitizes driver errors; recover only our stable domain code.
        seen = set()
        while exc is not None and id(exc) not in seen:
            seen.add(id(exc))
            if isinstance(exc, PredictionError):
                raise PredictionError(exc.code) from None
            exc = exc.__context__
        raise PredictionError('TRANSACTION_REJECTED') from None
    return result
