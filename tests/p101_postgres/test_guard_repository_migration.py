"""Catalog snapshots are fabricated; SQL is compiled/text-inspected, never run."""

import ast
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.p101_postgres.ddl import FUNCTIONS, function_ddl
from app.p101_postgres.guard import REQUIRED_TRUE, check_destination, validate_identity
from app.p101_postgres.repository import P101Repository, reservation_statement
from app.p101_postgres.runtime import GuardRejected, ContentConflict
from app.p101_postgres.tables import registry, predictions
from app.p101_postgres.mapping import map_prediction, validate_sources
from p101_postgres.conftest import NOW


def identity(config):
    return dict(server_address=config.server_address, server_port=config.server_port,
        database=config.destination.database, session_role=config.destination.role,
        effective_role=config.destination.role, instance_uuid=config.destination.instance_uuid,
        purpose="p101-ml-sandbox", owner_role=config.owner_role, writer_role=config.destination.role,
        reader_role=config.reader_role, core_revision="09ac8101e9fe", p101_revision="p101_0001",
        core_installed="09ac8101e9fe", p101_installed="p101_0001", isolation_level="read committed",
        marker_owner=config.owner_role, **{key: True for key in REQUIRED_TRUE})


class Rows:
    def __init__(self, rows=(), scalar=None): self.rows, self.scalar = rows, scalar
    def mappings(self): return self
    def one(self): return self.rows[0]
    def one_or_none(self): return self.rows[0] if self.rows else None
    def __iter__(self): return iter(self.rows)
    def scalar_one_or_none(self): return self.scalar


def catalog(config):
    constraints = []
    for name, kind in {"p101_registry_pk": "p", "p101_prediction_unique": "u", "p101_prediction_fk": "f",
        "p101_key_hex": "c", "p101_content_hex": "c", "p101_key_size": "c", "p101_content_size": "c"}.items():
        deferred = kind == "f"
        constraints.append(dict(conname=name, contype=kind, condeferrable=deferred, condeferred=deferred,
                                convalidated=True, registry_table=True, reference_target=True))
    functions = [dict(proname=name, owner=config.owner_role, prosecdef=True,
        proconfig=["search_path=pg_catalog"], body_sha256=hashlib.sha256(values[2].encode()).hexdigest(),
        executable=name == "lock_sources", public_execute=False) for name, values in FUNCTIONS.items()]
    triggers = []
    for name in ("p101_shape", "p101_prediction_link", "p101_registry_link"):
        deferred = name != "p101_shape"
        sandbox = name == "p101_registry_link"
        triggers.append(dict(tgname=name, tgenabled="O", deferred_capable=deferred, initially_deferred=deferred,
            table_schema="p101_pilot" if sandbox else "public",
            table_name="idempotency_records" if sandbox else "prediction_records",
            function_name="enforce_link" if deferred else "enforce_shape", function_schema="p101_pilot"))
    return [[identity(config)], functions, constraints, triggers]


class CatalogSession:
    def __init__(self, rows): self.rows, self.statements = iter(rows), []
    def execute(self, statement):
        self.statements.append(str(statement))
        return Rows(next(self.rows))


def test_complete_simulated_guard_snapshot(config):
    session = CatalogSession(catalog(config))
    check_destination(session, config)
    assert len(session.statements) == 4
    assert all(statement.lstrip().startswith("SELECT") for statement in session.statements)
    # Host published port differs from server internal port, legitimately.
    assert config.destination.port != config.server_port


@pytest.mark.parametrize("field,value", [("database", "industrial_predict_dev"), ("server_address", "wrong"),
    ("server_port", 5555), ("session_role", "other"), ("effective_role", "other"),
    ("instance_uuid", "other"), ("ssl", False), ("core_installed", None),
    ("p101_installed", None), ("limited_role", False), ("no_column_writes", False),
    ("provisioning_closed", False), ("no_memberships", False), ("no_ddl", 1)])
def test_effective_identity_fail_closed(config, field, value):
    row = identity(config)
    row[field] = value
    with pytest.raises(GuardRejected): validate_identity(config, row)


@pytest.mark.parametrize("kind", ["missing_function", "public_execute", "hash", "constraint", "fk_target", "trigger", "wrong_function"])
def test_catalog_protections_fail_closed(config, kind):
    data = catalog(config)
    if kind == "missing_function": data[1].pop()
    elif kind == "public_execute": data[1][0]["public_execute"] = True
    elif kind == "hash": data[1][0]["body_sha256"] = "0"*64
    elif kind == "constraint": data[2][0]["condeferrable"] = True
    elif kind == "fk_target": data[2][2]["reference_target"] = False
    elif kind == "trigger": data[3][1]["tgenabled"] = "D"
    elif kind == "wrong_function": data[3][1]["function_name"] = "wrong"
    with pytest.raises(GuardRejected): check_destination(CatalogSession(data), config)


