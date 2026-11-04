"""Static publication/DDL checks only; migration modules are never imported."""

import ast
import hashlib
import json

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app import general_migrations as guards
from app.models.application_session import ApplicationSessionRecord
from app.models.professional_account import ExternalIdentityRecord
from core.test_general_migrations import no_database_or_migration_commands


PATH = guards.GENERAL_DIRECTORY / "versions/b2b_0001_sessions.py"
TABLE = ApplicationSessionRecord.__table__


def literal(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.List):
        return tuple(literal(item) for item in node.elts)
    assert isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    return (node.func.attr, tuple(literal(item) for item in node.args),
            {key.arg: literal(key.value) for key in node.keywords})


def operations(path=PATH):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    upgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "upgrade")
    return [literal(statement.value) for statement in upgrade.body]


def test_complete_session_schema_matches_final_orm_without_execution():
    ops = operations()
    assert ops[0] == ("create_unique_constraint", ("uq_external_identities_id_user", "external_identities", ("id", "user_id")), {"schema": "public"})
    assert any(c.name == "uq_external_identities_id_user" and tuple(c.columns.keys()) == ("id", "user_id") for c in ExternalIdentityRecord.__table__.constraints)
    assert [op[0] for op in ops] == ["create_unique_constraint", "create_table", "create_index", "create_index"]
    _, args, options = ops[1]
    assert args[0] == "application_sessions" and options == {"schema": "public"}
    items = args[1:]
    actual_columns = [item for item in items if item[0] == "Column"]
    expected_columns = []
    for column in TABLE.columns:
        if column.type.__class__.__name__ == "DateTime":
            kind = ("DateTime", (), {"timezone": True})
        elif hasattr(column.type, "length"):
            kind = ("String", (column.type.length,), {})
        else:
            kind = ("Integer", (), {})
        expected_columns.append(("Column", (column.name, kind), {"nullable": column.nullable}))
    assert actual_columns == expected_columns
    expected = []
    for constraint in TABLE.constraints:
        if isinstance(constraint, CheckConstraint):
            expected.append(("CheckConstraint", (str(constraint.sqltext),), {"name": constraint.name}))
        elif isinstance(constraint, PrimaryKeyConstraint):
            expected.append(("PrimaryKeyConstraint", tuple(constraint.columns.keys()), {"name": constraint.name}))
        elif isinstance(constraint, ForeignKeyConstraint):
            expected.append(("ForeignKeyConstraint", (tuple(constraint.column_keys), tuple("public." + e.target_fullname for e in constraint.elements)), {"name": constraint.name, "ondelete": "RESTRICT"}))
        else:
            pytest.fail("Unexpected constraint")
    assert sorted(map(repr, [i for i in items if i[0] != "Column"])) == sorted(map(repr, expected))
    expected_indexes = {(index.name, TABLE.name, tuple(index.columns.keys())) for index in TABLE.indexes}
    assert {(args[0], args[1], args[2]) for kind, args, kw in ops[2:]} == expected_indexes
    assert all(kw == {"unique": False, "schema": "public"} for kind, args, kw in ops[2:])
    ddl = str(CreateTable(TABLE).compile(dialect=postgresql.dialect()))
    assert "FOREIGN KEY(external_identity_id, user_id) REFERENCES external_identities (id, user_id) ON DELETE RESTRICT" in ddl
    assert not {"secret", "csrf_token", "role", "permission", "company_id"} & set(TABLE.c.keys())
    assert all(c.default is None and c.server_default is None for c in TABLE.columns)


@pytest.mark.parametrize("revision", [guards.SESSION_REVISION, guards.ANALYSIS_REVISION])
@pytest.mark.parametrize("mutation", [
    lambda s: s + "\nraise RuntimeError('unapproved')\n",
    lambda s: s.replace('schema="public"', 'schema="unapproved"', 1),
    lambda s: s.replace('def downgrade()', 'def arbitrary()', 1),
    lambda s: s.replace('def upgrade() -> None:', 'def upgrade() -> None:\n    op.execute("unapproved")', 1),
])
def test_rehashing_altered_publication_cannot_approve_ast(monkeypatch, revision, mutation):
    path = guards.GENERAL_DIRECTORY / f"versions/{revision}.py"
    original = guards._read
    altered = mutation(original(path))
    manifest = json.loads(original(guards.MANIFEST_PATH))
    entry = next(e for e in manifest["revisions"] if e["revision"] == revision)
    entry["sha256"] = hashlib.sha256(altered.encode()).hexdigest()
    def read(candidate):
        if candidate == path:
            return altered
        if candidate == guards.MANIFEST_PATH:
            return json.dumps(manifest)
        return original(candidate)
    monkeypatch.setattr(guards, "_read", read)
    with pytest.raises(guards.MigrationGuardError):
        guards.inspect_sources()


def test_linear_final_publication_and_permanently_closed_downgrades():
    snapshot = guards.inspect_sources()
    assert guards.resolve_upgrade(snapshot.revisions, guards.HISTORICAL_HEAD, guards.ANALYSIS_REVISION) == ("12e2fc65f372", guards.ACCOUNT_REVISION, guards.SESSION_REVISION, guards.ANALYSIS_REVISION)
    for revision in (guards.SESSION_REVISION, guards.ANALYSIS_REVISION):
        path = guards.GENERAL_DIRECTORY / f"versions/{revision}.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        downgrade = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "downgrade")
        assert len(downgrade.body) == 1 and isinstance(downgrade.body[0], ast.Raise)
        assert downgrade.body[0].exc.func.id == "RuntimeError"
        assert "REQUIRES_SEPARATE_APPROVAL" in downgrade.body[0].exc.args[0].value


@pytest.mark.parametrize("revision,old,new", [
    (guards.SESSION_REVISION, '["external_identity_id", "user_id"]', '["external_identity_id"]'),
    (guards.SESSION_REVISION, 'ondelete="RESTRICT"', 'ondelete="CASCADE"'),
    (guards.ANALYSIS_REVISION, "role = 'company_admin' AND permission IN", "role IN ('technician', 'company_admin') AND permission IN"),
])
def test_security_semantic_changes_rejected_even_when_rehashed(monkeypatch, revision, old, new):
    path = guards.GENERAL_DIRECTORY / f"versions/{revision}.py"
    original = guards._read
    source = original(path)
    assert old in source
    altered = source.replace(old, new, 1)
    manifest = json.loads(original(guards.MANIFEST_PATH))
    next(e for e in manifest["revisions"] if e["revision"] == revision)["sha256"] = hashlib.sha256(altered.encode()).hexdigest()
    monkeypatch.setattr(guards, "_read", lambda p: altered if p == path else json.dumps(manifest) if p == guards.MANIFEST_PATH else original(p))
    with pytest.raises(guards.MigrationGuardError):
        guards.inspect_sources()
