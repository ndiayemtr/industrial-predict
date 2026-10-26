"""ML5.3A pure/static checks. No operational bootstrap, DDL, DML or ML calculation."""

import ast
from copy import deepcopy
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
from types import SimpleNamespace

from alembic import command
from alembic.script import ScriptDirectory
import psycopg
import pytest
from sqlalchemy import URL
from sqlalchemy.engine import Connection, Engine
import yaml

from app.p101_local_demo.bootstrap import insert_payloads, plan, validate_snapshot
from app.p101_local_demo.contracts import DATABASE, LocalDemoError, SqlRows
from app.p101_local_demo import provisioning, setup
from app.p101_local_demo.reader import IDENTITY_SQL
from app.p101_local_demo.setup_config import (
    CLUSTER, CORE_FILES, REVISION, ROOT, ROLES, SetupError, compose_files, parse_settings,
)


@pytest.fixture(autouse=True)
def prohibit_operations(monkeypatch):
    def forbidden(*a, **kw): raise AssertionError('No connection, SQL execution, external process or ML authorized')
    for cls, name in ((Engine, 'connect'), (Engine, 'raw_connection'), (Connection, 'execute'),
                      (Connection, 'exec_driver_sql')):
        monkeypatch.setattr(cls, name, forbidden)
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    monkeypatch.setattr(command, 'upgrade', forbidden)
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(socket, 'getaddrinfo', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    for key in list(os.environ):
        if key.startswith('PG'): monkeypatch.delenv(key)


@pytest.fixture
def config_data():
    # Fictitious private path and UUID are data only. No directory/secret is created.
    return dict(format='p101-local-settings-v1', private_root=str(ROOT.parent / 'p101-private-example'),
        host='127.0.0.1', port=55432, database=DATABASE, server_address='172.30.101.2', server_port=5432,
        network_subnet='172.30.101.0/28', instance_uuid='00000000-0000-4000-8000-000000000053',
        bootstrap_at='2026-10-26T00:00:00.000000Z',
        secret_files=dict(zip(ROLES, ('admin.password', 'owner.password', 'writer.password', 'reader.password'))))


@pytest.fixture
def settings(config_data): return parse_settings(config_data)


@pytest.fixture
def reference():
    return json.loads((ROOT / 'tests/p101_anomaly/fixtures/p101-temperature-v1.json').read_text(encoding='utf-8'))


def snapshot(prepared):
    payload = insert_payloads(prepared)
    parents = []
    ids = (101, 202, 303, 404)  # Test-only arbitrary SQL allocations, never production constants.
    for i, data in enumerate(payload['parents']):
        row = dict(data, id=ids[i])
        if i: row[('company_id', 'site_id', 'equipment_id')[i - 1]] = ids[i - 1]
        parents.append((row,))
    measurements = tuple(dict(r, id=501 + i, sensor_id=404) for i, r in enumerate(payload['measurements']))
    return SqlRows(*parents, measurements)


def closed(prepared):
    from app.p101_persistence.contracts import FIXTURE_SHA256
    return dict(fixture_sha256=FIXTURE_SHA256, bootstrap_closed=True, bootstrap_sha256=prepared.sha256)


def test_compose_is_independent_and_never_pulls():
    compose = yaml.safe_load((ROOT / 'infra/p101-local/compose.yaml').read_text())
    service = compose['services']['postgres']
    assert compose['name'] == CLUSTER
    assert service['ports'] == ['127.0.0.1:55432:5432']
    assert service['pull_policy'] == 'never'
    assert service['image'] == 'docker.io/library/postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317'
    assert service['healthcheck'] == {'disable': True}
    assert service['environment']['POSTGRES_PASSWORD_FILE'] == '/run/secrets/admin_password'
    assert 'env_file' not in service and 'build' not in service
    assert compose['volumes']['p101_data']['name'] == CLUSTER + '-data'
    assert compose['networks']['p101_net']['name'] == CLUSTER + '-net'
    assert compose['networks']['p101_net']['internal'] is False
    assert 'external' not in compose['volumes']['p101_data']
    assert not any('docker-entrypoint-initdb.d' in v for v in service['volumes'])


@pytest.mark.parametrize('field,value', [
    ('host', 'localhost'), ('host', '192.168.1.1'), ('port', 5433), ('port', True),
    ('database', 'industrial_predict_dev'), ('server_port', 55432), ('instance_uuid', 'bad'),
    ('instance_uuid', '00000000-0000-0000-0000-000000000000'),
    ('network_subnet', '172.18.0.0/24'), ('network_subnet', '8.8.8.0/24'),
    ('network_subnet', '172.30.101.0/16'), ('server_address', '172.30.101.1'),
    ('server_address', '172.30.101.15'), ('server_address', '127.0.0.1'),
    ('bootstrap_at', '2026-01-01T00:00:00.000000Z'), ('bootstrap_at', '2026-10-26T00:00:00Z'),
    ('private_root', str(ROOT)), ('private_root', str(ROOT / 'private')),
    ('private_root', 'relative'), ('private_root', str(ROOT.parent / '$private')),
    ('format', 'dev'), ('secret_files', {}),
])
def test_bad_configuration_rejected(config_data, field, value):
    config_data[field] = value
    with pytest.raises(SetupError): parse_settings(config_data)


def test_unknown_setting_refused(config_data):
    config_data['DATABASE_URL'] = 'forbidden'
    with pytest.raises(SetupError): parse_settings(config_data)


def test_config_and_private_render_are_pure(settings):
    generated = compose_files(settings)
    assert set(generated) == {'pg_hba.conf', 'compose.vars'}
    assert 'scram-sha-256' in generated['pg_hba.conf']
    assert 'host all all 0.0.0.0/0 reject' in generated['pg_hba.conf']
    assert 'trust' not in generated['pg_hba.conf']
    assert '172.30.101.0/28' in generated['pg_hba.conf']
    assert 'PASSWORD=' not in generated['compose.vars']
    assert 'admin.password' in generated['compose.vars']
    assert settings.destination(ROLES[3]).schema_revision == REVISION


@pytest.mark.parametrize('execute,instance', [(False, None), (True, None), (True, 'wrong'), (1, 'same')])
def test_no_execution_without_ack(settings, execute, instance):
    with pytest.raises(SetupError):
        with provisioning.transaction(settings, ROLES[0], execute=execute, instance=instance):
            pytest.fail('Must not reach transaction body')


def test_pg_environment_rejected_before_factory(settings, monkeypatch):
    monkeypatch.setenv('PGSERVICE', 'dev')
    with pytest.raises(SetupError):
        with provisioning.transaction(settings, ROLES[0], execute=True, instance=settings.instance_uuid):
            pytest.fail('Must not connect')


def test_no_secret_or_default_url_lookup(settings, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'unusable-forbidden')
    monkeypatch.setattr(provisioning, 'read_secret', lambda *a: (_ for _ in ()).throw(SetupError('Absent private secret')))
    with pytest.raises(SetupError):
        with provisioning.transaction(settings, ROLES[1], execute=True, instance=settings.instance_uuid):
            pytest.fail('Must not connect')


def fake_connection(settings, **overrides):
    row = dict(database=DATABASE, session_role=ROLES[1], effective_role=ROLES[1],
        server_address=settings.server_address, server_port=5432, cluster=CLUSTER, encoding='UTF8',
        isolation='read committed', no_protected_schema=True, no_memberships=True,
        rolsuper=False, rolcreatedb=False, rolcreaterole=False, rolreplication=False, rolbypassrls=False)
    row.update(overrides)
    driver = SimpleNamespace(info=SimpleNamespace(host=settings.host, port=settings.port,
        dbname=DATABASE, user=ROLES[1], get_parameters=lambda: {'sslmode': 'disable'}),
        pgconn=SimpleNamespace(ssl_in_use=False))
    return SimpleNamespace(engine=SimpleNamespace(url=URL.create('postgresql+psycopg', host=settings.host,
        port=settings.port, username=ROLES[1], database=DATABASE)),
        connection=SimpleNamespace(driver_connection=driver), in_transaction=lambda: True,
        execute=lambda statement: SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: row)))


