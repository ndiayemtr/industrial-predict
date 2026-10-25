"""Pure administrative contracts/plans and fabricated catalog snapshots only."""

import ast
from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import hashlib
import hmac
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import URL

from app.p101_postgres.administration import (
    AdminAction, AdminApproval, AdminApprovalVerifier, CORE_CHAIN, OWNER_OPTIONS,
    authorize, migration_config, migration_plan_sha256, run_migration_environment,
    run_migrations, validate_owner_identity, validate_owner_transport,
    validate_migration_source_config,
)
from app.p101_postgres.bootstrap import (
    bootstrap_data, build_bootstrap_plan, privilege_plan, role_creation_plan, validate_bootstrap_plan,
)
from app.p101_postgres.guard import check_destination
from app.p101_postgres.runtime import GuardRejected, guard_policy_fingerprint, verify_ca
from p101_postgres.conftest import NOW
from p101_postgres.test_guard_repository_migration import catalog, CatalogSession


ADMIN_TEST_KEY = b"unit-test-only separate admin domain key 00000000"


def admin_token(config, action=AdminAction.CORE, digest=None, **changes):
    approval = AdminApproval("00000000-0000-4000-8000-000000000020", action,
        digest or migration_plan_sha256(action), guard_policy_fingerprint(config),
        (NOW + timedelta(days=1)).isoformat(), "")
    approval = replace(approval, **changes)
    return replace(approval, signature=hmac.new(ADMIN_TEST_KEY, approval.payload(), hashlib.sha256).hexdigest())


@pytest.fixture
def admin_verifier():
    return AdminApprovalVerifier(ADMIN_TEST_KEY)


def fake_owner_connection(config, **changes):
    parameters = dict(sslmode="verify-full", sslrootcert=config.tls_root_certificate)
    info = SimpleNamespace(get_parameters=lambda: parameters, host=config.destination.host,
        port=config.destination.port, dbname=config.destination.database, user=config.owner_role, options=OWNER_OPTIONS)
    for key, value in changes.items():
        if key in parameters: parameters[key] = value
        else: setattr(info, key, value)
    driver = SimpleNamespace(info=info, pgconn=SimpleNamespace(ssl_in_use=True))
    url = URL.create("postgresql+psycopg", username=config.owner_role, host=config.destination.host,
                     port=config.destination.port, database=config.destination.database)
    return SimpleNamespace(engine=SimpleNamespace(url=url), connection=SimpleNamespace(driver_connection=driver))


def test_admin_approval_nominal_and_migration_config_only(config, admin_verifier):
    for action in (AdminAction.CORE, AdminAction.PILOT):
        approval = admin_token(config, action)
        authorize(config, approval, admin_verifier, action, migration_plan_sha256(action), NOW)
        cfg = migration_config(object(), config, approval, admin_verifier, action)
        validate_migration_source_config(cfg, action)
        assert "sqlalchemy.url" not in cfg.get_section("alembic")
        assert cfg.attributes["p101_admin_verifier"] is admin_verifier
        assert "p101_authorize_migration" not in cfg.attributes
    assert migration_plan_sha256(AdminAction.CORE) != migration_plan_sha256(AdminAction.PILOT)


@pytest.mark.parametrize("kind", ["absent", "bool", "expired", "signature", "scope", "plan", "policy", "uuid", "key", "business"])
def test_bad_admin_approval_is_rejected(config, admin_verifier, approval, kind):
    token = admin_token(config)
    if kind == "absent": token = None
    elif kind == "bool": token = True
    elif kind == "expired": token = admin_token(config, expires_at="2026-03-01T00:00:00Z")
    elif kind == "signature": token = replace(token, signature="0" * 64)
    elif kind == "scope": token = admin_token(config, AdminAction.PILOT)
    elif kind == "plan": token = admin_token(config, digest="1" * 64)
    elif kind == "policy": token = admin_token(config, policy_sha256="2" * 64)
    elif kind == "uuid": token = admin_token(config, approval_uuid="invalid")
    elif kind == "key": admin_verifier = AdminApprovalVerifier(b"different-unit-test-admin-key-00000000000000")
    elif kind == "business": token = approval
    with pytest.raises(GuardRejected):
        authorize(config, token, admin_verifier, AdminAction.CORE, migration_plan_sha256(AdminAction.CORE), NOW)


def test_no_permissive_callback_or_default_key(config):
    with pytest.raises(GuardRejected): AdminApprovalVerifier(b"")
    with pytest.raises(GuardRejected):
        authorize(config, admin_token(config), lambda *a: True, AdminAction.CORE,
                  migration_plan_sha256(AdminAction.CORE), NOW)
    # Missing attributes fail before a connection or Alembic run is requested.
    context = SimpleNamespace(is_offline_mode=lambda: False, config=SimpleNamespace(attributes={}))
    with pytest.raises(GuardRejected): run_migration_environment(context, AdminAction.CORE)
    context.is_offline_mode = lambda: True
    with pytest.raises(GuardRejected): run_migration_environment(context, AdminAction.PILOT)
    with pytest.raises(GuardRejected): run_migrations(None, config, None, None, AdminAction.CORE)


