"""Compiled SQL plus synthetic Session/Connection doubles; no PG or Docker."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, PropertyMock
from zoneinfo import ZoneInfo
import socket

import psycopg
from psycopg.pq import TransactionStatus
import pytest
import sqlalchemy
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, SessionTransactionOrigin

from app import p101_dev_loader as loader
from app.core.authorization import AuthorizationDecision, AuthorizationEffect, Permission
from app.p101_dev.adapter import evaluate_snapshot
from app.p101_dev.contracts import Abstained, AbstentionCode as A, Computed, DeclaredProvenance, Rejected


PRIVATE = "DO_NOT_EXPOSE_DRIVER_DIAGNOSTIC"


@pytest.fixture(autouse=True)
def no_live_database(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Live I/O forbidden")
    monkeypatch.setattr(sqlalchemy, "create_engine", forbidden)
    monkeypatch.setattr(Engine, "connect", forbidden)
    monkeypatch.setattr(psycopg, "connect", forbidden)
    monkeypatch.setattr(psycopg.Connection, "connect", forbidden)
    for name in ("connect", "connect_ex"):
        monkeypatch.setattr(socket.socket, name, forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.fixture
def db():
    time = datetime(2026, 4, 11, 13, 47, 2, 123456, tzinfo=timezone.utc)
    values = (65, 63, 67, 64.5, 65.5, 64.5, 65.5, 65, 65, 65)
    chain = dict(company_id=101, site_id=202, site_company_id=101, equipment_id=303,
        equipment_site_id=202, sensor_id=404, sensor_equipment_id=303, sensor_type="temperature", unit="°C")
    target = dict(id=11, sensor_id=404, timestamp=time, value=70, quality="good")
    refs = [dict(id=i+1, sensor_id=404, timestamp=time-timedelta(days=10-i), value=value, quality="good")
            for i, value in enumerate(values)]
    connection = Mock(spec=Connection)
    connection.dialect = SimpleNamespace(name="postgresql", driver="psycopg", is_async=False)
    connection.closed = connection.invalidated = False
    connection.in_transaction.return_value = True
    connection.in_nested_transaction.return_value = False
    connection.get_execution_options.return_value = {}
    connection.get_transaction.return_value = SimpleNamespace(is_active=True)
    connection.get_isolation_level.return_value = "REPEATABLE READ"
    driver = Mock(spec=psycopg.Connection)
    driver.closed = driver.broken = driver.autocommit = False
    driver.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
    connection.connection = SimpleNamespace(driver_connection=driver, dbapi_connection=driver)
    session = Mock(spec=Session)
    session.is_active = True
    session.autoflush = False
    session.new, session.dirty, session.deleted = set(), set(), set()
    session.join_transaction_mode = "rollback_only"
    session.in_transaction.return_value = True
    session.in_nested_transaction.return_value = False
    session.get_transaction.return_value = SimpleNamespace(is_active=True, origin=SessionTransactionOrigin.BEGIN)
    session.get_bind.return_value = connection
    data = SimpleNamespace(session=session, connection=connection, driver=driver, chain=[chain], target=[target], refs=refs,
        queries=[], proofs=[dict(isolation="repeatable read", read_only="on")]*2,
        arguments=dict(authorization=AuthorizationDecision(AuthorizationEffect.ALLOW, 101, Permission.PREDICTIONS_ANALYZE),
            equipment_id=303, sensor_id=404, target_measurement_id=11, event_cutoff=time,
            observed_at=time+timedelta(days=5), provenance=DeclaredProvenance("synthetic-sql-rows", "loader-review", True)))
    def execute(statement):
        result = Mock()
        if statement is loader.TRANSACTION_SQL:
            result.mappings.return_value.one.return_value = data.proofs.pop(0)
        else:
            compiled = statement.compile(dialect=postgresql.dialect())
            sql, params = str(compiled), compiled.params
            data.queries.append((sql, params))
            rows = data.chain if "JOIN public.equipments" in sql else data.refs if "measurements.id !=" in sql else data.target
            result.mappings.return_value.all.return_value = deepcopy(rows)
        return result
    connection.execute.side_effect = execute
    return data


def load(db, **overrides):
    return loader.load_snapshot(db.session, **(db.arguments | overrides))


def refused(db, code, **overrides):
    with pytest.raises(loader.SnapshotLoadError) as caught: load(db, **overrides)
    assert caught.value.code is code
    assert str(caught.value) == "P101_DEV_LOAD_REJECTED"
    assert caught.value.__cause__ is None and caught.value.__context__ is None


def test_snapshot_and_actual_sql_shape(db):
    before = deepcopy((db.chain, db.target, db.refs))
    snapshot = load(db)
    assert (db.chain, db.target, db.refs) == before
    assert snapshot.provenance is db.arguments["provenance"]
    assert snapshot.chain.equipment_id == 303 and snapshot.target.id == 11
    assert [row.id for row in snapshot.references] == list(range(1, 11))
    assert snapshot.target.timestamp.microsecond == 123456
    result = evaluate_snapshot(snapshot)
    assert type(result) is Computed and result.score == 1 and result.is_alert is True
    assert result.statistics.mean == 65 and result.statistics.sample_std == 1
    assert db.connection.execute.call_count == 5
    chain_sql, chain_params = db.queries[0]
    assert all("public."+name in chain_sql for name in ("companies", "sites", "equipments", "sensors"))
    assert chain_params["id_1"] == 404
    sql, params = db.queries[-1]
    assert "public.measurements" in sql and "ORDER BY" in sql
    assert "measurements.timestamp >=" in sql and "measurements.timestamp <=" in sql
    assert "measurements.id !=" in sql and "measurements.sensor_id =" in sql
    assert "DISTINCT" not in sql and "OFFSET" not in sql and "quality =" not in sql
    assert params["timestamp_1"] == snapshot.target.timestamp-timedelta(days=10)
    assert params["timestamp_2"] == snapshot.target.timestamp and params["param_1"] == 33
    for name in ("begin", "commit", "rollback", "close", "flush", "connection"):
        getattr(db.session, name).assert_not_called()
    for name in ("begin", "commit", "rollback", "close", "execution_options"):
        getattr(db.connection, name).assert_not_called()
    for name in ("commit", "rollback", "close", "set_autocommit"):
        getattr(db.driver, name).assert_not_called()
    assert db.driver.autocommit is False


@pytest.mark.parametrize("field,value", [("company_id", 999), ("site_company_id", 999),
    ("equipment_id", 999), ("equipment_site_id", 999), ("sensor_equipment_id", 999), ("sensor_id", 999)])
def test_incoherent_chain_stops_before_measurement_reads(db, field, value):
    db.chain[0][field] = value
    refused(db, loader.LoadCode.SCOPE_MISMATCH)
    assert len(db.queries) == 1


@pytest.mark.parametrize("which", ["chain", "target"])
@pytest.mark.parametrize("duplicate", [False, True])
def test_missing_or_ambiguous_parents_and_target(db, which, duplicate):
    rows = getattr(db, which)
    setattr(db, which, rows*2 if duplicate else [])
    refused(db, loader.LoadCode.CHAIN_NOT_FOUND if which == "chain" else loader.LoadCode.TARGET_NOT_FOUND)


@pytest.mark.parametrize("which", ["target", "refs"])
def test_foreign_sensor_row_rejected(db, which):
    getattr(db, which)[0]["sensor_id"] = 999
    refused(db, loader.LoadCode.INCOHERENT_ROWS)


def test_wrong_requested_equipment_and_measurement_rejected(db):
    refused(db, loader.LoadCode.SCOPE_MISMATCH, equipment_id=999)
    db.queries.clear()
    refused(db, loader.LoadCode.INCOHERENT_ROWS, target_measurement_id=999)


@pytest.mark.parametrize("permission,effect,company", [(Permission.PREDICTIONS_READ, AuthorizationEffect.ALLOW, 101),
    (Permission.PREDICTIONS_ANALYZE, AuthorizationEffect.DENY, 101),
    (Permission.PREDICTIONS_ANALYZE, AuthorizationEffect.ALLOW, True)])
def test_scope_assertion_is_required_before_sql(db, permission, effect, company):
    refused(db, loader.LoadCode.SCOPE_MISMATCH, authorization=AuthorizationDecision(effect, company, permission))
    db.connection.execute.assert_not_called()


@pytest.mark.parametrize("count", [0, 3, 9])
def test_missing_references_reach_engine(db, count):
    db.refs = db.refs[:count]
    snapshot = load(db)
    assert len(snapshot.references) == count
    result = evaluate_snapshot(snapshot)
    assert type(result) is Abstained and result.code is A.INSUFFICIENT_HISTORY


@pytest.mark.parametrize("kind,code", [("quality", A.INVALID_QUALITY), ("nan", A.INVALID_VALUE),
    ("infinity", A.INVALID_VALUE), ("unit", A.UNIT_MISMATCH), ("duplicate_time", A.DUPLICATE_OBSERVATION),
    ("duplicate_id", A.DUPLICATE_OBSERVATION), ("cadence", A.GAP_OR_CADENCE)])
def test_invalid_candidates_are_preserved_for_engine(db, kind, code):
    if kind == "quality": db.refs[0]["quality"] = "bad"
    elif kind == "nan": db.refs[0]["value"] = float("nan")
    elif kind == "infinity": db.refs[0]["value"] = float("inf")
    elif kind == "unit": db.chain[0]["unit"] = "K"
    elif kind == "duplicate_time": db.refs[0]["timestamp"] = db.refs[1]["timestamp"]
    elif kind == "duplicate_id": db.refs[0]["id"] = db.refs[1]["id"]
    else: db.refs[0]["timestamp"] += timedelta(microseconds=1)
    snapshot = load(db)
    assert len(snapshot.references) == 10
    if kind == "quality": assert snapshot.references[0].quality == "bad"
    result = evaluate_snapshot(snapshot)
    assert type(result) is Abstained and result.code is code


def test_cutoff_caps_query_even_for_future_target(db):
    cutoff = db.target[0]["timestamp"]-timedelta(hours=12)
    snapshot = load(db, event_cutoff=cutoff)
    assert db.queries[-1][1]["timestamp_2"] == cutoff
    result = evaluate_snapshot(snapshot)
    assert type(result) is Abstained and result.code is A.TARGET_AFTER_CUTOFF


@pytest.mark.parametrize("delta", [timedelta(seconds=1), -timedelta(days=11)])
def test_out_of_window_sql_result_is_rejected_not_dropped(db, delta):
    db.refs[0]["timestamp"] = db.target[0]["timestamp"]+delta
    refused(db, loader.LoadCode.INCOHERENT_ROWS)


def test_other_measurement_at_target_time_is_retained(db):
    db.refs.append(dict(db.target[0], id=12))
    snapshot = load(db)
    assert len(snapshot.references) == 11
    result = evaluate_snapshot(snapshot)
    assert type(result) is Abstained and result.code is A.DUPLICATE_OBSERVATION


def test_limit_is_refusal_not_successful_truncation(db):
    db.refs = db.refs*4
    refused(db, loader.LoadCode.CANDIDATE_LIMIT)


@pytest.mark.parametrize("fault", ["autobegin", "session_inactive", "no_session_tx", "session_nested", "autoflush",
    "pending", "dirty", "deleted", "savepoint_mode", "engine_bind", "multiple_binds", "wrong_dialect",
    "closed", "invalidated", "no_physical_tx", "physical_nested", "read_committed", "read_write", "server_mismatch", "schema_redirect"])
def test_transaction_contract_fails_closed(db, fault):
    if fault == "autobegin": db.session.get_transaction.return_value.origin = SessionTransactionOrigin.AUTOBEGIN
    elif fault == "session_inactive": db.session.is_active = False
    elif fault == "no_session_tx": db.session.in_transaction.return_value = False
    elif fault == "session_nested": db.session.in_nested_transaction.return_value = True
    elif fault == "autoflush": db.session.autoflush = True
    elif fault == "pending": db.session.new = {object()}
    elif fault == "dirty": db.session.dirty = {object()}
    elif fault == "deleted": db.session.deleted = {object()}
    elif fault == "savepoint_mode": db.session.join_transaction_mode = "create_savepoint"
    elif fault == "engine_bind": db.session.get_bind.return_value = Mock(spec=Engine)
    elif fault == "multiple_binds": db.session.get_bind.side_effect = lambda **kwargs: object() if kwargs else db.connection
    elif fault == "wrong_dialect": db.connection.dialect.name = "sqlite"
    elif fault == "closed": db.connection.closed = True
    elif fault == "invalidated": db.connection.invalidated = True
    elif fault == "no_physical_tx": db.connection.in_transaction.return_value = False
    elif fault == "physical_nested": db.connection.in_nested_transaction.return_value = True
    elif fault == "read_committed": db.connection.get_isolation_level.return_value = "READ COMMITTED"
    elif fault == "read_write": db.proofs[0] = dict(isolation="repeatable read", read_only="off")
    elif fault == "server_mismatch": db.proofs[0] = dict(isolation="read committed", read_only="on")
    else: db.connection.get_execution_options.return_value = {"schema_translate_map": {"public": "other"}}
    refused(db, loader.LoadCode.SESSION_CONTRACT)
    assert not db.queries


@pytest.mark.parametrize("fault", ["session", "physical", "server"])
def test_transaction_changes_during_load_are_refused(db, fault):
    if fault == "session":
        tx = db.session.get_transaction.return_value
        db.session.get_transaction.side_effect = [tx, SimpleNamespace(is_active=True, origin=SessionTransactionOrigin.BEGIN)]
    elif fault == "physical":
        tx = db.connection.get_transaction.return_value
        db.connection.get_transaction.side_effect = [tx, SimpleNamespace(is_active=True)]
    else: db.proofs[-1] = dict(isolation="repeatable read", read_only="off")
    refused(db, loader.LoadCode.SESSION_CONTRACT)
    assert len(db.queries) == 3


def test_serializable_is_explicitly_supported(db):
    db.connection.get_isolation_level.return_value = "SERIALIZABLE"
    db.proofs = [dict(isolation="serializable", read_only="on")]*2
    assert type(evaluate_snapshot(load(db))) is Computed


@pytest.mark.parametrize("session", [None, object(), {}])
def test_non_session_refused(db, session):
    db.session = session
    refused(db, loader.LoadCode.SESSION_CONTRACT)


def test_engine_still_rejects_invalid_provenance_contents(db):
    snapshot = load(db, provenance=DeclaredProvenance("", "review", True))
    assert type(evaluate_snapshot(snapshot)) is Rejected


def test_driver_errors_are_sanitized_without_lifecycle_calls(db):
    db.connection.execute.side_effect = RuntimeError(PRIVATE)
    refused(db, loader.LoadCode.UNAVAILABLE)
    db.connection.rollback.assert_not_called()
    db.connection.close.assert_not_called()


def test_invalid_request_time_never_opens_transaction(db):
    refused(db, loader.LoadCode.INVALID_REQUEST, event_cutoff=db.arguments["event_cutoff"].replace(tzinfo=None))
    db.connection.execute.assert_not_called()


def test_nested_driver_failure_has_closed_code_and_no_sensitive_context(db):
    import traceback
    db.connection.execute.side_effect = loader.SnapshotLoadError(PRIVATE)
    try:
        raise RuntimeError(PRIVATE)
    except RuntimeError:
        with pytest.raises(loader.SnapshotLoadError) as caught: load(db)
    assert caught.value.code is loader.LoadCode.UNAVAILABLE
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert PRIVATE not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("configuration", ["direct", "engine_inherited", "misleading_isolation"])
def test_effective_autocommit_refuses_before_any_sql(db, configuration):
    db.driver.autocommit = True
    if configuration == "direct":
        db.connection.get_execution_options.return_value = {"isolation_level": "AUTOCOMMIT"}
    elif configuration == "engine_inherited":
        db.connection.engine = SimpleNamespace(dialect=SimpleNamespace(_on_connect_isolation_level="AUTOCOMMIT"))
        assert db.connection.get_execution_options() == {}
    else:
        db.connection.get_execution_options.return_value = {"isolation_level": "REPEATABLE READ"}
    # Logical transaction, isolation and server-proof fixtures still look valid.
    refused(db, loader.LoadCode.SESSION_CONTRACT)
    db.connection.execute.assert_not_called()
    db.connection.get_isolation_level.assert_not_called()
    assert not db.queries and db.driver.autocommit is True


@pytest.mark.parametrize("signal", [None, 0, 1, "false", Mock()])
def test_ambiguous_autocommit_signal_fails_closed(db, signal):
    db.driver.autocommit = signal
    refused(db, loader.LoadCode.SESSION_CONTRACT)
    db.connection.execute.assert_not_called()
    db.connection.get_isolation_level.assert_not_called()


@pytest.mark.parametrize("signal", ["missing", "unreadable"])
def test_unavailable_autocommit_signal_fails_closed(db, monkeypatch, signal):
    if signal == "missing": del db.driver.autocommit
    else:
        monkeypatch.setattr(type(db.driver), "autocommit", PropertyMock(side_effect=RuntimeError(PRIVATE)), raising=False)
    refused(db, loader.LoadCode.SESSION_CONTRACT)
    db.connection.execute.assert_not_called()


@pytest.mark.parametrize("status", [TransactionStatus.IDLE, TransactionStatus.ACTIVE,
    TransactionStatus.INERROR, TransactionStatus.UNKNOWN, 2, None])
def test_native_transaction_required_before_isolation_inspection(db, status):
    db.driver.info.transaction_status = status
    refused(db, loader.LoadCode.SESSION_CONTRACT)
    db.connection.get_isolation_level.assert_not_called()
    db.connection.execute.assert_not_called()
    db.driver.rollback.assert_not_called()


@pytest.mark.parametrize("fault", ["wrong_driver", "async", "closed", "broken", "wrong_native_type", "proxy_mismatch"])
def test_only_synchronous_same_connection_psycopg_signal_is_admitted(db, fault):
    if fault == "wrong_driver": db.connection.dialect.driver = "psycopg2"
    elif fault == "async": db.connection.dialect.is_async = True
    elif fault == "closed": db.driver.closed = True
    elif fault == "broken": db.driver.broken = True
    elif fault == "wrong_native_type":
        fake = SimpleNamespace(autocommit=False, closed=False, broken=False,
                               info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS))
        db.connection.connection = SimpleNamespace(driver_connection=fake, dbapi_connection=fake)
    else: db.connection.connection.dbapi_connection = object()
    refused(db, loader.LoadCode.SESSION_CONTRACT)
    db.connection.execute.assert_not_called()


@pytest.mark.parametrize("fault", ["autocommit", "native_replaced"])
def test_native_connection_or_mode_change_discards_snapshot(db, fault):
    execute = db.connection.execute.side_effect
    def changed(statement):
        result = execute(statement)
        if len(db.queries) == 3:
            if fault == "autocommit": db.driver.autocommit = True
            else:
                replacement = Mock(spec=psycopg.Connection)
                replacement.closed = replacement.broken = replacement.autocommit = False
                replacement.info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)
                db.connection.connection = SimpleNamespace(driver_connection=replacement, dbapi_connection=replacement)
        return result
    db.connection.execute.side_effect = changed
    refused(db, loader.LoadCode.SESSION_CONTRACT)
    assert len(db.queries) == 3


def retime(db, target, *, cutoff=None, zone=timezone.utc):
    """Create daily references in absolute UTC time, then vary representations."""
    instant = target.astimezone(timezone.utc)
    db.target[0]["timestamp"] = target
    for i, row in enumerate(db.refs):
        row["timestamp"] = (instant-timedelta(days=10-i)).astimezone(zone)
    db.arguments["event_cutoff"] = target if cutoff is None else cutoff
    db.arguments["observed_at"] = (instant+timedelta(days=5)).astimezone(zone)


@pytest.mark.parametrize("target", [datetime(2026, 4, 1, 10, 15, 2, 123456, tzinfo=timezone.utc),
    datetime(2026, 10, 28, 10, 15, 2, 123456, tzinfo=timezone.utc)])
def test_dst_window_is_ten_absolute_days_not_local_days(db, target):
    paris = ZoneInfo("Europe/Paris")
    retime(db, target.astimezone(paris), zone=paris)
    before = deepcopy((db.target, db.refs, db.arguments))
    snapshot = load(db)
    bounds = db.queries[-1][1]
    assert bounds["timestamp_1"] == target-timedelta(seconds=10*86400)
    assert bounds["timestamp_2"] == target
    assert bounds["timestamp_1"].tzinfo is bounds["timestamp_2"].tzinfo is timezone.utc
    assert (snapshot.target.timestamp-snapshot.references[0].timestamp).total_seconds() == 10*86400
    assert all(row.timestamp.microsecond == 123456 and row.timestamp.tzinfo is timezone.utc
               for row in (snapshot.target, *snapshot.references))
    assert (db.target, db.refs, db.arguments) == before
    assert type(evaluate_snapshot(snapshot)) is Computed


@pytest.mark.parametrize("target_fold", [0, 1])
def test_ambiguous_fold_cutoff_compares_instants(db, target_fold):
    paris = ZoneInfo("Europe/Paris")
    target = datetime(2026, 10, 25, 2, 45 if target_fold == 0 else 30, 2, 123456,
                      tzinfo=paris, fold=target_fold)
    cutoff = datetime(2026, 10, 25, 2, 30 if target_fold == 0 else 45, 2, 123456,
                      tzinfo=paris, fold=1-target_fold)
    retime(db, target, cutoff=cutoff, zone=paris)
    snapshot = load(db)
    target_utc, cutoff_utc = target.astimezone(timezone.utc), cutoff.astimezone(timezone.utc)
    assert db.queries[-1][1]["timestamp_2"] == min(target_utc, cutoff_utc)
    assert snapshot.event_cutoff == cutoff_utc and snapshot.target.timestamp == target_utc
    result = evaluate_snapshot(snapshot)
    if target_fold == 0: assert type(result) is Computed
    else: assert type(result) is Abstained and result.code is A.TARGET_AFTER_CUTOFF


def test_fold_reference_after_absolute_cutoff_is_not_admitted(db):
    paris = ZoneInfo("Europe/Paris")
    target = datetime(2026, 10, 25, 3, 0, 0, 123456, tzinfo=paris)
    cutoff = datetime(2026, 10, 25, 2, 45, 0, 123456, tzinfo=paris, fold=0)
    retime(db, target, cutoff=cutoff, zone=paris)
    # Locally 02:30 < 02:45, but fold=1 is later in absolute time.
    db.refs[0]["timestamp"] = datetime(2026, 10, 25, 2, 30, 0, 123456, tzinfo=paris, fold=1)
    refused(db, loader.LoadCode.INCOHERENT_ROWS)


@pytest.mark.parametrize("boundary", ["lower", "target", "cutoff"])
def test_inclusive_boundaries_preserve_other_measurement_ids(db, boundary):
    target = db.target[0]["timestamp"]
    cutoff = target-timedelta(hours=12) if boundary == "cutoff" else target
    instant = target-timedelta(seconds=10*86400) if boundary == "lower" else cutoff
    index = 0 if boundary == "lower" else -1
    db.refs[index]["timestamp"] = instant.astimezone(timezone(timedelta(hours=-4)))
    snapshot = load(db, event_cutoff=cutoff.astimezone(timezone(timedelta(hours=9))))
    assert snapshot.references[index].timestamp == instant
    assert snapshot.references[index].timestamp.tzinfo is timezone.utc
    assert snapshot.references[index].id == db.refs[index]["id"]
    result = evaluate_snapshot(snapshot)
    if boundary == "lower": assert type(result) is Computed
    else:
        assert type(result) is Abstained
        assert result.code is (A.TARGET_AFTER_CUTOFF if boundary == "cutoff" else A.DUPLICATE_OBSERVATION)


@pytest.mark.parametrize("boundary", ["lower", "upper"])
def test_one_microsecond_outside_utc_bounds_refuses(db, boundary):
    target = db.target[0]["timestamp"]
    instant = target-timedelta(seconds=10*86400, microseconds=1) if boundary == "lower" else target+timedelta(microseconds=1)
    db.refs[0]["timestamp"] = instant.astimezone(ZoneInfo("Europe/Paris"))
    refused(db, loader.LoadCode.INCOHERENT_ROWS)


def test_offset_representations_produce_identical_snapshot_and_result(db):
    original = load(db)
    db.proofs = [dict(isolation="repeatable read", read_only="on")]*2
    target = db.target[0]["timestamp"]
    retime(db, target.astimezone(timezone(timedelta(hours=9))),
           cutoff=target.astimezone(timezone(timedelta(hours=-4))), zone=ZoneInfo("Europe/Paris"))
    normalized = load(db)
    assert normalized == original
    assert evaluate_snapshot(normalized) == evaluate_snapshot(original)
    assert normalized.observed_at.tzinfo is normalized.event_cutoff.tzinfo is timezone.utc
