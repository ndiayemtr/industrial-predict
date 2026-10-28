"""Offline declarations/graphs only; no proof of a real destination or DDL."""

import ast
from dataclasses import replace
from datetime import datetime, timedelta, timezone, tzinfo
import os
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import Mock, patch

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.script.revision import Revision, RevisionMap
from alembic.util.exc import CommandError
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

from app import general_migrations as module


NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
SENSITIVE = "SYNTHETIC-GENERAL-MIGRATION-PRIVATE-DETAIL"


@pytest.fixture(autouse=True)
def no_database_or_migration_commands(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Database/network/migration execution forbidden")

    for name in ("sqlalchemy.create_engine", "sqlalchemy.engine_from_config",
                 "sqlalchemy.engine.Engine.connect", "sqlalchemy.engine.Engine.raw_connection",
                 "sqlalchemy.engine.Connection.execute", "sqlalchemy.engine.Connection.exec_driver_sql",
                 "psycopg.connect", "socket.create_connection", "socket.socket.connect",
                 "socket.socket.connect_ex", "socket.getaddrinfo",
                 "alembic.command.upgrade", "alembic.command.downgrade", "alembic.command.stamp",
                 "alembic.command.revision", "alembic.command.merge", "alembic.operations.Operations.execute"):
        monkeypatch.setattr(name, forbidden)


@pytest.fixture
def destination():
    return module.DestinationExpectation(
        "oidc-migration-test", "00000000-0000-4000-8000-000000000001",
        "sql.example.invalid", 6543, "oidc_test_only", "oidc_test_owner",
        "192.0.2.10", 5432, module.TransportExpectation("verify-full", "a" * 64))


@pytest.fixture
def intent(destination):
    return module.MigrationIntent(destination, "upgrade", module.HISTORICAL_HEAD,
                                  module.HISTORICAL_HEAD, (), module.inspect_sources().sources,
                                  module.SCHEMA_SCOPE)


@pytest.fixture
def declaration(intent):
    # A synthetic CLAIM, deliberately not signed or authenticated.
    return module.ApprovalDeclaration("00000000-0000-4000-8000-000000000002",
                                      "synthetic-untrusted-issuer", intent, NOW + timedelta(minutes=5))


def assert_sanitized(error):
    assert str(error) == "GENERAL_MIGRATION_REJECTED"
    assert error.__context__ is None and error.__cause__ is None
    assert SENSITIVE not in repr(error)


def test_required_contract_fields_and_no_secret_fields():
    for cls in (module.DestinationExpectation, module.TransportExpectation,
                module.MigrationIntent, module.ApprovalDeclaration):
        with pytest.raises(TypeError):
            cls()
        assert not {"password", "database_url", "signature"} & set(cls.__dataclass_fields__)


def test_guarded_config_is_inert_even_after_source_validation():
    config = module.make_alembic_config()
    for name in ("sqlalchemy.url", "script_location", "version_locations", "prepend_sys_path"):
        assert not config.get_main_option(name)
    assert config.attributes == {}
    with pytest.raises(CommandError):
        ScriptDirectory.from_config(config)
    assert not list((module.GENERAL_DIRECTORY / "versions").glob("*.py"))


def test_real_historical_graph_and_pinned_sources_without_running_env():
    snapshot = module.inspect_sources()
    assert len(snapshot.revisions) == 9
    assert {r.revision for r in snapshot.revisions} == set(module.HISTORICAL_CHAIN)
    assert len(snapshot.sources) == 12  # nine revisions, config, env, guards
    graph = RevisionMap(lambda: iter(Revision(r.revision, r.parent) for r in snapshot.revisions))
    assert graph.heads == (module.HISTORICAL_HEAD,)
    assert len(list(graph.iterate_revisions(module.HISTORICAL_HEAD, "base"))) == 9
    assert module.resolve_upgrade(snapshot.revisions, module.HISTORICAL_HEAD, module.HISTORICAL_HEAD) == ()


def test_future_external_parent_resolution_with_alembic_in_memory_only():
    snapshot = module.inspect_sources()
    future = module.RevisionDescription("oidc_synthetic_future", module.HISTORICAL_HEAD,
                                        "general_migrations/versions/oidc_synthetic_future.py")
    revisions = snapshot.revisions + (future,)
    assert module.resolve_upgrade(revisions, module.HISTORICAL_HEAD, future.revision) == (future.revision,)
    # Alembic metadata only: no ScriptDirectory loader or migration module.
    graph = RevisionMap(lambda: iter(Revision(r.revision, r.parent) for r in revisions))
    assert graph.heads == (future.revision,)
    parent = graph.get_revision(future.revision).down_revision
    assert graph.get_revision(parent).revision == module.HISTORICAL_HEAD
    assert [r.revision for r in graph.iterate_revisions(future.revision, module.HISTORICAL_HEAD)] == [future.revision]
    assert (module.BACKEND / future.path).parent == module.GENERAL_DIRECTORY / "versions"
    assert not (module.BACKEND / future.path).exists()


@pytest.mark.parametrize("kind", ["unknown", "head", "heads", "downgrade", "multiple_heads", "duplicate", "cycle", "missing_parent"])
def test_invalid_graphs_and_targets_are_rejected(kind):
    graph = module.inspect_sources().revisions
    target = module.HISTORICAL_HEAD
    if kind in {"unknown", "head", "heads"}:
        target = kind
    elif kind == "downgrade":
        target = module.HISTORICAL_CHAIN[-2]
    elif kind == "multiple_heads":
        graph += tuple(module.RevisionDescription(name, module.HISTORICAL_HEAD, name) for name in ("future_a", "future_b"))
    elif kind == "duplicate":
        graph += (graph[0],)
    elif kind == "cycle":
        graph += (module.RevisionDescription("future_a", "future_b", "a"),
                  module.RevisionDescription("future_b", "future_a", "b"))
    else:
        graph += (module.RevisionDescription("future_a", "absent_parent", "a"),)
    with pytest.raises(module.MigrationGuardError) as caught:
        module.resolve_upgrade(graph, module.HISTORICAL_HEAD, target)
    assert_sanitized(caught.value)


def test_historical_source_alteration_rejected_without_modifying_files(monkeypatch):
    original = module._read
    def changed(path):
        source = original(path)
        return source + "\n# simulated alteration\n" if path.parent == module.HISTORICAL_DIRECTORY else source
    monkeypatch.setattr(module, "_read", changed)
    with pytest.raises(module.MigrationGuardError) as caught:
        module.inspect_sources()
    assert_sanitized(caught.value)


@pytest.mark.parametrize("guarded", [False, True])
@pytest.mark.parametrize("consultation", ["heads", "history", "branches"])
def test_graph_consultations_refuse_before_any_revision_import(guarded, consultation):
    with patch("alembic.util.load_python_file") as importer:
        config = module.make_alembic_config() if guarded else Config(str(module.GENERAL_DIRECTORY / "alembic.ini"))
        with pytest.raises(CommandError):
            getattr(command, consultation)(config)
        importer.assert_not_called()


def test_config_checks_sources_before_construction():
    events = []
    inspect = module.inspect_sources
    def inspected():
        events.append("inspect")
        return inspect()
    def constructed(*args, **kwargs):
        events.append("config")
        return Config(*args, **kwargs)
    with patch.object(module, "inspect_sources", side_effect=inspected), \
         patch("alembic.config.Config", side_effect=constructed):
        module.make_alembic_config()
    assert events == ["inspect", "config"]


def test_altered_historical_source_refused_before_config_or_import(monkeypatch):
    original = module._read
    def altered(path):
        source = original(path)
        return source + "\nraise RuntimeError('unapproved source')\n" if path.parent == module.HISTORICAL_DIRECTORY else source
    monkeypatch.setattr(module, "_read", altered)
    with patch("alembic.config.Config") as constructor, patch("alembic.util.load_python_file") as importer:
        with pytest.raises(module.MigrationGuardError) as caught:
            module.make_alembic_config()
        assert_sanitized(caught.value)
        constructor.assert_not_called()
        importer.assert_not_called()


def test_future_source_refused_before_read_config_or_import(monkeypatch):
    # Simulate discovery, without creating a revision file in any directory.
    future = module.GENERAL_DIRECTORY / "versions/unapproved_future.py"
    original = Path.glob
    def discovered(path, pattern):
        if path == future.parent and pattern == "*.py":
            return iter((future,))
        return original(path, pattern)
    monkeypatch.setattr(Path, "glob", discovered)
    with patch.object(module, "_read") as reader, \
         patch("alembic.config.Config") as constructor, \
         patch("alembic.util.load_python_file") as importer:
        with pytest.raises(module.MigrationGuardError) as caught:
            module.make_alembic_config()
        assert_sanitized(caught.value)
        reader.assert_not_called()
        constructor.assert_not_called()
        importer.assert_not_called()
    assert not future.exists()


def test_config_remains_inert_if_sources_change_after_return(monkeypatch):
    config = module.make_alembic_config()
    monkeypatch.setattr(module, "inspect_sources", Mock(side_effect=ValueError(SENSITIVE)))
    with patch("alembic.util.load_python_file") as importer:
        with pytest.raises(CommandError):
            command.heads(config)
        importer.assert_not_called()


@pytest.mark.parametrize("option", ["script_location", "version_locations", "prepend_sys_path", "sqlalchemy.url"])
def test_guarded_api_rejects_operational_options_in_ini(option):
    def altered(*args):
        config = Config()
        config.set_main_option("path_separator", "newline")
        config.set_main_option(option, SENSITIVE)
        return config
    with patch("alembic.config.Config", side_effect=altered):
        with pytest.raises(module.MigrationGuardError) as caught:
            module.make_alembic_config()
    assert_sanitized(caught.value)


@pytest.mark.parametrize("host", [
    ".", "...", "-", "host..invalid", ".host.invalid", "host.invalid.",
    "-host.invalid", "host-.invalid", "host._label.invalid", "a" * 64 + ".invalid",
    "127.0.0.999", "256.1.2.3", "127.1", "01.2.3.4", "1234", "1.2.3.4.5",
    "2001:db8:::1", "[2001:db8::1]", "fe80::1%eth0", "host invalid", "host\n.invalid",
    "https://host.invalid", "host.invalid:5432", "höst.invalid", "", None,
])
def test_invalid_dns_and_ip_hosts_are_sanitized(intent, declaration, host):
    altered = replace(intent, destination=replace(intent.destination, host=host))
    with pytest.raises(module.MigrationGuardError) as caught:
        module.preflight(altered, replace(declaration, intent=altered), now=NOW)
    assert_sanitized(caught.value)


@pytest.mark.parametrize("host", ["sql.example.invalid", "SQL.Example.INVALID", "localhost",
                                  "host-1.example.invalid", "a" * 63 + ".invalid",
                                  "192.0.2.10", "127.0.0.1", "2001:db8::1", "::1", "::ffff:192.0.2.10"])
def test_valid_dns_ipv4_and_ipv6_hosts_need_no_lookup(intent, declaration, host):
    altered = replace(intent, destination=replace(intent.destination, host=host))
    report = module.preflight(altered, replace(declaration, intent=altered), now=NOW)
    assert report.declaration_matches
    assert not report.authenticated and not report.execution_enabled


def test_reference_preflight_never_authenticates_or_authorizes(intent, declaration):
    result = module.preflight(intent, declaration, now=NOW)
    assert result.declaration_matches and result.sources_match
    assert result.authenticated is False and result.execution_enabled is False
    assert SENSITIVE not in repr(intent) + repr(declaration)


@pytest.mark.parametrize("approval", [None, True, {}, object()])
def test_absent_or_untyped_approval_rejected(intent, approval):
    with pytest.raises(module.MigrationGuardError):
        module.preflight(intent, approval, now=NOW)


@pytest.mark.parametrize("environment", ["development", "production", "p101", "p101-local-demo", "unknown"])
def test_unapproved_environments_rejected(intent, declaration, environment):
    altered = replace(intent, destination=replace(intent.destination, environment_id=environment))
    with pytest.raises(module.MigrationGuardError):
        module.preflight(altered, replace(declaration, intent=altered), now=NOW)


@pytest.mark.parametrize("database", ["industrial_predict", "industrial_predict_ml_sandbox", "industrial_predict_p101_local_demo"])
def test_dev_and_p101_destinations_are_rejected(intent, declaration, database):
    altered = replace(intent, destination=replace(intent.destination, database=database))
    with pytest.raises(module.MigrationGuardError):
        module.preflight(altered, replace(declaration, intent=altered), now=NOW)


@pytest.mark.parametrize("field,value", [
    ("host", "other.example.invalid"), ("database", "other_test_database"),
    ("role", "other_test_owner"), ("port", 6544), ("server_address", "192.0.2.11"),
    ("server_port", 5433), ("instance_id", "00000000-0000-4000-8000-000000000003"),
    ("transport", module.TransportExpectation("verify-full", "b" * 64)),
])
def test_destination_mismatch_against_claim_is_rejected(intent, declaration, field, value):
    altered = replace(intent, destination=replace(intent.destination, **{field: value}))
    with pytest.raises(module.MigrationGuardError):
        module.preflight(altered, declaration, now=NOW)


@pytest.mark.parametrize("transport", [module.TransportExpectation("disable", "a" * 64),
                                      module.TransportExpectation("require", "a" * 64),
                                      module.TransportExpectation("verify-full", "0" * 64)])
def test_unsafe_transport_even_with_matching_claim_is_rejected(intent, declaration, transport):
    altered = replace(intent, destination=replace(intent.destination, transport=transport))
    with pytest.raises(module.MigrationGuardError):
        module.preflight(altered, replace(declaration, intent=altered), now=NOW)


@pytest.mark.parametrize("expiry", [NOW, NOW - timedelta(microseconds=1), NOW.replace(tzinfo=None)])
def test_expiry_is_strict_and_timezone_required(intent, declaration, expiry):
    with pytest.raises(module.MigrationGuardError):
        module.preflight(intent, replace(declaration, expires_at=expiry), now=NOW)


@pytest.mark.parametrize("change", [
    {"direction": "downgrade"}, {"direction": "stamp"}, {"direction": "autogenerate"},
    {"final_revision": "head"}, {"final_revision": "unknown"},
    {"initial_revision": module.HISTORICAL_CHAIN[0]}, {"sequence": (module.HISTORICAL_HEAD,)},
    {"schema_scope": ("public.prediction_records",)}, {"sources": ()},
])
def test_disallowed_operations_sequences_sources_and_scope(intent, declaration, change):
    altered = replace(intent, **change)
    with pytest.raises(module.MigrationGuardError):
        module.preflight(altered, replace(declaration, intent=altered), now=NOW)


def test_sources_changed_after_claim_are_rejected(intent, declaration, monkeypatch):
    original = module._read
    monkeypatch.setattr(module, "_read", lambda p: original(p) + ("\n# change" if p.name == "env.py" else ""))
    with pytest.raises(module.MigrationGuardError):
        module.preflight(intent, declaration, now=NOW)


def test_graph_changed_after_claim_is_rejected(intent, declaration, monkeypatch):
    snapshot = module.inspect_sources()
    future = module.RevisionDescription("oidc_synthetic_future", module.HISTORICAL_HEAD,
                                        "general_migrations/versions/oidc_synthetic_future.py")
    changed = module.SourceSnapshot(snapshot.revisions + (future,), snapshot.sources + (
        module.SourceFingerprint(future.path, "e" * 64),))
    monkeypatch.setattr(module, "inspect_sources", lambda: changed)
    with pytest.raises(module.MigrationGuardError):
        module.preflight(intent, declaration, now=NOW)


def test_no_execution_even_with_matching_claim_and_injected_connection(intent, declaration):
    connection = Mock(spec=Connection)
    with pytest.raises(module.MigrationExecutionDisabled) as caught:
        module.request_execution(intent, declaration, now=NOW, connection=connection)
    assert str(caught.value) == "GENERAL_MIGRATION_EXECUTION_DISABLED"
    assert caught.value.__context__ is None
    assert connection.mock_calls == []


def test_env_always_refuses_without_loading_metadata_or_connection():
    with pytest.raises(module.MigrationExecutionDisabled):
        runpy.run_path(str(module.GENERAL_DIRECTORY / "env.py"),
                       init_globals={"connection": Mock(spec=Connection), "approved": True})
    source = (module.GENERAL_DIRECTORY / "env.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert any(isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and n.value.value is None
               and any(isinstance(t, ast.Name) and t.id == "target_metadata" for t in n.targets) for n in tree.body)


def test_installed_alembic_preserves_external_transaction_with_simulated_connection():
    connection = Mock(spec=Connection)
    connection.dialect = postgresql.dialect()
    connection.in_transaction.return_value = True
    context = MigrationContext.configure(connection=connection,
        opts={"transactional_ddl": True, "transaction_per_migration": False})
    with context.begin_transaction():
        pass
    connection.begin.assert_not_called()
    connection.commit.assert_not_called()
    connection.rollback.assert_not_called()
    connection.close.assert_not_called()


def test_p101_and_local_demo_paths_cannot_discover_future_directory():
    p101 = Config(str(module.BACKEND / "p101_core_migrations/alembic.ini"))
    historical = Path(p101.get_main_option("version_locations")).resolve()
    assert historical == module.HISTORICAL_DIRECTORY
    assert len(list(historical.glob("*.py"))) == 9
    local_source = (module.BACKEND / "app/p101_local_demo/provisioning.py").read_text(encoding="utf-8")
    assert "general_migrations" not in local_source
    assert "backend/migrations/versions" in local_source and "backend/local_demo_migrations/versions" in local_source
    # No imports of P101, its policy, or the FastAPI application.
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(name.startswith(("app.p101", "app.core", "app.models", "fastapi")) for name in imports)


def test_validation_errors_do_not_retain_sensitive_timezone_context(intent, declaration):
    class BrokenTimezone(tzinfo):
        def utcoffset(self, dt):
            raise ValueError(SENSITIVE)
    with pytest.raises(module.MigrationGuardError) as caught:
        module.preflight(intent, declaration, now=NOW.replace(tzinfo=BrokenTimezone()))
    assert_sanitized(caught.value)


def test_import_is_inert_in_isolated_process():
    script = r'''
import importlib.abc, sys
from contextlib import ExitStack
from unittest.mock import patch
import sqlalchemy, sqlalchemy.orm, psycopg
sys.path.insert(0, sys.argv[1])
def forbidden(*args, **kwargs): raise AssertionError('Implicit SQL/configuration forbidden')
class NoLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(('app.p101','app.models')) or fullname in (
            'app.main','app.application','app.core.config','app.core.database','dotenv','pydantic_settings'):
            forbidden()
sys.meta_path.insert(0, NoLegacy())
with ExitStack() as guards:
    for name in ('sqlalchemy.create_engine','sqlalchemy.engine_from_config',
                 'sqlalchemy.orm.sessionmaker','sqlalchemy.engine.Engine.connect',
                 'psycopg.connect','socket.socket.connect','socket.create_connection','socket.getaddrinfo'):
        guards.enter_context(patch(name, side_effect=forbidden))
    import app.general_migrations
    assert 'fastapi' not in sys.modules
    assert 'app.core.config' not in sys.modules
    assert 'app.models' not in sys.modules
'''
    env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP") if k in os.environ}
    env.update(DATABASE_URL="invalid://ambient", PGHOST="ambient.invalid")
    result = subprocess.run([sys.executable, "-B", "-I", "-c", script, str(module.BACKEND)],
                            cwd=module.BACKEND.parent, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
