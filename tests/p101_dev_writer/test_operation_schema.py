"""Metadata, AST and compiled SQL only; no migration import/execution or real PG."""

import ast
from dataclasses import replace
from hashlib import sha256
import json
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint, UniqueConstraint, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from sqlalchemy.schema import AddConstraint, CreateTable

from app import general_migrations as guards
from app.models.p101_prediction_operation import P101PredictionOperation
from app.models.prediction_record import PredictionRecord
from app.services.p101_dev_orchestration import PersistenceState
from core.test_application_session_migration import operations
from core.test_general_migrations import (
    NOW, declaration, destination, intent, no_database_or_migration_commands,
)
from p101_dev_orchestration.test_orchestration import scenario
from p101_dev_sql.test_loader import db, no_live_database


PATH = guards.GENERAL_DIRECTORY / "versions/p101_0001_operations.py"
TABLE = P101PredictionOperation.__table__


def sql_statements():
    return [args[0] for kind, args, options in operations(PATH) if kind == "execute"]


def test_complete_table_declaration_matches_independent_orm_metadata():
    ops = operations(PATH)
    kind, args, options = ops[2]
    assert kind == "create_table" and args[0] == TABLE.name and options == {"schema": "public"}
    items = args[1:]
    expected_columns = []
    for column in TABLE.columns:
        if column.type.__class__.__name__ == "DateTime":
            type_spec = ("DateTime", (), {"timezone": True})
        elif column.type.__class__.__name__ == "Boolean":
            type_spec = ("Boolean", (), {})
        elif hasattr(column.type, "length"):
            type_spec = (column.type.__class__.__name__, (column.type.length,) if column.type.length else (), {})
        else:
            type_spec = ("Integer", (), {})
        column_options = {"nullable": False}
        if column.name == "id": column_options["autoincrement"] = "ignore_fk"
        expected_columns.append(("Column", (column.name, type_spec), column_options))
    assert [item for item in items if item[0] == "Column"] == expected_columns
    expected = []
    for constraint in TABLE.constraints:
        if isinstance(constraint, CheckConstraint):
            expected.append(("CheckConstraint", (str(constraint.sqltext),), {"name": constraint.name}))
        elif isinstance(constraint, PrimaryKeyConstraint):
            expected.append(("PrimaryKeyConstraint", tuple(constraint.columns.keys()), {}))
        elif isinstance(constraint, UniqueConstraint):
            expected.append(("UniqueConstraint", tuple(constraint.columns.keys()), {"name": constraint.name}))
        elif isinstance(constraint, ForeignKeyConstraint):
            expected.append(("ForeignKeyConstraint", (tuple(constraint.column_keys),
                tuple("public."+element.target_fullname for element in constraint.elements)),
                dict(name=constraint.name, ondelete="RESTRICT", onupdate="RESTRICT", deferrable=True, initially="DEFERRED")))
        else:
            pytest.fail("Unexpected journal constraint")
    assert sorted(map(repr, [item for item in items if item[0] != "Column"])) == sorted(map(repr, expected))
    assert all(column.default is None and column.server_default is None for column in TABLE.columns)
    assert [kind for kind, args, opts in ops] == ["add_column", "create_unique_constraint", "create_table", "create_foreign_key"] + ["execute"]*7
    assert not {"cookie", "session_secret", "email", "role", "permission"} & set(TABLE.columns.keys())


def test_unique_keys_and_deferred_prediction_obligation():
    unique = {tuple(c.columns.keys()) for c in TABLE.constraints if isinstance(c, UniqueConstraint)}
    assert unique == {("idempotency_key",), ("prediction_id",), ("id", "prediction_id"),
        ("company_id", "equipment_id", "sensor_id", "measurement_id", "model_name", "model_version")}
    foreign = next(c for c in TABLE.constraints if isinstance(c, ForeignKeyConstraint))
    assert foreign.referred_table is PredictionRecord.__table__
    ddl = str(CreateTable(TABLE).compile(dialect=postgresql.dialect()))
    assert "ON DELETE RESTRICT ON UPDATE RESTRICT DEFERRABLE INITIALLY DEFERRED" in ddl
    assert all(not column.nullable for column in TABLE.columns)
    # The technical id may vary; the operation identity is the business tuple.
    assert tuple(TABLE.primary_key.columns.keys()) == ("id",)
    assert "id SERIAL NOT NULL" in ddl
    assert not TABLE.c.idempotency_key.unique  # Named table-level UNIQUE, not an accidental implicit index.