def test_postgresql_reservation_compilation_and_separate_select(dossier):
    target = dossier.targets[0]
    compiled = reservation_statement(target, 9001, NOW).compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "ON CONFLICT (idempotency_key) DO NOTHING" in sql and "RETURNING" in sql
    assert "DO UPDATE" not in sql and compiled.params["prediction_id"] == 9001
    class Fake:
        def __init__(self): self.statements = []
        def execute(self, statement):
            self.statements.append(str(statement))
            return Rows([{ "prediction_id": 888 }]) if len(self.statements) == 2 else Rows(scalar=None)
    session = Fake()
    new, row = P101Repository(session).reserve(target, 9001, NOW)
    assert new is False and row["prediction_id"] == 888
    assert len(session.statements) == 2 and session.statements[1].startswith("SELECT")


def test_metadata_and_migration_sources_only():
    root = Path(__file__).resolve().parents[2]
    model = ast.parse((root / "backend/app/models/prediction_record.py").read_text(encoding="utf-8"))
    model_class = next(n for n in model.body if isinstance(n, ast.ClassDef) and n.name == "PredictionRecord")
    original_fields = {n.target.id for n in model_class.body if isinstance(n, ast.AnnAssign)}
    assert set(predictions.c.keys()) == original_fields and len(original_fields) == 14
    assert predictions.c.predicted_at.type.timezone and predictions.c.created_at.type.timezone
    ddl = str(CreateTable(registry).compile(dialect=postgresql.dialect()))
    assert "DEFERRABLE INITIALLY DEFERRED" in ddl and "ON DELETE NO ACTION" in ddl
    assert "PRIMARY KEY (idempotency_key)" in ddl and "UNIQUE (prediction_id)" in ddl
    path = root / "backend/p101_migrations/versions/p101_0001_registry.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                   and isinstance(n.targets[0], ast.Name)}
    assert assignments["revision"] == "p101_0001" and assignments["down_revision"] is None
    for fragment in ("p101_prediction_fk", "p101_registry_pk", "DEFERRABLE INITIALLY DEFERRED",
                     "p101_prediction_link", "p101_registry_link", "ON DELETE NO ACTION",
                     "REVOKE ALL", "if count:", "retention procedure"):
        assert fragment in source
    assert "INSERT INTO" not in source and "DELETE FROM" not in source
    downgrade = source.split("def downgrade():", 1)[1]
    assert downgrade.index("REVOKE ALL ON public.prediction_records") < downgrade.index("DROP TRIGGER")
    for name in FUNCTIONS:
        definition = function_ddl(name)
        assert "SECURITY DEFINER SET search_path=pg_catalog" in definition
    assert "session_user" in FUNCTIONS["lock_sources"][2]
    assert "FOR SHARE" in FUNCTIONS["lock_sources"][2]
    assert "content_canonical::jsonb" in FUNCTIONS["enforce_link"][2]
    env = (root / "backend/p101_migrations/env.py").read_text(encoding="utf-8")
    ast.parse(env)
    assert 'version_table_schema="p101_pilot"' in env
    assert "p101_authorize_migration" in env and "create_engine" not in env
    assert "DATABASE_URL" not in env and "is_offline_mode" in env
    assert "sqlalchemy.url" not in (root / "backend/p101_migrations/alembic.ini").read_text()


def test_existing_repository_preserves_original_id_and_metadata(dossier, sources):
    mapping = validate_sources(dossier, sources)
    target = dossier.targets[0]
    original = map_prediction(dossier, target, mapping, 9001, NOW)
    ledger = dict(idempotency_key=target.key.projection.sha256,
                  key_canonical=target.key.projection.canonical_json,
                  content_sha256=target.content.sha256, content_canonical=target.content.canonical_json,
                  prediction_id=9001, first_created_at=NOW)
    details = target.read_plan.details.candidate
    details["run_id"] = "00000000-0000-4000-8000-000000000009"
    details["prepared_at"] = "2026-03-01T00:00:00.000000Z"
    retry = replace(target, read_plan=replace(target.read_plan,
        details=replace(target.read_plan.details, candidate_json=json.dumps(details))))
    class ReadSession:
        def execute(self, statement): return Rows([deepcopy(original)])
    repository = P101Repository(ReadSession())
    loaded = repository.existing(dossier, retry, mapping, ledger)
    assert loaded["id"] == original["id"] == 9001
    assert loaded["details"]["run_id"] == original["details"]["run_id"]
    assert loaded["created_at"] == original["created_at"]
    with pytest.raises(ContentConflict):
        repository.existing(dossier, retry, mapping, dict(ledger, content_canonical="{}"))
