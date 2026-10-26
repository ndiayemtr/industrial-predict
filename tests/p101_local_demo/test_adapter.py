"""SQL rows, transport and catalog are simulated; no real PostgreSQL or network."""

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import psycopg
import pytest
from sqlalchemy import URL
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.anomaly_detection.p101_contracts import Abstained, AbstentionCode, Computed
from app.p101_persistence.contracts import CALCULATION_REVISION
from app.p101_local_demo.contracts import (
    CUTOFFS, TARGETS, CalculationContext, ErrorCode, LocalDemoError, LocalDestination, PURPOSE, SqlRows,
)
from app.p101_local_demo.processing import process_rows, read_and_evaluate
from app.p101_local_demo.reader import IDENTITY_SQL, adapt_rows, read_rows, validate_transport


ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def no_real_database_or_network(monkeypatch):
    def forbidden(*a, **kw): raise AssertionError("Only pure/simulated SQL-to-ML tests are authorized")
    for cls, name in ((Engine, "connect"), (Engine, "raw_connection"), (Connection, "execute"),
                      (Connection, "exec_driver_sql"), (Session, "execute"), (Session, "commit"), (Session, "flush")):
        monkeypatch.setattr(cls, name, forbidden)
    monkeypatch.setattr(psycopg, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    for key in list(os.environ):
        if key.startswith("PG"): monkeypatch.delenv(key)


@pytest.fixture
def reference():
    return json.loads((ROOT / "tests/p101_anomaly/fixtures/p101-temperature-v1.json").read_text(encoding="utf-8"))


@pytest.fixture
def rows(reference):
    return SqlRows(
        ({"id": 101, "code": "MLDEMO-COMP-P101"},),
        ({"id": 202, "code": "MLDEMO-SITE-P101", "company_id": 101},),
        ({"id": 303, "code": "MLDEMO-EQ-P101", "site_id": 202, "equipment_type": "pump",
          "name": "Pompe P101 synthétique", "status": "operational", "criticality": "medium"},),
        ({"id": 404, "code": "MLDEMO-SEN-P101-TEMP", "equipment_id": 303,
          "sensor_type": "temperature", "unit": "°C", "status": "active"},),
        tuple(dict(id=500 + i, sensor_id=404,
                   timestamp=datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")),
                   value=float(r["value"]), quality=r["quality"])
              for i, r in enumerate(reference["observations"], 1)))


@pytest.fixture
def context():
    return CalculationContext("00000000-0000-4000-8000-000000000001", "2026-02-01T00:00:00Z",
                              CALCULATION_REVISION, CUTOFFS)


@pytest.fixture
def destination():
    return LocalDestination("127.0.0.1", 55432, "industrial_predict_p101_local_demo", "p101_local_reader",
                            "127.0.0.2", 5432, "00000000-0000-4000-8000-000000000002", "p101_local_0001")


def identity(config):
    return dict(database=config.database, database_name=config.database, purpose=PURPOSE,
        session_role=config.role, effective_role=config.role, server_address=config.server_address,
        server_port=config.server_port, instance_uuid=config.instance_uuid,
        bootstrap_closed=True, schema_revision=config.schema_revision, installed_revision=config.schema_revision,
        no_protected_schema=True, limited_role=True, no_memberships=True, not_owner=True,
        source_read=True, sources_immutable=True, isolation_level="read committed", encoding="UTF8")


class ResultRows:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def one(self):
        assert len(self.rows) == 1
        return self.rows[0]
    def __iter__(self): return iter(self.rows)


class FakeConnection:
    def __init__(self, config, rows, *, identity_row=None):
        self.engine = SimpleNamespace(url=URL.create("postgresql+psycopg", username=config.role,
            host=config.host, port=config.port, database=config.database))
        info = SimpleNamespace(host=config.host, port=config.port, dbname=config.database,
            user=config.role, get_parameters=lambda: {"sslmode": "disable"})
        self.driver = SimpleNamespace(info=info, pgconn=SimpleNamespace(ssl_in_use=False))
        self.connection = SimpleNamespace(driver_connection=self.driver)
        self.in_transaction = lambda: True
        self.queue = iter(([(identity_row or identity(config))], rows.companies, rows.sites,
                           rows.equipments, rows.sensors, rows.measurements))
        self.statements = []

    def execute(self, statement):
        self.statements.append(statement)
        sql = str(statement.compile(dialect=postgresql.dialect()))
        assert sql.lstrip().startswith("SELECT")
        return ResultRows(next(self.queue))


def test_nominal_from_simulated_sql_through_real_ml3(destination, rows, reference, context):
    before = deepcopy((rows, reference, context))
    connection = FakeConnection(destination, rows)
    pair = read_and_evaluate(connection, destination, reference, context)
    assert len(connection.statements) == 6
    assert all(type(r) is Computed for r in pair.results)
    assert [r.prediction.measurement_fixture_id for r in pair.results] == list(TARGETS)
    assert [r.prediction.score for r in pair.results] == [0, 1]
    assert [r.prediction.is_alert for r in pair.results] == [False, True]
    assert [r.prediction.details["target"]["value"] for r in pair.results] == [65.0, 70.0]
    assert pair.results[0].reference_ids == tuple(f"DEMO-M-{i:03d}" for i in range(1, 11))
    assert pair.results[1].reference_ids == tuple(f"DEMO-M-{i:03d}" for i in range(2, 12))
    assert all(r.statistics.mean == 65 and r.statistics.sample_std == 1 and r.statistics.threshold == 3 for r in pair.results)
    assert pair.identities.measurements[-2:] == (("DEMO-M-011", 511), ("DEMO-M-012", 512))
    assert (rows, reference, context) == before


def test_sql_value_types_reach_evaluate_and_outputs_are_untouched(rows, reference, context, monkeypatch):
    import app.p101_local_demo.processing as module
    original = module.evaluate
    returned, before = [], []
    def spy(manifest, *args, **kwargs):
        assert all(type(r["value"]) is float for r in manifest["observations"])
        result = original(manifest, *args, **kwargs)
        returned.append(result)
        before.append(deepcopy(result))
        return result
    monkeypatch.setattr(module, "evaluate", spy)
    pair = module.process_rows(rows, reference, context)
    assert all(r is expected for r, expected in zip(pair.results, returned))
    assert returned == before
    pair.results[0].prediction.details["statistics"]["mean"] = 999
    assert returned == before
    with pytest.raises(FrozenInstanceError): pair.results[0].prediction.score = 1


@pytest.mark.parametrize("kind", ["missing", "extra", "quality", "unit", "value", "duplicate_time",
    "duplicate_id", "equipment_code", "sensor_code", "parent", "sensor_parent", "measurement_sensor",
    "naive_time", "wrong_date", "nan", "infinite", "bool_value", "string_value", "null_value",
    "bool_id", "equipment_status", "missing_parent", "duplicate_parent", "missing_field"])
def test_bad_sql_rows_rejected_before_any_calculation(rows, reference, context, kind, monkeypatch):
    data = deepcopy(rows)
    measures = list(data.measurements)
    if kind == "missing": measures.pop()
    elif kind == "extra": measures.append(deepcopy(measures[-1]))
    elif kind == "quality": measures[0]["quality"] = "bad"
    elif kind == "unit": data.sensors[0]["unit"] = "K"
    elif kind == "value": measures[0]["value"] = 99.0
    elif kind == "duplicate_time": measures[-1]["timestamp"] = measures[0]["timestamp"]
    elif kind == "duplicate_id": measures[-1]["id"] = measures[0]["id"]
    elif kind == "equipment_code": data.equipments[0]["code"] = "OTHER"
    elif kind == "sensor_code": data.sensors[0]["code"] = "OTHER"
    elif kind == "parent": data.sites[0]["company_id"] = 999
    elif kind == "sensor_parent": data.sensors[0]["equipment_id"] = 999
    elif kind == "measurement_sensor": measures[0]["sensor_id"] = 999
    elif kind == "naive_time": measures[0]["timestamp"] = datetime(2026, 1, 1, 8)
    elif kind == "wrong_date": measures[0]["timestamp"] = "2026-01-01T09:00:00Z"
    elif kind in ("nan", "infinite"): measures[0]["value"] = float("nan" if kind == "nan" else "inf")
    elif kind == "bool_value": measures[0]["value"] = True
    elif kind == "string_value": measures[0]["value"] = "65"
    elif kind == "null_value": measures[0]["value"] = None
    elif kind == "bool_id": measures[0]["id"] = True
    elif kind == "equipment_status": data.equipments[0]["status"] = "active"
    elif kind == "missing_parent": data = replace(data, companies=())
    elif kind == "duplicate_parent": data = replace(data, sensors=data.sensors * 2)
    elif kind == "missing_field": measures[0].pop("quality")
    data = replace(data, measurements=tuple(measures))
    calls = []
    monkeypatch.setattr("app.p101_local_demo.processing.evaluate", lambda *a, **kw: calls.append(a))
    with pytest.raises(LocalDemoError): process_rows(data, reference, context)
    assert not calls


def test_reference_cannot_legitimize_modified_sql(rows, reference, context):
    reference["observations"][0]["value"] = 99.0
    rows.measurements[0]["value"] = 99.0
    with pytest.raises(LocalDemoError) as exc: process_rows(rows, reference, context)
    assert exc.value.code == ErrorCode.FIXTURE


def test_order_and_real_ids_are_not_assumed(rows, reference, context):
    changed = deepcopy(rows)
    for row in changed.measurements: row["id"] += 10000
    changed = replace(changed, measurements=tuple(reversed(changed.measurements)))
    pair = process_rows(changed, reference, context)
    assert pair.identities.measurements[0] == ("DEMO-M-001", 10501)
    assert [r.prediction.score for r in pair.results] == [0, 1]


@pytest.mark.parametrize("field,value", [("run_id", "invalid"), ("code_revision", "0" * 40),
    ("prepared_at", "2026-01-11T08:01:00Z"), ("prepared_at", "2026-02-01T00:00:00"),
    ("cutoffs", CUTOFFS[:1]), ("cutoffs", (CUTOFFS[1], CUTOFFS[0])),
    ("cutoffs", ("2026-01-11T08:00:00Z", CUTOFFS[1]))])
def test_bad_context(rows, reference, context, field, value):
    with pytest.raises(LocalDemoError) as exc: process_rows(rows, reference, replace(context, **{field: value}))
    assert exc.value.code == ErrorCode.CONTEXT


@pytest.mark.parametrize("code", list(AbstentionCode))
def test_every_ml3_abstention_rejects_the_whole_pair(rows, reference, context, code, monkeypatch):
    import app.p101_local_demo.processing as module
    original = module.evaluate
    def partial(manifest, target, **kwargs):
        if target == TARGETS[1]: return Abstained(code, target, CUTOFFS[1], (), "synthetic test")
        return original(manifest, target, **kwargs)
    monkeypatch.setattr(module, "evaluate", partial)
    with pytest.raises(LocalDemoError) as exc: module.process_rows(rows, reference, context)
    assert exc.value.code == ErrorCode.CALCULATION


@pytest.mark.parametrize("kind", ["none", "duplicate", "statistics", "references", "digest"])
def test_incomplete_or_incoherent_computed(rows, reference, context, kind, monkeypatch):
    import app.p101_local_demo.processing as module
    original = module.evaluate
    def changed(manifest, target, **kwargs):
        if kind == "none": return None
        if kind == "duplicate": target = TARGETS[0]
        result = original(manifest, target, **kwargs)
        if kind == "statistics": result = replace(result, statistics=replace(result.statistics, mean=99))
        if kind == "references": result = replace(result, reference_ids=())
        if kind == "digest": result = replace(result, dataset_sha256="0" * 64)
        return result
    monkeypatch.setattr(module, "evaluate", changed)
    with pytest.raises(LocalDemoError): module.process_rows(rows, reference, context)


@pytest.mark.parametrize("field,value", [("host", "localhost"), ("host", "remote.invalid"), ("port", 5434),
    ("database", "industrial_predict_dev"), ("database", "industrial_predict_ml_sandbox"),
    ("role", "p101_local_owner"), ("server_address", "unknown"), ("server_port", 55432),
    ("instance_uuid", "00000000-0000-0000-0000-000000000000"), ("schema_revision", "09ac8101e9fe")])
def test_bad_destination_refused_before_sql(destination, rows, field, value):
    connection = FakeConnection(destination, rows)
    with pytest.raises(LocalDemoError): read_rows(connection, replace(destination, **{field: value}))
    assert not connection.statements


@pytest.mark.parametrize("field,value", [("instance_uuid", "other"), ("purpose", "other"),
    ("database_name", "other"), ("bootstrap_closed", False), ("schema_revision", "other"),
    ("no_protected_schema", False), ("limited_role", False), ("sources_immutable", False),
    ("not_owner", False), ("server_address", "127.0.0.3"), ("server_port", 55432), ("source_read", 1)])
def test_bad_effective_identity_prevents_source_reads(destination, rows, field, value):
    row = identity(destination)
    row[field] = value
    connection = FakeConnection(destination, rows, identity_row=row)
    with pytest.raises(LocalDemoError): read_rows(connection, destination)
    assert connection.statements == [IDENTITY_SQL]


def test_no_implicit_configuration(destination, rows, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "unused-sentinel")
    read_rows(FakeConnection(destination, rows), destination)
    monkeypatch.setenv("PGSERVICE", "unused-sentinel")
    connection = FakeConnection(destination, rows)
    with pytest.raises(LocalDemoError): read_rows(connection, destination)
    assert not connection.statements


@pytest.mark.parametrize("kind", ["driver", "sslmode", "ssl", "transaction", "database"])
def test_bad_supplied_connection(destination, rows, kind):
    connection = FakeConnection(destination, rows)
    if kind == "driver": connection.engine.url = connection.engine.url.set(drivername="postgresql+other")
    elif kind == "sslmode": connection.driver.info.get_parameters = lambda: {"sslmode": "prefer"}
    elif kind == "ssl": connection.driver.pgconn.ssl_in_use = True
    elif kind == "transaction": connection.in_transaction = lambda: False
    elif kind == "database": connection.driver.info.dbname = "industrial_predict_dev"
    with pytest.raises(LocalDemoError): validate_transport(connection, destination)
    assert not connection.statements


def test_sql_is_bounded_select_only_and_does_not_hide_bad_rows(destination, rows):
    connection = FakeConnection(destination, rows)
    read_rows(connection, destination)
    statement = connection.statements[-1]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert sql.startswith("SELECT") and "public.measurements" in sql and "ORDER BY" in sql
    assert 13 in compiled.params.values()
    where = str(statement.whereclause)
    assert "sensor_id" in where and "quality" not in where and "timestamp" not in where
    assert all(2 in s.compile(dialect=postgresql.dialect()).params.values() for s in connection.statements[1:5])


def test_unexpected_errors_are_explicit_and_sanitized(destination, rows, reference, context, monkeypatch):
    def broken(*a, **kw): raise RuntimeError("unit-test-only sensitive-error-canary")
    connection = FakeConnection(destination, rows)
    connection.execute = broken
    with pytest.raises(LocalDemoError) as exc: read_rows(connection, destination)
    assert "canary" not in str(exc.value)
    monkeypatch.setattr("app.p101_local_demo.processing.evaluate", broken)
    with pytest.raises(LocalDemoError) as exc: process_rows(rows, reference, context)
    assert exc.value.code == ErrorCode.CALCULATION and "canary" not in str(exc.value)


def test_static_no_write_or_implicit_import_and_model_column_subsets():
    package = ROOT / "backend/app/p101_local_demo"
    forbidden = {"create_engine", "sessionmaker", "connect", "create_all", "insert", "update", "delete", "commit", "flush"}
    for path in package.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not node.module.startswith(("app.core", "app.models", "app.services", "app.p101_postgres"))
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else ""
                assert name not in forbidden
    from app.p101_local_demo import reader
    for name, table in (("company", reader.companies), ("site", reader.sites), ("equipment", reader.equipments),
                        ("sensor", reader.sensors), ("measurement", reader.measurements)):
        tree = ast.parse((ROOT / f"backend/app/models/{name}.py").read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
        columns = {n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)}
        assert set(table.c.keys()) <= columns and table.schema == "public"


def test_fresh_import_does_not_initialize_dev_or_network():
    script = '''
import builtins, io, socket, sys
import sqlalchemy, psycopg
def forbidden(*a, **kw): raise AssertionError("forbidden side effect")
sqlalchemy.create_engine = forbidden
psycopg.connect = forbidden
socket.socket.connect = forbidden
socket.create_connection = forbidden
socket.getaddrinfo = forbidden
original_import = builtins.__import__
def guarded_import(name, *a, **kw):
    if name.startswith(("app.core", "app.models", "app.services", "app.p101_postgres")): forbidden()
    return original_import(name, *a, **kw)
builtins.__import__ = guarded_import
original_open = io.open
def guarded_open(path, *a, **kw):
    if str(path).endswith(".env"): forbidden()
    return original_open(path, *a, **kw)
io.open = guarded_open
import app.p101_local_demo.reader, app.p101_local_demo.processing
assert "app.core.database" not in sys.modules
print("safe imports")
'''
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONPATH=str(ROOT / "backend"), DATABASE_URL="unused-sentinel")
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=ROOT, env=env,
                            capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "safe imports"