def test_sql_key_definition_preserves_dev3a_serialization(scenario):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    result = plan.draft.computed
    serialized = json.dumps([result.asset.company_id, result.asset.equipment_id,
        result.asset.sensor_id, result.target.measurement_id, result.model_name, result.model_version], separators=(",", ":"))
    assert serialized == '[101,303,404,11,"statistical_deviation","p101-dev-stat-v1"]'
    assert plan.key == sha256(serialized.encode("utf-8")).hexdigest()
    checks = {c.name: str(c.sqltext) for c in TABLE.constraints if isinstance(c, CheckConstraint)}
    assert checks["ck_p101_operations_key"] == (
        "idempotency_key = encode(sha256(convert_to('[' || company_id::text || ',' || equipment_id::text || ',' || sensor_id::text || ',' || measurement_id::text || ',\"statistical_deviation\",\"p101-dev-stat-v1\"]', 'UTF8')), 'hex')")
    assert "model_version = 'p101-dev-stat-v1'" in checks["ck_p101_operations_model"]
    assert checks["ck_p101_operations_state"] == "state = 'recorded'"
    assert "IS TRUE" in checks["ck_p101_operations_payload"]  # Missing JSON members cannot pass via SQL NULL.
    assert "BETWEEN 1 AND 6000" in checks["ck_p101_operations_result"]
    assert "sha256(convert_to(result_details_json, 'UTF8'))" in checks["ck_p101_operations_result"]
    # Pure transient construction, not a writer or a successful SQL insertion.
    record = P101PredictionOperation(idempotency_key=plan.key, company_id=result.asset.company_id,
        site_id=result.asset.site_id, equipment_id=result.asset.equipment_id, sensor_id=result.asset.sensor_id,
        measurement_id=result.target.measurement_id, model_name=result.model_name, model_version=result.model_version,
        input_sha256=result.input_sha256, result_sha256=result.details_sha256, result_details_json=result.details_json,
        actor_user_id=plan.actor[0], actor_issuer=plan.actor[1], actor_subject=plan.actor[2], state="recorded",
        score=result.score, is_alert=result.is_alert,
        prediction_id=7, target_at=plan.snapshot.target.timestamp, prepared_at=plan.prepared_at, recorded_at=plan.prepared_at)
    assert inspect(record).transient and record.id is None
    assert json.loads(record.result_details_json) == plan.draft.values(created_at=plan.prepared_at)["details"]
    assert sha256(record.result_details_json.encode()).hexdigest() == record.result_sha256
    assert record.state not in {state.value for state in PersistenceState}


def test_deferred_coherence_checks_all_prediction_mapping_fields():
    sql = sql_statements()
    validate = next(statement for statement in sql if "CREATE FUNCTION public.p101_operation_validate()" in statement)
    for name in ("equipment_id", "sensor_id", "measurement_id", "model_name", "model_version", "score", "is_alert"):
        assert f"prediction.{name} IS DISTINCT FROM NEW.{name}" in validate
    for expected in (
        "WHERE id = NEW.prediction_id FOR SHARE", "IF NOT FOUND THEN",
        "prediction.p101_operation_id IS DISTINCT FROM NEW.id",
        "prediction.prediction_type IS DISTINCT FROM 'anomaly'",
        "prediction.predicted_at IS DISTINCT FROM NEW.target_at",
        "prediction.created_at IS DISTINCT FROM NEW.recorded_at",
        "prediction.score NOT IN (0, 1)", "prediction.is_alert IS DISTINCT FROM (prediction.score = 1)",
        "prediction.level IS NOT NULL OR prediction.horizon_hours IS NOT NULL",
        "prediction.details::jsonb IS DISTINCT FROM NEW.result_details_json::jsonb",
        "::timestamptz IS DISTINCT FROM NEW.target_at",
    ):
        assert expected in validate
    deferred = sql[-1]
    assert "CREATE CONSTRAINT TRIGGER" in deferred
    assert "AFTER INSERT ON public.p101_prediction_operations DEFERRABLE INITIALLY DEFERRED" in deferred
    assert all("SECURITY INVOKER SET search_path = pg_catalog, pg_temp" in statement
               for statement in sql if statement.startswith("CREATE FUNCTION"))


