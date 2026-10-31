"""Publication/AST/schema checks only: the revision module is never imported."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import CheckConstraint, DateTime, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app import general_migrations as guards
from app.models.oidc_transaction import OidcTransactionRecord


REVISION = "12e2fc65f372"
PATH = guards.GENERAL_DIRECTORY / "versions/12e2fc65f372_create_oidc_transactions.py"
TABLE = OidcTransactionRecord.__table__
MARKER = "SYNTHETIC-UNAPPROVED-REVISION-DETAIL"


@pytest.fixture(autouse=True)
def no_revision_import_or_database(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Real SQL/network/DDL forbidden")

    for name in ("sqlalchemy.create_engine", "sqlalchemy.engine_from_config", "sqlalchemy.engine.Engine.connect",
                 "sqlalchemy.engine.Engine.raw_connection", "sqlalchemy.engine.Connection.execute",
                 "sqlalchemy.engine.Connection.exec_driver_sql", "psycopg.connect", "socket.socket.connect",
                 "socket.create_connection", "socket.getaddrinfo", "alembic.command.upgrade",
                 "alembic.command.downgrade", "alembic.command.stamp", "alembic.command.revision",
                 "alembic.operations.Operations.execute"):
        monkeypatch.setattr(name, forbidden)
    importer = Mock(side_effect=AssertionError("Revision import forbidden"))
    monkeypatch.setattr("alembic.util.load_python_file", importer)
    yield
    importer.assert_not_called()
    assert not any(str(getattr(m, "__file__", "")).endswith(PATH.name) for m in list(sys.modules.values()))


@pytest.fixture
def source():
    return guards._read(PATH)


def assert_rejected(call):
    with pytest.raises(guards.MigrationGuardError) as caught:
        call()
    assert str(caught.value) == "GENERAL_MIGRATION_REJECTED"
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert MARKER not in repr(caught.value)


def test_publication_identity_hash_and_single_extended_head(source):
    entries = guards.read_manifest()
    assert len(entries) == 2
    entry = entries[0]
    assert (entry.revision, entry.parent, entry.path, entry.schema_scope) == (
        REVISION, "09ac8101e9fe", PATH.relative_to(guards.BACKEND).as_posix(), ("public.oidc_transactions",))
    assert hashlib.sha256(source.encode("utf-8")).hexdigest() == entry.sha256
    assert hashlib.sha256(PATH.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == entry.sha256
    snapshot = guards.inspect_sources()
    nodes = {r.revision: r for r in snapshot.revisions}
    assert set(nodes) == set(guards.HISTORICAL_CHAIN) | {REVISION, guards.ACCOUNT_REVISION}
    assert set(nodes) - {r.parent for r in snapshot.revisions} == {guards.ACCOUNT_REVISION}
    assert guards.resolve_upgrade(snapshot.revisions, guards.HISTORICAL_HEAD, REVISION) == (REVISION,)
    fingerprints = {s.path: s.sha256 for s in snapshot.sources}
    assert fingerprints[entry.path] == entry.sha256
    assert "general_migrations/revision_manifest.json" in fingerprints
    # Presence of downgrade code does not change the upgrade-only boundary.
    assert_rejected(lambda: guards.resolve_upgrade(snapshot.revisions, REVISION, guards.HISTORICAL_HEAD))


def test_every_hash_checked_before_first_ast(monkeypatch):
    events = []
    fingerprint, parse = guards._fingerprint, guards._parse_revision
    def hashed(path, source):
        events.append(("hash", path))
        return fingerprint(path, source)
    def parsed(path, source):
        events.append(("ast", path))
        return parse(path, source)
    monkeypatch.setattr(guards, "_fingerprint", hashed)
    monkeypatch.setattr(guards, "_parse_revision", parsed)
    guards.inspect_sources()
    hashes = [i for i, (kind, p) in enumerate(events) if kind == "hash" and p.parent in (PATH.parent, guards.HISTORICAL_DIRECTORY)]
    parses = [i for i, (kind, _) in enumerate(events) if kind == "ast"]
    assert len(hashes) == len(parses) == 11
    assert max(hashes) < min(parses)


def test_altered_hash_rejected_before_any_ast(monkeypatch):
    read = guards._read
    monkeypatch.setattr(guards, "_read", lambda p: read(p) + ("\n# " + MARKER if p == PATH else ""))
    with patch.object(guards, "_parse_revision") as parser:
        assert_rejected(guards.inspect_sources)
        parser.assert_not_called()


def manifest_data():
    return json.loads(guards._read(guards.MANIFEST_PATH))


@pytest.mark.parametrize("change", [
    {"format": "unknown"}, {"enabled": True}, {"revisions": []}, {"revisions": {}},
    {"revisions": "invalid"},
])
def test_manifest_root_closed_schema(monkeypatch, change):
    data = manifest_data()
    data.update(change)
    read = guards._read
    monkeypatch.setattr(guards, "_read", lambda p: json.dumps(data) if p == guards.MANIFEST_PATH else read(p))
    assert_rejected(guards.inspect_sources)


@pytest.mark.parametrize("change", [
    {"extra": MARKER}, {"revision": "head"}, {"revision": "09ac8101e9fe"},
    {"parent": "d6ec01cf13b6"}, {"path": "../outside.py"},
    {"path": "/outside.py"}, {"path": "D:\\outside.py"},
    {"path": "general_migrations/versions/../outside.py"},
    {"path": "general_migrations/versions/wrong_name.py"},
    {"sha256": "invalid"}, {"sha256": "A" * 64}, {"sha256": "0" * 64},
    {"schema_scope": ["public.prediction_records"]}, {"schema_scope": "public.oidc_transactions"},
])
def test_manifest_entry_closed_identity_and_paths(monkeypatch, change):
    data = manifest_data()
    data["revisions"][0].update(change)
    read = guards._read
    monkeypatch.setattr(guards, "_read", lambda p: json.dumps(data) if p == guards.MANIFEST_PATH else read(p))
    assert_rejected(guards.inspect_sources)


@pytest.mark.parametrize("kind", ["entry", "root_key", "entry_key", "missing_field", "malformed"])
def test_manifest_duplicates_and_missing_fields_rejected(monkeypatch, kind):
    data = manifest_data()
    if kind == "entry":
        data["revisions"].append(dict(data["revisions"][0]))
    elif kind == "missing_field":
        del data["revisions"][0]["sha256"]
    text = json.dumps(data)
    if kind == "root_key":
        text = text.replace('"format":', '"format": "general-revisions-v1", "format":', 1)
    elif kind == "entry_key":
        text = text.replace('"revision":', '"revision": "duplicate", "revision":', 1)
    elif kind == "malformed":
        text = "{ " + MARKER
    read = guards._read
    monkeypatch.setattr(guards, "_read", lambda p: text if p == guards.MANIFEST_PATH else read(p))
    assert_rejected(guards.inspect_sources)


@pytest.mark.parametrize("extra", ["unexpected.py", "unexpected.txt", "nested", "__pycache__"])
def test_exact_version_file_set_rejects_every_extra_before_source_read(monkeypatch, extra):
    original = Path.iterdir
    def added(path):
        return iter((*original(path), path / extra)) if path == PATH.parent else original(path)
    monkeypatch.setattr(Path, "iterdir", added)
    with patch.object(guards, "_read", wraps=guards._read) as reader:
        assert_rejected(guards.inspect_sources)
        reader.assert_called_once_with(guards.MANIFEST_PATH)


def test_missing_published_file_rejected(monkeypatch):
    original = Path.iterdir
    monkeypatch.setattr(Path, "iterdir", lambda p: iter(x for x in original(p) if x != PATH))
    assert_rejected(guards.inspect_sources)


def test_symlink_or_directory_redirect_rejected_before_source_read(monkeypatch):
    # Simulate resolve() on a redirected source, without creating OS symlinks.
    original = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda p, *a, **kw:
                        guards.BACKEND.parent / "outside.py" if p == PATH else original(p, *a, **kw))
    with patch.object(guards, "_read", wraps=guards._read) as reader:
        assert_rejected(guards.inspect_sources)
        reader.assert_called_once_with(guards.MANIFEST_PATH)


@pytest.mark.parametrize("old,new", [
    ('revision = "12e2fc65f372"', 'revision = "wrong_revision"'),
    ('down_revision = "09ac8101e9fe"', 'down_revision = "d6ec01cf13b6"'),
])
def test_metadata_rejected_even_with_matching_modified_manifest_hash(monkeypatch, source, old, new):
    altered = source.replace(old, new)
    assert altered != source
    data = manifest_data()
    data["revisions"][0]["sha256"] = hashlib.sha256(altered.encode()).hexdigest()
    read = guards._read
    monkeypatch.setattr(guards, "_read", lambda p:
                        altered if p == PATH else json.dumps(data) if p == guards.MANIFEST_PATH else read(p))
    assert_rejected(guards.inspect_sources)


@pytest.mark.parametrize("old,new", [
    ('from alembic import op', 'from app.core.database import op'),
    ('import sqlalchemy as sa', 'import sqlalchemy as sa\nimport socket'),
    ('def upgrade() -> None:', '@dangerous()\ndef upgrade() -> None:'),
    ('def upgrade() -> None:', 'def upgrade(connection=__import__("socket")) -> None:'),
    ('def upgrade() -> None:', 'def upgrade() -> __import__("socket"):'),
    ('def upgrade() -> None:', 'async def upgrade() -> None:'),
    ('revision = "12e2fc65f372"', 'revision: dangerous() = "12e2fc65f372"'),
    ('sa.String(64)', 'sa.String(32 + 32)'),
    ('nullable=False', 'nullable=0'),
    ('sa.String(43)', 'sa.String(64)'),
    ('op.create_index(', 'op.execute('),
    ('"oidc_transactions"', '"prediction_records"'),
    ('schema="public"', 'schema="p101_pilot"'),
    ('schema="public",', '**{"schema": "public"},'),
    ('unique=False', 'unique=True'),
    ('"char_length(nonce) = 43"', '"true"'),
    ('op.drop_table("oidc_transactions", schema="public")',
     'op.drop_table("oidc_transactions", schema="public", cascade=True)'),
    ('    op.create_table(', '    open("' + MARKER + '", "w")\n    op.create_table('),
    ('    op.create_table(', '    with op.get_context().autocommit_block():\n        pass\n    op.create_table('),
])
def test_closed_ast_rejects_dynamic_and_out_of_scope_constructions(source, old, new):
    altered = source.replace(old, new)
    assert altered != source
    assert_rejected(lambda: guards.validate_oidc_source(altered, revision=REVISION, parent=guards.HISTORICAL_HEAD))


def test_module_side_effect_rejected_even_with_matching_manifest(monkeypatch, source):
    altered = source + '\nraise RuntimeError("' + MARKER + '")\n'
    data = manifest_data()
    data["revisions"][0]["sha256"] = hashlib.sha256(altered.encode()).hexdigest()
    read = guards._read
    monkeypatch.setattr(guards, "_read", lambda p:
                        altered if p == PATH else json.dumps(data) if p == guards.MANIFEST_PATH else read(p))
    assert_rejected(guards.inspect_sources)


def test_migration_ast_matches_orm_exactly_without_executing_it(source):
    upgrade, downgrade = guards.validate_oidc_source(source, revision=REVISION, parent=guards.HISTORICAL_HEAD)
    operation, table_args, table_kwargs = upgrade[0]
    assert operation == "op.create_table" and table_args[0] == TABLE.name
    assert dict(table_kwargs) == {"schema": TABLE.schema}
    columns = [item for item in table_args[1:] if item[0] == "sa.Column"]
    assert [item[1][0] for item in columns] == list(TABLE.c.keys())
    for _, (name, type_spec), keywords in columns:
        column = TABLE.c[name]
        assert dict(keywords) == {"nullable": column.nullable} == {"nullable": False}
        type_name, type_args, type_keywords = type_spec
        if isinstance(column.type, Text):
            assert (type_name, type_args, type_keywords) == ("sa.Text", (), ())
        elif isinstance(column.type, String):
            assert (type_name, type_args, type_keywords) == ("sa.String", (column.type.length,), ())
        else:
            assert isinstance(column.type, DateTime)
            assert (type_name, type_args, type_keywords) == ("sa.DateTime", (), (("timezone", True),))
        assert column.default is None and column.server_default is None
    checks = {dict(item[2])["name"]: item[1][0] for item in table_args[1:] if item[0] == "sa.CheckConstraint"}
    assert checks == {c.name: str(c.sqltext) for c in TABLE.constraints if isinstance(c, CheckConstraint)}
    for constructor, cls in (("sa.PrimaryKeyConstraint", PrimaryKeyConstraint), ("sa.UniqueConstraint", UniqueConstraint)):
        declared = {dict(item[2])["name"]: item[1] for item in table_args[1:] if item[0] == constructor}
        assert declared == {c.name: tuple(column.name for column in c.columns)
                            for c in TABLE.constraints if isinstance(c, cls)}
    assert not TABLE.foreign_keys and len(TABLE.constraints) == 9
    assert checks["ck_oidc_transactions_nonce_length"] == "char_length(nonce) = 43"
    assert checks["ck_oidc_transactions_code_verifier_length"] == "char_length(code_verifier) = 43"
    index = next(iter(TABLE.indexes))
    assert len(TABLE.indexes) == 1
    assert upgrade[1] == ("op.create_index", (index.name, TABLE.name, tuple(c.name for c in index.columns)),
                          (("schema", TABLE.schema), ("unique", index.unique)))
    assert downgrade == (
        ("op.drop_index", (index.name,), (("schema", "public"), ("table_name", TABLE.name))),
        ("op.drop_table", (TABLE.name,), (("schema", "public"),)),
    )
    ddl = str(CreateTable(TABLE).compile(dialect=postgresql.dialect()))
    assert "CREATE TABLE public.oidc_transactions" in ddl and "TIMESTAMP WITH TIME ZONE" in ddl
    assert "FOREIGN KEY" not in ddl and "DEFAULT" not in ddl and "SERIAL" not in ddl
    assert "char_length(nonce) = 43" in ddl and "char_length(code_verifier) = 43" in ddl
    assert "ON public.oidc_transactions (expires_at)" in str(CreateIndex(index).compile(dialect=postgresql.dialect()))


def test_recognized_plan_still_has_no_execution_authority():
    # A complete OIDC plan is recognized but cannot open/touch this connection.
    snapshot = guards.inspect_sources()
    now = datetime(2026, 10, 28, tzinfo=timezone.utc)
    target = guards.DestinationExpectation("oidc-migration-test", "00000000-0000-4000-8000-000000000001",
        "sql.example.invalid", 6543, "oidc_test_only", "oidc_test_owner", "192.0.2.10", 5432,
        guards.TransportExpectation("verify-full", "a" * 64))
    intent = guards.MigrationIntent(target, "upgrade", guards.HISTORICAL_HEAD, REVISION, (REVISION,), snapshot.sources, guards.SCHEMA_SCOPE)
    claim = guards.ApprovalDeclaration("00000000-0000-4000-8000-000000000002", "untrusted-issuer", intent, now + timedelta(minutes=1))
    report = guards.preflight(intent, claim, now=now)
    assert report.declaration_matches and not report.authenticated and not report.execution_enabled
    connection = Mock()
    with pytest.raises(guards.MigrationExecutionDisabled):
        guards.request_execution(intent, claim, now=now, connection=connection)
    connection.assert_not_called()
    assert connection.mock_calls == []
    forbidden = replace(intent, direction="downgrade")
    assert_rejected(lambda: guards.preflight(forbidden, replace(claim, intent=forbidden), now=now))
