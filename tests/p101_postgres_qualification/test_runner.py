"""New runner components only; all persistence observations are synthetic."""

from copy import deepcopy
from dataclasses import replace
from hashlib import sha256
import json
from unittest.mock import Mock

import pytest

from app import general_migrations as g
from b2b_postgres_qualification.contracts import Rejected, ExecutionDisabled, Publication
from b2b_postgres_qualification.test_contracts import campaign
from p101_postgres_qualification import plans as p, scenario as s, runner as r


WRITER = '44444444-4444-4444-8444-444444444444'
READER = '55555555-5555-4555-8555-555555555555'


@pytest.fixture(autouse=True)
def no_external_io(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Real I/O/execution forbidden')
    for name in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection',
                 'socket.getaddrinfo', 'subprocess.run', 'subprocess.Popen', 'os.system',
                 'psycopg.connect', 'psycopg.Connection.connect', 'sqlalchemy.create_engine',
                 'sqlalchemy.engine.Engine.connect', 'alembic.command.upgrade'):
        monkeypatch.setattr(name, forbidden)


@pytest.fixture
def ids():
    return s.FixtureIds(101, 202, 303, 404, tuple(range(1, 12)))


@pytest.fixture
def operation(campaign, ids):
    return s.prepare_operation(campaign, ids, expected_campaign=campaign)


def test_exact_fourteen_sources_order_hashes_and_inert_declarations(campaign):
    plan = p.prepare_migrations(campaign, expected_campaign=campaign)
    assert len(plan.publications) == len(plan.declarations) == 14
    assert plan.initial_revision is None and plan.final_revision == 'p101_0001_operations'
    assert tuple(x.revision for x in plan.publications[:9]) == g.HISTORICAL_CHAIN
    assert plan.publications[-1] == p.P101
    assert len(plan.source_snapshot_sha256) == 64
    assert not plan.execution_authorized and not plan.real_attested
    assert 'p101_operations_prediction_matches' in str(plan.declarations[-1])


@pytest.mark.parametrize('fault', ['reverse', 'missing', 'unknown', 'hash', 'parent'])
def test_unknown_or_changed_migration_plan_refused(campaign, monkeypatch, fault):
    values = p.PUBLICATIONS
    if fault == 'reverse': values = tuple(reversed(values))
    if fault == 'missing': values = values[:-1]
    if fault == 'unknown': values = (*values, Publication('unknown', values[-1].revision, 'x.py', 'f' * 64))
    if fault in ('hash', 'parent'):
        values = (*values[:-1], replace(values[-1], **({'sha256': 'f' * 64} if fault == 'hash' else {'parent': None})))
    inspect = Mock(side_effect=AssertionError('Must refuse before source access'))
    monkeypatch.setattr(g, 'inspect_sources', inspect)
    with pytest.raises(Rejected):
        p.prepare_migrations(campaign, expected_campaign=campaign, publications=values)
    inspect.assert_not_called()


def test_actual_source_tamper_is_rejected_without_revision_import(campaign, monkeypatch):
    original = g._read
    def changed(path):
        source = original(path)
        return source + '\n# altered publication\n' if path.name == 'p101_0001_operations.py' else source
    monkeypatch.setattr(g, '_read', changed)
    with pytest.raises(Rejected): p.prepare_migrations(campaign, expected_campaign=campaign)


@pytest.mark.parametrize('changes', [dict(database='industrial_predict_dev'),
    dict(host='localhost'), dict(subnet='172.30.91.0/28'), dict(instance_id='fb3284bd-fb7b-4c22-b620-96a1564b1d0c'),
    dict(instance_id='77777777-7777-4777-8777-777777777777')])
def test_unapproved_or_excluded_destination(campaign, changes):
    unknown = replace(campaign, **changes)
    with pytest.raises(Rejected): p.prepare_migrations(unknown, expected_campaign=campaign)


def empty_identity(campaign):
    return dict(database=campaign.database, host=campaign.host, address=campaign.server_address,
        port=5432, cluster=campaign.cluster_name, instance=campaign.instance_id, version=170010,
        role=campaign.roles[1], dev_marker=None, sslmode='verify-full', ca_sha256=campaign.ca_sha256)


def test_empty_database_declaration_is_not_live_evidence(campaign):
    counts = dict(p.EMPTY_COUNTS)
    assert len(p.review_empty_declaration(campaign, expected_campaign=campaign,
        identity=empty_identity(campaign), counts=counts, revision=None)) == 64
    for key in counts:
        with pytest.raises(Rejected):
            p.review_empty_declaration(campaign, expected_campaign=campaign,
                identity=empty_identity(campaign), counts=counts | {key: counts[key] + 1}, revision=None)
    with pytest.raises(Rejected):
        p.review_empty_declaration(campaign, expected_campaign=campaign,
            identity=empty_identity(campaign), counts=counts, revision='09ac8101e9fe')