def test_retention_only_guards_linked_predictions_without_lookup_races():
    sql = "\n".join(sql_statements())
    assert "BEFORE UPDATE OR DELETE ON public.p101_prediction_operations" in sql
    assert "BEFORE TRUNCATE ON public.p101_prediction_operations" in sql
    assert "BEFORE UPDATE OR DELETE ON public.prediction_records" in sql
    predicate = next(s for s in sql_statements() if s.startswith("CREATE TRIGGER p101_predictions_no_mutation"))
    assert predicate == """CREATE TRIGGER p101_predictions_no_mutation
BEFORE UPDATE OR DELETE ON public.prediction_records
FOR EACH ROW WHEN (OLD.p101_operation_id IS NOT NULL)
EXECUTE FUNCTION public.p101_prediction_immutable()"""
    assert "model_name" not in predicate and "model_version" not in predicate
    immutable = next(s for s in sql_statements() if s.startswith("CREATE FUNCTION public.p101_prediction_immutable"))
    assert "SELECT" not in immutable and "RAISE EXCEPTION" in immutable
    assert "CASCADE" not in sql and "SECURITY DEFINER" not in sql
    assert "UPDATE public." not in sql and "DELETE FROM" not in sql
    tree = ast.parse(PATH.read_text(encoding="utf-8"))
    downgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
    assert len(downgrade.body) == 1 and isinstance(downgrade.body[0], ast.Raise)
    assert downgrade.body[0].exc.args[0].value == "P101_OPERATION_DOWNGRADE_REQUIRES_SEPARATE_APPROVAL"


def test_historical_predictions_get_nullable_marker_without_backfill_or_cascade_changes():
    table = PredictionRecord.__table__
    marker = table.c.p101_operation_id
    assert marker.nullable and marker.default is None and marker.server_default is None
    assert operations(PATH)[0] == ("add_column", ("prediction_records",
        ("Column", ("p101_operation_id", ("Integer", (), {})), {"nullable": True})), {"schema": "public"})
    assert operations(PATH)[1] == ("create_unique_constraint",
        ("uq_prediction_records_p101_pair", "prediction_records", ("id", "p101_operation_id")), {"schema": "public"})
    assert any(isinstance(c, UniqueConstraint) and tuple(c.columns.keys()) == ("id", "p101_operation_id")
               for c in table.constraints)
    assert "id SERIAL NOT NULL" in str(CreateTable(table).compile(dialect=postgresql.dialect()))
    for name in ("equipment_id", "sensor_id", "measurement_id"):
        foreign = next(iter(table.c[name].foreign_keys))
        assert foreign.ondelete == "CASCADE"
    # The sole prediction guard is a row trigger on OLD.marker, not a global
    # model predicate or statement trigger. NULL-marker UPDATE/DELETE and their
    # cascades do not satisfy that WHEN. Actual PostgreSQL behavior is untested.
    prediction_triggers = [s for s in sql_statements() if s.startswith("CREATE")
                           and "TRIGGER" in s and "ON public.prediction_records" in s]
    assert len(prediction_triggers) == 1 and "WHEN (OLD.p101_operation_id IS NOT NULL)" in prediction_triggers[0]