def test_simulated_identity_acceptance_is_not_database_proof(settings):
    provisioning.validate_connection(fake_connection(settings), settings, ROLES[1])


@pytest.mark.parametrize('query', [provisioning.IDENTITY, IDENTITY_SQL], ids=['provisioning', 'reader'])
def test_server_address_is_projected_as_host_without_netmask(query):
    """Static SQL contract only; PostgreSQL host() semantics require the real read-only check."""
    sql = str(query)
    assert 'host(inet_server_addr()) AS server_address' in sql
    assert 'inet_server_addr()::text' not in sql


@pytest.mark.parametrize('field,value', [('database','industrial_predict_dev'), ('cluster','dev'),
    ('server_address','172.18.0.2'), ('server_port',5433), ('effective_role',ROLES[0]),
    ('server_address',None), ('server_address','invalid'), ('server_address','172.30.101.2/32'),
    ('rolsuper',True), ('rolcreaterole',True), ('no_memberships',False),
    ('no_protected_schema',False), ('encoding','LATIN1')])
def test_bad_simulated_identity(settings, field, value):
    with pytest.raises(SetupError):
        provisioning.validate_connection(fake_connection(settings, **{field:value}), settings, ROLES[1])


def test_wrong_transport_stops_before_identity_select(settings):
    connection = fake_connection(settings)
    connection.engine.url = connection.engine.url.set(database='industrial_predict_dev')
    connection.execute = lambda *a: pytest.fail('Identity SELECT must not run')
    with pytest.raises(SetupError): provisioning.validate_connection(connection, settings, ROLES[1])