def catalogue():
    constraints = [dict(name=name, type=kind, validated=True, definition='synthetic definition',
        deferrable=kind == 'f', deferred=kind == 'f') for name, kind in p.P101_CONSTRAINTS.items()]
    return dict(revision='p101_0001_operations', columns=[{'synthetic': True}], constraints=constraints,
        indexes=[{'synthetic': True}], sequences=[{'synthetic': True}],
        ownership=[{'synthetic': True}], acl=[{'synthetic': True}],
        functions=[dict(name=name, security_definer=False, search_path='pg_catalog, pg_temp') for name in p.P101_FUNCTIONS],
        triggers=[dict(name=name, enabled='O', deferrable=True, deferred=True) for name in p.P101_TRIGGERS])


def test_catalogue_requires_independent_baseline_and_complete_sections():
    data = catalogue()
    digest = p.fingerprint(data)
    assert p.review_catalogue_declaration(data, expected_sha256=digest) == digest
    data['constraints'][0]['definition'] = 'changed'
    with pytest.raises(Rejected): p.review_catalogue_declaration(data, expected_sha256=digest)
    data = catalogue()
    data['constraints'][0]['validated'] = False
    with pytest.raises(Rejected): p.review_catalogue_declaration(data, expected_sha256=p.fingerprint(data))
    data = catalogue()
    del data['acl']
    with pytest.raises(Rejected): p.review_catalogue_declaration(data, expected_sha256=p.fingerprint(data))


def test_seed_uses_returned_ids_and_exact_daily_fixture(campaign):
    steps = s.seed_plan(campaign, expected_campaign=campaign)
    assert len(steps) == 15
    assert tuple(step.returns for step in steps[:4]) == ('company', 'site', 'equipment', 'sensor')
    assert steps[1].parameters[3] == s.Reference('company')
    assert all(step.sql.count('%s') == len(step.parameters) for step in steps)
    assert all('RETURNING id' in step.sql for step in steps)
    assert not any('prediction_records' in step.sql or 'UPDATE' in step.sql for step in steps)


def test_operation_uses_existing_evaluator_and_canonical_result(operation, campaign):
    computed = operation.computed
    assert computed.score == 1 and computed.is_alert is True
    assert computed.reference_ids == tuple(range(1, 11))
    assert computed.target.measurement_id == 11
    assert computed.provenance.synthetic is True
    assert operation.actor[1] == 'https://qualification.invalid'
    assert sha256(computed.details_json.encode()).hexdigest() == computed.details_sha256
    key = sha256(b'[101,303,404,11,"statistical_deviation","p101-dev-stat-v1"]').hexdigest()
    assert operation.key == key and len(computed.details_json.encode()) <= 6000
    assert not operation.execution_authorized


def test_pair_plan_reserves_before_prediction_and_single_commit(campaign, operation):
    steps = s.pair_plan(campaign, operation, expected_campaign=campaign)
    assert steps[0].sql == 'BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE'
    assert "pg_get_serial_sequence('public.prediction_records','id')" in steps[2].sql
    assert steps[3].sql.startswith('INSERT INTO public.p101_prediction_operations')
    assert steps[3].returns == 'operation_id'
    assert steps[4].sql.startswith('INSERT INTO public.prediction_records')
    assert s.Reference('prediction_id') in steps[3].parameters
    assert s.Reference('operation_id') in steps[4].parameters
    assert sum(step.sql == 'COMMIT' for step in steps) == 1 and steps[-1].sql == 'COMMIT'
    assert not any('UPDATE ' in step.sql or 'ON CONFLICT' in step.sql for step in steps)


@pytest.mark.parametrize('change', [dict(key='f' * 64), dict(actor=(True, 'x', 'y'))])
def test_forged_operation_refused(campaign, operation, change):
    with pytest.raises(Rejected): s.pair_plan(campaign, replace(operation, **change), expected_campaign=campaign)


def test_forged_boolean_score_does_not_equal_integer(campaign, operation):
    forged = replace(operation, computed=replace(operation.computed, score=True))
    with pytest.raises(Rejected): s.pair_plan(campaign, forged, expected_campaign=campaign)


def test_confirmed_simulation_and_independent_observation(campaign, operation):
    store = s.OfflineScenario(campaign, expected_campaign=campaign)
    assert store.rehearse(operation, prediction_id=501, operation_id=601) == 'simulated_commit_confirmed'
    rows = store.observe()
    assert rows[0][0]['prediction_id'] == rows[0][1]['id'] == 501
    assert rows[0][1]['p101_operation_id'] == rows[0][0]['id'] == 601
    assert len(s.review_pair(campaign, operation, expected_campaign=campaign,
        writer_connection_id=WRITER, reader_connection_id=READER, rows=rows)) == 64
    rows[0][0]['score'] = 0
    assert store.observe()[0][0]['score'] == 1  # Separate copies, no simulated DB claim.