def test_bidirectional_composite_foreign_keys_and_installation_order():
    journal_fk = next(iter(TABLE.foreign_key_constraints))
    prediction_fk = next(c for c in PredictionRecord.__table__.foreign_key_constraints
                         if c.name == "fk_prediction_records_p101_operation")
    assert tuple(journal_fk.column_keys) == ("prediction_id", "id")
    assert tuple(e.target_fullname for e in journal_fk.elements) == (
        "prediction_records.id", "prediction_records.p101_operation_id")
    assert tuple(prediction_fk.column_keys) == ("p101_operation_id", "id")
    assert tuple(e.target_fullname for e in prediction_fk.elements) == (
        "p101_prediction_operations.id", "p101_prediction_operations.prediction_id")
    for constraint in (journal_fk, prediction_fk):
        assert constraint.deferrable is True and constraint.initially == "DEFERRED"
        assert constraint.ondelete == constraint.onupdate == "RESTRICT"
    assert prediction_fk.match == "SIMPLE" and prediction_fk.use_alter is True
    assert "MATCH SIMPLE ON DELETE RESTRICT ON UPDATE RESTRICT DEFERRABLE INITIALLY DEFERRED" in str(
        AddConstraint(prediction_fk).compile(dialect=postgresql.dialect()))
    assert operations(PATH)[3] == ("create_foreign_key", (
        "fk_prediction_records_p101_operation", "prediction_records", "p101_prediction_operations",
        ("p101_operation_id", "id"), ("id", "prediction_id")),
        dict(source_schema="public", referent_schema="public", ondelete="RESTRICT", onupdate="RESTRICT",
             deferrable=True, initially="DEFERRED", match="SIMPLE"))
    # All changes of association on a linked row (NULL, another id, same id,
    # different PK/content) encounter the same OLD-marker guard before UPDATE.
    guard = next(s for s in sql_statements() if s.startswith("CREATE TRIGGER p101_predictions_no_mutation"))
    assert "BEFORE UPDATE OR DELETE" in guard and "NEW." not in guard and "EXISTS" not in guard


def declared_pair_references_match(predictions, journals):
    """Inspect declared pair membership on synthetic rows; not a PostgreSQL emulator.

    This checks the schema's mathematical relation, not transaction visibility,
    row locking, triggers, uniqueness enforcement or commit behavior.
    """
    tables = {"prediction_records": predictions, TABLE.name: journals}
    constraints = [next(iter(TABLE.foreign_key_constraints)),
        next(c for c in PredictionRecord.__table__.foreign_key_constraints
             if c.name == "fk_prediction_records_p101_operation")]
    for constraint in constraints:
        for row in tables[constraint.table.name]:
            values = tuple(row[element.parent.name] for element in constraint.elements)
            if any(value is None for value in values):  # MATCH SIMPLE
                continue
            if not any(values == tuple(target[element.column.name] for element in constraint.elements)
                       for target in tables[constraint.referred_table.name]):
                return False
    return True


@pytest.mark.parametrize("predictions,journals,expected", [
    ([{"id": 1, "p101_operation_id": None}], [], True),
    ([{"id": 1, "p101_operation_id": 11}], [{"id": 11, "prediction_id": 1}], True),
    ([{"id": 1, "p101_operation_id": None}], [{"id": 11, "prediction_id": 1}], False),
    ([{"id": 1, "p101_operation_id": 11}], [], False),
    ([], [{"id": 11, "prediction_id": 1}], False),
    ([{"id": 1, "p101_operation_id": 11}], [{"id": 11, "prediction_id": 2}], False),
    ([{"id": 1, "p101_operation_id": 12}], [{"id": 11, "prediction_id": 1}], False),
    ([{"id": 1, "p101_operation_id": 11}], [{"id": 11, "prediction_id": 1}, {"id": 12, "prediction_id": 1}], False),
    ([{"id": 1, "p101_operation_id": 11}, {"id": 2, "p101_operation_id": 11}], [{"id": 11, "prediction_id": 1}], False),
    ([{"id": 1, "p101_operation_id": 12}, {"id": 2, "p101_operation_id": 11}],
     [{"id": 11, "prediction_id": 1}, {"id": 12, "prediction_id": 2}], False),
])
def test_declared_pairs_require_exact_reciprocal_association(predictions, journals, expected):
    assert declared_pair_references_match(predictions, journals) is expected