def test_migration_sources_cannot_be_overridden(config, admin_verifier):
    for action in (AdminAction.CORE, AdminAction.PILOT):
        cfg = migration_config(None, config, admin_token(config, action), admin_verifier, action)
        cfg.set_main_option("version_locations", "unapproved-folder")
        with pytest.raises(GuardRejected): validate_migration_source_config(cfg, action)


def test_ca_bytes_are_bound_in_both_approval_domains(config, dossier, approval, verifier, admin_verifier):
    token = admin_token(config)
    verify_ca(config)
    Path(config.tls_root_certificate).write_bytes(b"modified fake CA data, still not a certificate")
    with pytest.raises(GuardRejected): verify_ca(config)
    with pytest.raises(GuardRejected): verifier.verify(approval, dossier, config, NOW)
    with pytest.raises(GuardRejected):
        authorize(config, token, admin_verifier, AdminAction.CORE, migration_plan_sha256(AdminAction.CORE), NOW)
    changed = replace(config, tls_root_sha256=hashlib.sha256(Path(config.tls_root_certificate).read_bytes()).hexdigest())
    with pytest.raises(GuardRejected): verifier.verify(approval, dossier, changed, NOW)


@pytest.mark.parametrize("kind", ["relative", "digest", "missing", "oversize", "bootstrap"])
def test_invalid_ca_or_bootstrap_policy(config, kind):
    if kind == "relative": config = replace(config, tls_root_certificate="relative-ca.txt")
    elif kind == "digest": config = replace(config, tls_root_sha256="invalid")
    elif kind == "missing": config = replace(config, tls_root_certificate=str(Path(config.tls_root_certificate).with_name("missing")))
    elif kind == "oversize": Path(config.tls_root_certificate).write_bytes(b"x" * 65537)
    elif kind == "bootstrap": config = replace(config, bootstrap_uuid="invalid")
    with pytest.raises(GuardRejected): verify_ca(config)


def test_owner_transport_nominal_is_only_an_object_inspection(config):
    validate_owner_transport(fake_owner_connection(config), config)


@pytest.mark.parametrize("field,value", [("sslmode", "require"), ("sslrootcert", "another"),
    ("host", "dev.invalid"), ("port", 5433), ("dbname", "industrial_predict_dev"),
    ("user", "other"), ("options", "")])
def test_wrong_owner_transport_rejected(config, field, value):
    with pytest.raises(GuardRejected): validate_owner_transport(fake_owner_connection(config, **{field: value}), config)


def test_owner_transport_refuses_implicit_configuration(config, monkeypatch):
    monkeypatch.setenv("PGSERVICE", "forbidden")
    with pytest.raises(GuardRejected): validate_owner_transport(fake_owner_connection(config), config)


@pytest.mark.parametrize("field,value", [("database", "industrial_predict_dev"), ("session_role", "other"),
    ("effective_role", "other"), ("address", "other"), ("port", 55432), ("ssl", False), ("encoding", "LATIN1")])
def test_owner_effective_identity_rejected(config, field, value):
    row = dict(database=config.destination.database, session_role=config.owner_role, effective_role=config.owner_role,
               address=config.server_address, port=config.server_port, ssl=True, encoding="UTF8")
    validate_owner_identity(config, row)
    row[field] = value
    with pytest.raises(GuardRejected): validate_owner_identity(config, row)


@pytest.mark.parametrize("index,field,value", [
    (0, "bootstrap_uuid", "00000000-0000-4000-8000-000000000099"), (0, "marker_database", "other"),
    (1, "owner", "other"), (1, "arguments", "integer"), (1, "result_type", "integer"),
    (1, "language", "sql"), (1, "provolatile", "v"), (1, "execute_roles", ["PUBLIC"]),
    (1, "no_execute_delegation", False), (2, "definition", "PRIMARY KEY (prediction_id)"),
    (2, "columns", ["prediction_id"]), (2, "referenced_columns", ["equipment_id"]),
    (3, "tgtype", 5), (3, "tgnargs", 1), (3, "tgqual", "true"), (3, "attribute_numbers", "1"),
    (4, "owner", "other"), (4, "schema_owner", "other"), (4, "columns", []), (4, "relkind", "v"),
    (5, "definition", "CHECK (true)")])
def test_stronger_catalog_snapshots_fail_closed(config, index, field, value):
    rows = deepcopy(catalog(config))
    rows[index][0][field] = value
    with pytest.raises(GuardRejected): check_destination(CatalogSession(rows), config)


def test_extra_catalog_objects_and_checks_are_rejected(config):
    for index in (1, 2, 3, 4, 5):
        rows = deepcopy(catalog(config))
        rows[index].append(deepcopy(rows[index][0]))
        with pytest.raises(GuardRejected): check_destination(CatalogSession(rows), config)