def test_bootstrap_plan_exact_and_stable(settings, reference):
    original = deepcopy(reference)
    prepared = plan(settings, reference)
    data = json.loads(prepared.content_json)
    assert len(data['parents']) == 4 and len(data['measurements']) == 12
    assert [r['value'] for r in data['measurements']] == [65,63,67,64.5,65.5,64.5,65.5,65,65,65,65,70]
    assert data['parents'][2]['status'] == 'operational'
    assert all('id' not in r and not any(k.endswith('_id') for k in r) for r in data['parents'])
    assert all(r['quality'] == 'good' for r in data['measurements'])
    assert plan(settings, reference) == prepared
    assert reference == original
    values = insert_payloads(prepared)
    assert values['parents'][0]['created_at'].tzinfo is None
    assert values['measurements'][0]['timestamp'].utcoffset().total_seconds() == 0


def test_fixture_divergence_rejected(settings, reference):
    reference['observations'][0]['value'] = 99
    with pytest.raises(LocalDemoError): plan(settings, reference)


def test_instance_and_timestamp_participate_in_bootstrap_hash(settings, reference):
    original = plan(settings, reference)
    assert plan(replace(settings, bootstrap_at='2026-10-27T00:00:00.000000Z'), reference).sha256 != original.sha256
    assert plan(replace(settings, instance_uuid='00000000-0000-4000-8000-000000000054'), reference).sha256 != original.sha256


def test_exact_retry_preserves_real_allocated_ids(settings, reference):
    prepared = plan(settings, reference)
    rows = snapshot(prepared)
    result = validate_snapshot(prepared, rows, reference, closed(prepared))
    assert result.identities.company_id == 101
    assert dict(result.identities.measurements)['DEMO-M-012'] == 512


@pytest.mark.parametrize('field,value', [('bootstrap_closed',False), ('bootstrap_sha256','0'*64),
                                      ('fixture_sha256','0'*64)])
def test_bad_bootstrap_state(settings, reference, field, value):
    prepared = plan(settings, reference)
    state = closed(prepared)
    state[field] = value
    with pytest.raises(SetupError): validate_snapshot(prepared, snapshot(prepared), reference, state)


@pytest.mark.parametrize('change', ['missing','extra','value','parent','foreign_key'])
def test_divergent_snapshot_never_adopted(settings, reference, change):
    prepared = plan(settings, reference)
    rows = snapshot(prepared)
    if change == 'missing': rows = replace(rows, measurements=rows.measurements[:-1])
    if change == 'extra': rows = replace(rows, companies=rows.companies * 2)
    if change == 'parent': rows.companies[0]['name'] = 'Changed'
    if change == 'foreign_key': rows.sensors[0]['equipment_id'] = 1
    if change == 'value': rows.measurements[0]['value'] = 99
    with pytest.raises((SetupError, LocalDemoError)):
        validate_snapshot(prepared, rows, reference, closed(prepared))


