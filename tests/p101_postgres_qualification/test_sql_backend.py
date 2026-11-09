"""EXEC-2 single offline campaign. Responses are data, never a real SQL server."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import json
import traceback
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from psycopg.pq import TransactionStatus as TS

from b2b_postgres_qualification import collectors
from b2b_postgres_qualification.contracts import Rejected, ExecutionDisabled
from b2b_postgres_qualification.test_authority_evidence import NOW, certificates, campaign, policy, base_campaign
from p101_postgres_qualification import execution as ex, plans, scenario as s, sql_backend as db
from p101_postgres_qualification.offline_dbapi import OfflineChannelPool, ScriptedConnection, Response
from p101_postgres_qualification.test_execution import no_live_operations, release, case, signed


def json_row(value):
    return json.loads(json.dumps(value, default=lambda obj: obj.isoformat() if type(obj) is datetime else obj))


def catalog_data():
    # Independent synthetic baseline; deliberately NOT an actual approved schema baseline.
    constraints = [dict(schema='public', table='synthetic', name=name, type=kind, validated=True,
        deferrable=kind == 'f', deferred=kind == 'f', definition='synthetic')
        for name, kind in plans.P101_CONSTRAINTS.items()]
    functions = [dict(name=name, security_definer=False, search_path='pg_catalog, pg_temp',
        config=['search_path=pg_catalog, pg_temp'], definition='synthetic') for name in plans.P101_FUNCTIONS]
    triggers = [dict(table='synthetic', name=name, enabled='O', deferrable=True, deferred=True,
        definition='synthetic') for name in plans.P101_TRIGGERS]
    return dict(revision='p101_0001_operations', constraints=constraints, functions=functions,
        triggers=triggers, **{name: [dict(synthetic=True)]
            for name in ('columns', 'indexes', 'sequences', 'ownership', 'acl')})


def script_catalog(raw, cat):
    raw.add(collectors.REVISION_SQL, None, Response((dict(version_num=cat['revision']),)))
    raw.add(plans.CATALOG_SQL, None, Response(tuple(dict(schema_name=row['schema'], relname=row['table'],
        conname=row['name'], contype=row['type'], convalidated=row['validated'],
        condeferrable=row['deferrable'], condeferred=row['deferred'], definition=row['definition'])
        for row in cat['constraints'])))
    raw.add(plans.FUNCTIONS_SQL, None, Response(tuple(dict(proname=row['name'],
        prosecdef=row['security_definer'], proconfig=row['config'], definition=row['definition'])
        for row in cat['functions'])))
    raw.add(plans.TRIGGERS_SQL, None, Response(tuple(dict(relname=row['table'], tgname=row['name'],
        tgenabled=row['enabled'], tgdeferrable=row['deferrable'], tginitdeferred=row['deferred'],
        definition=row['definition']) for row in cat['triggers'])))
    for name, sql in (('columns', db.COLUMNS_SQL), ('indexes', db.INDEXES_SQL),
                      ('sequences', db.SEQUENCES_SQL), ('ownership', db.OWNERS_SQL), ('acl', db.ACL_SQL)):
        raw.add(sql, None, Response(tuple(cat[name])))


def script_channel(campaign, certificate, pid, role, readonly):
    raw = ScriptedConnection(pid, certificate, campaign.host)
    identity = dict(database=campaign.database, session_role=role, role=role,
        address=campaign.server_address, port=campaign.port, version=str(campaign.server_version_num),
        cluster=campaign.cluster_name, instance=campaign.instance_id, dev_marker=None,
        read_only='on' if readonly else 'off', default_read_only='on' if readonly else 'off',
        pid=pid, elevated=False)
    raw.add(collectors.IDENTITY_SQL, None, Response((identity,)))
    raw.add(db.BEGIN_RO if readonly else db.BEGIN_RW, None, Response(end_status=TS.INTRANS))
    for sql in db.SET_TIMEOUTS:
        raw.add(sql, None, Response())
    raw.add(db.TRANSACTION_SQL, None, Response((dict(isolation='repeatable read' if readonly else 'serializable',
        read_only='on' if readonly else 'off', pid=pid),)))
    raw.add('COMMIT', None, Response(end_status=TS.IDLE, command_tag='COMMIT'))
    raw.add('ROLLBACK', None, Response(end_status=TS.IDLE, command_tag='ROLLBACK'))
    return raw


@pytest.fixture
def sqlcase(case, certificates):
    def prepare(operation='first-pair'):
        c, release = case.campaign, case.backend.release
        writer = script_channel(c, certificates[1](c.host), 1001,
            c.roles[1 if operation == 'migrate' else 2], False)
        reader = script_channel(c, certificates[1](c.host), 1002, c.roles[3], True)
        cat = catalog_data()
        for raw in (writer, reader):
            script_catalog(raw, cat)
        case.executor.catalogue_sha256 = plans.fingerprint(cat)
        if operation == 'migrate':
            writer.add(plans.EMPTY_SQL, None, Response((dict(plans.EMPTY_COUNTS),)))
            writer.add(release.version_create, None, Response())
            for revision, version in zip(release.revisions, release.version_steps):
                for sql in revision.statements:
                    writer.add(sql, None, Response())
                writer.add(version, None, Response(rowcount=1))
        else:
            writer.add(db.LOCK_SOURCES, None, Response())
            writer.add(db.BUSINESS_SQL, None, Response((dict.fromkeys(db.TABLES, 0),)))
            values = {}
            for index, original in enumerate(s.seed_plan(c, expected_campaign=c), 1):
                params = tuple(values[v.name] if type(v) is s.Reference else v for v in original.parameters)
                values[original.returns] = index
                writer.add(original.sql, params, Response((dict(id=index),), rowcount=1))
                table = original.sql.split('public.', 1)[1].split(' ', 1)[0]
                columns = original.sql.split('(', 1)[1].split(')', 1)[0].split(',')
                record = dict(zip(columns, params)) | dict(id=index)
                writer.add(db.SEED_SELECTS[table], (index,), Response((dict(record=json_row(record)),)))
            ids = s.FixtureIds(values['company'], values['site'], values['equipment'], values['sensor'],
                tuple(values[f'measurement_{index}'] for index in range(11)))
            pair = s.prepare_operation(c, ids, expected_campaign=c)
            for original in s.pair_plan(c, pair, expected_campaign=c)[1:-1]:
                params = tuple(values[v.name] if type(v) is s.Reference else v for v in original.parameters)
                if original.returns:
                    identifier = 501 if original.returns == 'prediction_id' else 601
                    values[original.returns] = identifier
                    response = Response((dict(id=identifier),), rowcount=1)
                else:
                    response = Response(rowcount=1 if original.sql.startswith('INSERT ') else -1)
                writer.add(original.sql, params or None, response)
            journal, prediction = s._rows(pair, 501, 601)
            for raw in (writer, reader):
                raw.add(s.PAIR_SQL, (pair.key,), Response((dict(operation=json_row(journal), prediction=json_row(prediction)),)))
        backend = db.PostgresBackend(c, case.policy, expected_campaign=c, resources=case.executor.resources,
            release=release, operation=operation, connector=OfflineChannelPool((writer, reader)), clock=lambda: NOW)
        return SimpleNamespace(case=case, backend=backend, writer=writer, reader=reader,
            operation=operation, pair=pair if operation == 'first-pair' else None)
    return prepare


def run(item):
    intent, signature = signed(item.case, item.operation)
    return item.case.executor.run_simulated(item.backend, intent, signature)


def commands(raw):
    return [sql for sql, params in raw.events]


def test_frozen_migrations_native_ddl_and_observer(sqlcase):
    item = sqlcase('migrate')
    report = run(item)
    assert report.status == 'simulated_commit_confirmed'
    assert report.commit_status == 'confirmed' and not report.cleanup_failed
    ddl = commands(item.writer)
    expected = [item.backend.release.version_create]
    for revision, version in zip(item.backend.release.revisions, item.backend.release.version_steps):
        expected.extend((*revision.statements, version))
    start = ddl.index(expected[0])
    assert ddl[start:start + len(expected)] == expected
    assert all(params is None for sql, params in item.writer.events if sql in expected)
    assert any('%ROWTYPE' in sql and '%%ROWTYPE' not in sql for sql in expected)
    assert db.BEGIN_RO in commands(item.reader) and ddl.count('COMMIT') == 1
    assert all(raw.close_calls == 1 for raw in (item.writer, item.reader))
    assert not report.real_attested and not report.authenticated


def test_atomic_pair_and_full_sql_observation(sqlcase):
    item = sqlcase()
    report = run(item)
    assert report.status == 'simulated_commit_confirmed' and report.commit_status == 'confirmed'
    assert report.operation_key == item.pair.key
    sql = commands(item.writer)
    assert sql[1] == db.BEGIN_RW and db.BEGIN_RO in commands(item.reader)
    assert sum(q.startswith('INSERT ') for q in sql) == 17
    assert sql.index('SET CONSTRAINTS ALL IMMEDIATE') < sql.index('COMMIT')
    assert sum(q.startswith('SELECT row_to_json(t)') for q in sql) == 15
    assert commands(item.reader).count(s.PAIR_SQL) == 1
    assert sql.count('COMMIT') == 1 and 'COMMIT' not in commands(item.reader)


@pytest.mark.parametrize('sqlstate,status,commit', [('23503', 'simulated_rollback_confirmed', 'rejected'),
    ('40001', 'simulated_rollback_confirmed', 'rejected'), ('08006', 'uncertain', 'uncertain'),
    ('XX000', 'uncertain', 'uncertain')])
def test_commit_classification_no_retry(sqlcase, sqlstate, status, commit):
    item = sqlcase()
    item.writer.add('COMMIT', None, Response(sqlstate=sqlstate, end_status=TS.IDLE))
    report = run(item)
    assert (report.status, report.commit_status) == (status, commit)
    assert report.operation_key == item.pair.key
    intent, signature = signed(item.case, 'first-pair')
    with pytest.raises(Rejected): item.case.executor.run_simulated(item.backend, intent, signature)
    assert commands(item.writer).count('COMMIT') == 1
    assert 'ROLLBACK' not in commands(item.writer)
    assert not item.reader.events


@pytest.mark.parametrize('end_status', [TS.IDLE, TS.UNKNOWN])
def test_lost_commit_ack_is_never_retried_or_inferred_from_rollback(sqlcase, end_status):
    item = sqlcase()
    item.writer.add('COMMIT', None, Response(lost_ack=True, end_status=end_status))
    report = run(item)
    assert report.status == report.commit_status == 'uncertain'
    assert report.operation_key == item.pair.key and item.writer.close_calls == 1
    assert commands(item.writer).count('COMMIT') == 1 and 'ROLLBACK' not in commands(item.writer)
    intent, signature = signed(item.case, 'first-pair')
    with pytest.raises(Rejected): item.case.executor.run_simulated(item.backend, intent, signature)


def test_rollback_command_tag_is_never_a_commit_proof(sqlcase):
    item = sqlcase()
    item.writer.add('COMMIT', None, Response(end_status=TS.IDLE, command_tag='ROLLBACK'))
    report = run(item)
    assert report.status == report.commit_status == 'uncertain'
    assert commands(item.writer).count('COMMIT') == 1 and not item.reader.events


@pytest.mark.parametrize('fault', ['association', 'hash', 'content', 'missing', 'duplicate', 'identifier', 'both_ids'])
def test_observer_rejects_incomplete_or_inconsistent_content(sqlcase, fault):
    item = sqlcase()
    response = deepcopy(item.reader.responses[(s.PAIR_SQL, (item.pair.key,))][0].rows[0])
    if fault == 'association': response['prediction']['p101_operation_id'] += 1
    if fault == 'hash': response['operation']['result_sha256'] = 'f' * 64
    if fault == 'content': response['operation']['result_details_json'] += ' '
    if fault == 'missing': response['prediction'] = None
    if fault == 'identifier': response['prediction']['id'] += 1
    if fault == 'both_ids':
        response['prediction']['id'] += 1
        response['operation']['prediction_id'] += 1
    rows = (response, response) if fault == 'duplicate' else (response,)
    item.reader.add(s.PAIR_SQL, (item.pair.key,), Response(rows))
    report = run(item)
    assert report.status == 'simulated_commit_verification_failed' and report.commit_status == 'confirmed'
    assert commands(item.writer).count('COMMIT') == 1


@pytest.mark.parametrize('fault', ['same_raw', 'same_pid', 'same_socket', 'same_handle'])
def test_sessions_need_physical_and_server_independence(sqlcase, fault):
    item = sqlcase()
    if fault == 'same_raw': item.backend.connector = OfflineChannelPool((item.writer, item.writer))
    if fault == 'same_pid': item.reader.info.backend_pid = item.writer.info.backend_pid
    if fault == 'same_socket': item.reader.socket = item.writer.socket
    if fault == 'same_handle': item.reader.socket.handle = item.writer.socket.handle
    report = run(item)
    assert report.status == 'simulated_commit_verification_failed' and report.commit_status == 'confirmed'
    assert s.PAIR_SQL not in commands(item.reader)
    assert item.writer.close_calls == 1


@pytest.mark.parametrize('field,value', [('database', 'industrial_predict_dev'), ('cluster', 'wrong'),
    ('instance', 'unknown'), ('address', '127.0.0.1'), ('role', 'postgres'), ('elevated', True)])
def test_destination_identity_refused_before_begin(sqlcase, field, value):
    item = sqlcase()
    row = deepcopy(item.writer.responses[(collectors.IDENTITY_SQL, None)][0].rows[0])
    row[field] = value
    item.writer.add(collectors.IDENTITY_SQL, None, Response((row,)))
    report = run(item)
    assert report.commit_status == 'not_attempted' and db.BEGIN_RW not in commands(item.writer)
    assert item.writer.close_calls == 1


@pytest.mark.parametrize('fault', ['auth', 'unverified', 'host', 'san', 'ca', 'broken', 'connect'])
def test_channel_refusals_and_closure(sqlcase, certificates, fault):
    item = sqlcase()
    if fault == 'auth': item.writer.auth_method = 'trust'
    if fault == 'unverified': item.writer.tls_verified = False
    if fault == 'host': item.writer.verified_host = 'wrong.invalid'
    if fault == 'san': item.writer.socket.certificate = certificates[1]('wrong.invalid')
    if fault == 'ca': item.writer.socket.certificate = b'not-a-certificate'
    if fault == 'broken': item.writer.broken = True
    if fault == 'connect': item.backend.connector = OfflineChannelPool(())
    report = run(item)
    assert report.commit_status == 'not_attempted' and not item.writer.events
    assert item.writer.close_calls == (0 if fault == 'connect' else 1)


def test_sqlstate_error_sanitized_and_rollback(sqlcase):
    item = sqlcase()
    step = s.seed_plan(item.case.campaign, expected_campaign=item.case.campaign)[0]
    item.writer.add(step.sql, step.parameters, Response(sqlstate='23505', end_status=TS.INERROR))
    report = run(item)
    assert report.status == 'simulated_rollback_confirmed' and report.commit_status == 'not_attempted'
    assert 'COMMIT' not in commands(item.writer) and commands(item.writer).count('ROLLBACK') == 1
    assert 'PRIVATE' not in repr(report) and not report.execution_authorized


def test_driver_exception_does_not_survive_public_error(sqlcase):
    item = sqlcase()
    session = item.backend.open(item.case.campaign.roles[2], False)
    item.writer.add(collectors.IDENTITY_SQL, None, Response(sqlstate='28P01'))
    with pytest.raises(db.SqlFailure) as caught: item.backend.identity(session)
    assert caught.value.sqlstate == '28P01'
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert 'PRIVATE' not in ''.join(traceback.format_exception(caught.value))
    item.backend.close(session)


@pytest.mark.parametrize('fault', ['arbitrary', 'changed_parameters', 'order'])
def test_only_exact_next_frozen_statement_can_execute(sqlcase, fault):
    item = sqlcase()
    b, c = item.backend, item.case.campaign
    session = b.open(c.roles[2], False)
    b.begin(session)
    assert b.business_empty(session)
    first = s.seed_plan(c, expected_campaign=c)[0]
    step = s.Statement('DELETE FROM public.companies', ()) if fault == 'arbitrary' else first
    if fault == 'changed_parameters': step = replace(first, parameters=('wrong', *first.parameters[1:]))
    if fault == 'order': step = s.seed_plan(c, expected_campaign=c)[1]
    count = len(item.writer.events)
    with pytest.raises((Rejected, KeyError)): b.execute(session, step)
    assert len(item.writer.events) == count
    b.rollback(session)
    b.close(session)


def test_revision_order_cannot_be_changed_or_called_twice(sqlcase):
    item = sqlcase('migrate')
    b = item.backend
    session = b.open(item.case.campaign.roles[1], False)
    b.begin(session)
    b.start_migrations(session, b.release)
    count = len(item.writer.events)
    with pytest.raises(Rejected): b.apply_revision(session, b.release.revisions[1])
    assert len(item.writer.events) == count
    b.apply_revision(session, b.release.revisions[0])
    with pytest.raises(Rejected): b.apply_revision(session, b.release.revisions[0])
    b.rollback(session)
    b.close(session)


@pytest.mark.parametrize('fault', ['readonly', 'isolation', 'status', 'rowcount', 'seed', 'catalogue', 'nonempty'])
def test_transaction_and_source_checks_prevent_commit(sqlcase, fault):
    item = sqlcase()
    if fault in ('readonly', 'isolation'):
        row = dict(isolation='serializable', read_only='off', pid=1001)
        row['read_only' if fault == 'readonly' else 'isolation'] = 'on' if fault == 'readonly' else 'read committed'
        item.writer.add(db.TRANSACTION_SQL, None, Response((row,)))
    if fault == 'status': item.writer.add(db.BEGIN_RW, None, Response(end_status=TS.IDLE))
    if fault == 'rowcount':
        first = s.seed_plan(item.case.campaign, expected_campaign=item.case.campaign)[0]
        item.writer.add(first.sql, first.parameters, Response((dict(id=1),), rowcount=0))
    if fault == 'seed':
        item.writer.add(db.SEED_SELECTS['companies'], (1,), Response((dict(record=dict(id=1)),)))
    if fault == 'catalogue': item.writer.add(db.COLUMNS_SQL, None, Response((dict(changed=True),)))
    if fault == 'nonempty':
        counts = dict.fromkeys(db.TABLES, 0) | dict(measurements=1)
        item.writer.add(db.BUSINESS_SQL, None, Response((counts,)))
    report = run(item)
    assert report.commit_status == 'not_attempted' and 'COMMIT' not in commands(item.writer)
    assert item.writer.close_calls == 1


def test_close_failure_report_preserves_known_commit(sqlcase):
    item = sqlcase()
    item.writer.close_error = True
    report = run(item)
    assert report.commit_status == 'confirmed' and report.cleanup_failed
    assert item.writer.close_calls == 1


def test_live_paths_and_external_connectors_stay_closed(sqlcase):
    item = sqlcase()
    poison = Mock(side_effect=AssertionError('never touch'))
    with pytest.raises(ExecutionDisabled): item.case.executor.run_live(poison, approved=True)
    with pytest.raises(ExecutionDisabled): db.PsycopgBoundConnector().open(poison, sslmode='require')
    with pytest.raises(Rejected):
        db.PostgresBackend(item.case.campaign, item.case.policy, expected_campaign=item.case.campaign,
            resources=item.case.executor.resources, release=item.backend.release, operation='first-pair',
            connector=poison, clock=lambda: NOW)
    poison.assert_not_called()


def test_unapproved_resources_and_authorization_precede_connections(sqlcase):
    item = sqlcase()
    intent, signature = signed(item.case, 'first-pair')
    with pytest.raises(Rejected): item.case.executor.run_simulated(item.backend, intent, b'x' * 64)
    item.backend.resources['engine_id'] = 'unknown'
    with pytest.raises(Rejected): item.case.executor.run_simulated(item.backend, intent, signature)
    assert not item.backend.sessions and not item.writer.events


def test_unbounded_result_refused_and_readonly_cannot_write(sqlcase):
    item = sqlcase()
    b = item.backend
    b.connector = OfflineChannelPool((item.reader,))
    session = b.open(item.case.campaign.roles[3], True)
    b.begin(session)
    step = s.seed_plan(item.case.campaign, expected_campaign=item.case.campaign)[0]
    count = len(item.reader.events)
    with pytest.raises(Rejected): b.execute(session, step)
    assert len(item.reader.events) == count
    item.reader.add(collectors.IDENTITY_SQL, None, Response(({}, {}, {})))
    with pytest.raises(db.SqlFailure): b.identity(session)
    b.rollback(session)
    b.close(session)