def test_insertion_plan_has_deferred_intermediate_and_coherent_final_pairs():
    journal = {"id": 11, "prediction_id": 7}
    prediction = {"id": 7, "p101_operation_id": 11}
    assert not declared_pair_references_match([], [journal])
    assert declared_pair_references_match([prediction], [journal])
    # IDs must be allocated explicitly; no relationship post_update or UPDATE
    # finalization is introduced. Historical rows remain NULL until explicitly linked.
    assert all(fk.deferrable and fk.initially == "DEFERRED" for fk in TABLE.foreign_key_constraints)


def test_exact_linear_publication_scope_and_inert_loading():
    published = guards.read_manifest()
    entry = published[-1]
    assert (entry.revision, entry.parent, entry.path, entry.schema_scope) == (
        guards.OPERATION_REVISION, guards.ANALYSIS_REVISION,
        "general_migrations/versions/p101_0001_operations.py", guards.OPERATION_SCOPE)
    source = PATH.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert sha256(source.encode()).hexdigest() == entry.sha256
    with patch("alembic.util.load_python_file") as importer:
        snapshot = guards.inspect_sources()
        assert guards.resolve_upgrade(snapshot.revisions, guards.HISTORICAL_HEAD, guards.OPERATION_REVISION) == (
            "12e2fc65f372", guards.ACCOUNT_REVISION, guards.SESSION_REVISION,
            guards.ANALYSIS_REVISION, guards.OPERATION_REVISION)
        guards.make_alembic_config()
        importer.assert_not_called()


@pytest.mark.parametrize("mutate", [
    lambda s: s + "\nraise RuntimeError('unapproved')\n",
    lambda s: s.replace('ondelete="RESTRICT"', 'ondelete="CASCADE"'),
    lambda s: s.replace("BEFORE UPDATE OR DELETE", "BEFORE DELETE"),
    lambda s: s.replace("DEFERRABLE INITIALLY DEFERRED", "NOT DEFERRABLE"),
    lambda s: s.replace("prediction.details::jsonb IS DISTINCT FROM", "prediction.details::jsonb ="),
    lambda s: s.replace("state = 'recorded'", "state IN ('recorded', 'commit_confirmed')"),
    lambda s: s.replace("OLD.p101_operation_id IS NOT NULL", "OLD.model_version = 'p101-dev-stat-v1'"),
    lambda s: s.replace('["prediction_id", "id"]', '["prediction_id"]', 1),
    lambda s: s.replace('match="SIMPLE"', 'match="FULL"', 1),
    lambda s: s.replace('schema="public"', 'schema="unreviewed"'),
    lambda s: s.replace('    op.create_table(', '    op.execute("SELECT 1")\n    op.create_table(', 1),
])
def test_manifest_rehash_cannot_approve_altered_journal_or_trigger(monkeypatch, mutate):
    read = guards._read
    original = read(PATH)
    altered = mutate(original)
    assert altered != original
    manifest = json.loads(read(guards.MANIFEST_PATH))
    manifest["revisions"][-1]["sha256"] = sha256(altered.encode()).hexdigest()
    def changed(path):
        if path == PATH: return altered
        if path == guards.MANIFEST_PATH: return json.dumps(manifest)
        return read(path)
    monkeypatch.setattr(guards, "_read", changed)
    with pytest.raises(guards.MigrationGuardError): guards.inspect_sources()


def test_journal_preflight_never_enables_migration_even_with_matching_claim(intent, declaration):
    snapshot = guards.inspect_sources()
    full = replace(intent, final_revision=guards.OPERATION_REVISION,
        sequence=guards.resolve_upgrade(snapshot.revisions, guards.HISTORICAL_HEAD, guards.OPERATION_REVISION))
    claim = replace(declaration, intent=full)
    report = guards.preflight(full, claim, now=NOW)
    assert report.sources_match and report.declaration_matches
    assert not report.authenticated and not report.execution_enabled
    connection = Mock(spec=Connection)
    with pytest.raises(guards.MigrationExecutionDisabled):
        guards.request_execution(full, claim, now=NOW, connection=connection)
    assert connection.mock_calls == []