def test_json_observation_normalization_preserves_exact_journal_text(campaign, operation):
    store = s.OfflineScenario(campaign, expected_campaign=campaign)
    store.rehearse(operation, prediction_id=501, operation_id=601)
    journal, prediction = store.observe()[0]
    raw = json.loads(json.dumps([dict(operation=journal, prediction=prediction)], default=lambda value: value.isoformat()))
    raw[0]['prediction']['score'] = 1  # PostgreSQL JSON may encode a double as an integer token.
    normalized = s.normalize_pair_observation(raw)
    assert normalized[0][0]['result_details_json'] == operation.computed.details_json
    assert s.review_pair(campaign, operation, expected_campaign=campaign,
        writer_connection_id=WRITER, reader_connection_id=READER, rows=normalized)
    raw[0]['operation']['target_at'] = '2026-04-11T12:00:00'
    with pytest.raises(Rejected): s.normalize_pair_observation(raw)


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'orphan', 'crossed', 'hash', 'details', 'boolean'])
def test_independent_result_must_be_one_exact_complete_pair(campaign, operation, fault):
    store = s.OfflineScenario(campaign, expected_campaign=campaign)
    store.rehearse(operation, prediction_id=501, operation_id=601)
    rows = store.observe()
    if fault == 'missing': rows = ()
    if fault == 'duplicate': rows = rows * 2
    if fault == 'orphan': rows = ((rows[0][0], None),)
    if fault == 'crossed': rows[0][1]['p101_operation_id'] = 602
    if fault == 'hash': rows[0][0]['result_sha256'] = 'f' * 64
    if fault == 'details': rows[0][1]['details']['synthetic'] = False
    if fault == 'boolean': rows[0][0]['score'] = True
    with pytest.raises(Rejected):
        s.review_pair(campaign, operation, expected_campaign=campaign,
            writer_connection_id=WRITER, reader_connection_id=READER, rows=rows)


@pytest.mark.parametrize('ack,rows', [('lost_before_commit', 0), ('lost_after_commit', 1)])
def test_uncertain_commit_never_retried_or_inferred_from_absence(campaign, operation, ack, rows):
    store = s.OfflineScenario(campaign, expected_campaign=campaign)
    assert store.rehearse(operation, prediction_id=501, operation_id=601, acknowledgement=ack) == 'uncertain'
    assert len(store.observe()) == rows
    for _ in range(2):
        with pytest.raises(Rejected): store.rehearse(operation, prediction_id=502, operation_id=602)
    assert len(store.observe()) == rows


def test_same_connection_is_not_an_independent_read(campaign, operation):
    with pytest.raises(Rejected):
        s.review_pair(campaign, operation, expected_campaign=campaign,
            writer_connection_id=WRITER, reader_connection_id=WRITER, rows=())


def test_every_live_entry_point_refuses_before_callbacks_or_sql():
    poison = Mock(side_effect=AssertionError('Must not be invoked'))
    for function in (p.request_migration_execution, s.request_scenario_execution, r.request_build):
        with pytest.raises(ExecutionDisabled): function(connection=poison, approval=poison, enabled=True)
    for action in ('build', 'migrate', 'scenario', 'verify'):
        with pytest.raises(ExecutionDisabled): r.main([action])
    poison.assert_not_called()
    assert not poison.mock_calls


def test_runner_reports_real_blockers_and_no_ambient_destination(capsys):
    assert r.main(['report']) == 0
    report = json.loads(capsys.readouterr().out)
    assert not report['execution_enabled'] and not report['build_enabled'] and not report['real_attested']
    assert len(report['revisions']) == 14 and len(report['build_blockers']) == 4
    lock = json.loads(r.DEPENDENCIES.read_text())
    assert lock['base_image'] is None and lock['wheel_artifacts'] == []
    assert lock['runtime_packages']['pandas'] == '3.0.6'


def test_explicit_source_context_excludes_business_entrypoints_and_preserves_sources(campaign, operation):
    before = r.source_manifest()
    paths = {entry['path'] for entry in before}
    assert len(paths) == len(r.SOURCE_PATHS)
    assert not any('/services/' in path or '/api/' in path or path.startswith('frontend/') for path in paths)
    assert 'tests/b2b_postgres_qualification/transport.py' in paths
    assert not any('test_' in path for path in paths)
    p.prepare_migrations(campaign, expected_campaign=campaign)
    s.pair_plan(campaign, operation, expected_campaign=campaign)
    assert r.source_manifest() == before