def test_migration_sources_and_local_constraints_static():
    versions = ROOT / 'backend/migrations/versions'
    assert {p.name for p in versions.glob('*.py')} == set(CORE_FILES)
    spec = importlib.util.spec_from_file_location('local_revision', ROOT / 'backend/local_demo_migrations/versions/p101_local_0001.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # Definitions only; upgrade() is never called.
    assert module.down_revision == '09ac8101e9fe'
    assert module.revision == REVISION
    check = module.CONTENT_CHECK.format(instance_uuid='00000000-0000-4000-8000-000000000053')
    for clause in ('IS TRUE', 'sensor_id IS NOT NULL', 'measurement_id IS NOT NULL', 'score IN (0,1)',
                   'is_alert=(score=1)', 'level IS NULL', 'horizon_hours IS NULL', 'octet_length',
                   'p101-local-demo-details-v1', 'instance_uuid', 'idempotency_key', 'content_sha256'):
        assert clause in check
    source = Path(spec.origin).read_text()
    assert "unique=True, schema='public', postgresql_where=sa.text(PROFILE)" in source
    assert 'INSERT INTO public.prediction_records' not in source
    with pytest.raises(SetupError): module.downgrade()
    config = provisioning.alembic_config(object(), None)
    graph = ScriptDirectory.from_config(config)
    assert graph.get_heads() == [REVISION]
    assert len(list(graph.walk_revisions())) == 10


def test_isolated_env_and_no_ml_or_dev_imports():
    paths = list((ROOT / 'backend/app/p101_local_demo').glob('*.py'))
    paths += [ROOT / 'backend/local_demo_migrations/env.py']
    for path in paths:
        if path.name == 'processing.py': continue  # Existing ML5.2 calculation entrypoint, unchanged.
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source)
        modules = [node.module or '' for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert not any(m.startswith(('app.core', 'app.models', 'app.p101_postgres', 'dotenv')) for m in modules)
        assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id in ('evaluate', 'load_dotenv') for n in ast.walk(tree))
    env = (ROOT / 'backend/local_demo_migrations/env.py').read_text()
    assert env.index('validate_connection(connection') < env.index('SET LOCAL search_path')
    assert 'engine_from_config' not in env and 'create_engine' not in env


def test_cli_refusal_no_private_files_or_connections(monkeypatch, settings):
    monkeypatch.setattr(setup, 'load_settings', lambda path: settings)
    monkeypatch.setattr(setup, 'render', lambda *a: pytest.fail('No file generation allowed'))
    for operation in ('render','roles','migrate','bootstrap','seal','verify'):
        assert setup.main(['--config','fictitious.json',operation]) == 1
    assert setup.main(['--config','fictitious.json','check-config']) == 0


@pytest.mark.parametrize('wrong', ['uuid','revision','multiple','singleton'])
def test_marker_mismatch_refused_before_mutation(settings, wrong):
    state = dict(instance_uuid=settings.instance_uuid, purpose='local-p101-functional-demo',
                 database_name=DATABASE, schema_revision=REVISION, singleton=True)
    if wrong == 'uuid': state['instance_uuid'] = '00000000-0000-4000-8000-000000000099'
    if wrong == 'revision': state['schema_revision'] = 'other'
    if wrong == 'singleton': state['singleton'] = False
    rows = [state] * (2 if wrong == 'multiple' else 1)
    result = SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: rows))
    connection = SimpleNamespace(execute=lambda statement: result)
    with pytest.raises(SetupError): provisioning.marker(connection, settings)


@pytest.mark.parametrize('fail_at', ['body','commit','none'])
def test_transaction_boundary_simulation_only(settings, monkeypatch, fail_at):
    events = []
    class Transaction:
        def __enter__(self): events.append('begin')
        def __exit__(self, typ, value, tb):
            events.append('rollback' if typ else 'commit')
            if fail_at == 'commit': raise RuntimeError('Simulated lost commit response')
    class FakeConnection:
        def __enter__(self): return self
        def __exit__(self, *a): events.append('close')
        def begin(self): return Transaction()
    class FakeEngine:
        def connect(self): events.append('connect'); return FakeConnection()
        def dispose(self): events.append('dispose')
    captured = {}
    def factory(url, **kwargs):
        captured.update(url=url, kwargs=kwargs)
        return FakeEngine()
    monkeypatch.setattr(provisioning, 'read_secret', lambda *a: 'test-only-placeholder-not-an-actual-secret')
    monkeypatch.setattr(provisioning, 'create_engine', factory)
    monkeypatch.setattr(provisioning, 'validate_connection', lambda *a: events.append('guard'))
    def operation():
        with provisioning.transaction(settings, ROLES[1], execute=True, instance=settings.instance_uuid):
            events.append('body')
            if fail_at == 'body': raise RuntimeError('Simulated operation refusal')
    if fail_at == 'none': operation()
    else:
        with pytest.raises(SetupError, match='commit may be uncertain'): operation()
    assert events[:4] == ['connect','begin','guard','body']
    assert events[-2:] == ['close','dispose']
    assert events[4] == ('rollback' if fail_at == 'body' else 'commit')
    assert captured['url'].database == DATABASE
    assert captured['kwargs']['connect_args']['sslmode'] == 'disable'
    assert captured['kwargs']['hide_parameters'] is True