def test_bootstrap_exact_pinned_scope_and_no_allocated_ids(config):
    root = Path(__file__).resolve().parents[2]
    manifest = json.loads((root / "tests/p101_anomaly/fixtures/p101-temperature-v1.json").read_text(encoding="utf-8"))
    plan = build_bootstrap_plan(config, manifest, NOW.isoformat())
    data = validate_bootstrap_plan(config, plan)
    assert len(data["parents"]) == 4 and len(data["manifest"]["observations"]) == 12
    assert [p["table"] for p in data["parents"]] == ["companies", "sites", "equipments", "sensors"]
    assert [o["fixture_id"] for o in data["manifest"]["observations"]][-2:] == ["DEMO-M-011", "DEMO-M-012"]
    assert all("id" not in p for p in data["parents"])
    assert data["bootstrap_uuid"] == config.bootstrap_uuid
    assert "prediction_records" not in plan.canonical_json
    assert build_bootstrap_plan(config, deepcopy(manifest), NOW.isoformat()) == plan
    changed = replace(config, bootstrap_uuid="00000000-0000-4000-8000-000000000099")
    with pytest.raises(GuardRejected): validate_bootstrap_plan(changed, plan)
    for kind in ("missing", "extra", "value", "unit", "asset"):
        bad = deepcopy(manifest)
        if kind == "missing": bad["observations"].pop()
        elif kind == "extra": bad["observations"].append(deepcopy(bad["observations"][-1]))
        elif kind == "value": bad["observations"][0]["value"] = 99
        elif kind == "unit": bad["observations"][0]["unit"] = "K"
        elif kind == "asset": bad["asset"]["equipment_code"] = "other"
        with pytest.raises(GuardRejected): build_bootstrap_plan(config, bad, NOW.isoformat())
    with pytest.raises(GuardRejected): validate_bootstrap_plan(config, replace(plan, sha256="0" * 64))
    # Even the operational entry rejects missing approval before touching a connection.
    with pytest.raises(GuardRejected): bootstrap_data(None, config, plan, None, None)


def test_role_and_privilege_plans_are_minimal_text_only(config):
    roles = role_creation_plan(config)
    assert len(roles) == 3 and len(set(roles)) == 3
    assert all("NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE" in s and "PASSWORD" not in s for s in roles)
    privileges = privilege_plan(config, "public.prediction_records_id_seq")
    assert not any("GRANT UPDATE" in s or "GRANT DELETE" in s or "GRANT CREATE" in s for s in privileges)
    inserts = [s for s in privileges if s.startswith("GRANT INSERT")]
    assert inserts == [f'GRANT INSERT ON public.prediction_records,p101_pilot.idempotency_records TO "{config.destination.role}"']
    assert any("REVOKE ALL ON DATABASE" in s and "PUBLIC" in s for s in privileges)
    assert any("GRANT EXECUTE" in s and "lock_sources()" in s for s in privileges)
    with pytest.raises(GuardRejected): privilege_plan(config, 'public.x; DROP TABLE x')


def test_entrypoints_and_bootstrap_static_no_execution():
    root = Path(__file__).resolve().parents[2]
    for folder in ("p101_core_migrations", "p101_migrations"):
        env = (root / "backend" / folder / "env.py").read_text(encoding="utf-8")
        ast.parse(env)
        assert "run_migration_environment" in env
        assert "create_engine" not in env and "core.database" not in env and "settings" not in env
    cfg = (root / "backend/p101_core_migrations/alembic.ini").read_text()
    assert "../migrations/versions" in cfg and "sqlalchemy.url" not in cfg
    chain = []
    for path in (root / "backend/migrations/versions").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        revision = next(ast.literal_eval(n.value) for n in tree.body
                        if isinstance(n, ast.AnnAssign) and n.target.id == "revision")
        chain.append(revision)
    assert len(chain) == 9 and set(chain) == set(CORE_CHAIN)
    admin = (root / "backend/app/p101_postgres/administration.py").read_text(encoding="utf-8")
    bootstrap = (root / "backend/app/p101_postgres/bootstrap.py").read_text(encoding="utf-8")
    assert "seed" not in bootstrap and "DATABASE_URL" not in admin
    function = next(n for n in ast.parse(admin).body if isinstance(n, ast.FunctionDef) and n.name == "run_migration_environment")
    fragment = ast.get_source_segment(admin, function)
    assert fragment.index("check_owner_identity(connection, policy)") < fragment.index("CREATE SCHEMA")
    assert "pg_advisory_xact_lock(1010042)" in bootstrap and "provisioning_closed=true" in bootstrap
    assert "RETURNING id" in bootstrap and "nextval" not in bootstrap
    assert "ON CONFLICT" not in bootstrap and "DELETE FROM" not in bootstrap
