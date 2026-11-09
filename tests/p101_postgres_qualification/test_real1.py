"""REAL-1 offline wire/crypto/kernel tests. Never an actual PostgreSQL server."""

from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
import json
import ssl
import struct
import traceback

import pytest
from psycopg.pq import TransactionStatus as TS

from b2b_postgres_qualification import collectors, evidence, validation as v
from b2b_postgres_qualification.contracts import ExecutionDisabled, Rejected, Observation
from b2b_postgres_qualification.test_transport import ScriptedSocket, packet, PRIVATE
from b2b_postgres_qualification.test_transport import memory_handshake, tls_material
from p101_postgres_qualification import live_authority as la, wire_transport as wt, privileges, sql_backend as db
from p101_postgres_qualification import execution as ex, operator as operator_cli
from p101_postgres_qualification import resources as resource_profile
from p101_postgres_qualification.offline_dbapi import Response
from p101_postgres_qualification.test_sql_backend import sqlcase, script_catalog, catalog_data
from p101_postgres_qualification.test_execution import signed, case, release, no_live_operations
from b2b_postgres_qualification.test_authority_evidence import NOW, certificates, campaign, policy, base_campaign


def row_response(rows, tag, status):
    if not rows:
        return packet(b'n', b'') + packet(b'C', tag.encode() + b'\0') + packet(b'Z', status)
    columns, desc = [], struct.pack('!H', len(rows[0]))
    for name, value in rows[0].items():
        oid = 16 if type(value) is bool else 20 if type(value) is int else 701 if type(value) is float else 114 if type(value) in (dict, list) else 25
        columns.append((name, oid))
        desc += name.encode() + b'\0' + struct.pack('!IhIhih', 0, 0, oid, -1, -1, 0)
    result = packet(b'T', desc)
    for row in rows:
        body = struct.pack('!H', len(columns))
        for name, oid in columns:
            value = row[name]
            if value is None:
                body += struct.pack('!i', -1)
            else:
                text = json.dumps(value) if oid == 114 else ('t' if value else 'f') if oid == 16 else str(value)
                encoded = text.encode()
                body += struct.pack('!i', len(encoded)) + encoded
        result += packet(b'D', body)
    return result + packet(b'C', tag.encode() + b'\0') + packet(b'Z', status)


class ExtendedSocket(ScriptedSocket):
    def __init__(self, campaign, certificate, *, pid=103):
        super().__init__(campaign, certificate)
        self.script, self.status, self.handle, self.pid = {}, b'I', pid, pid
        self.query, self.params, self.fail_commit, self.corrupt = None, (), False, None

    def fileno(self):
        return -1 if self.closed else self.handle

    def sendall(self, data):
        if data[:1] not in (b'P', b'B', b'D', b'E', b'S'):
            super().sendall(data)
            if data[:1] == b'p' and hasattr(self, 'first') and b',p=' in data:
                old = packet(b'K', struct.pack('!II', 103, 0))
                self.input = self.input.replace(old, packet(b'K', struct.pack('!II', self.pid, 0)))
            return
        self.sent.append(data)
        kind, body = data[:1], data[5:]
        if kind == b'P':
            self.query = body[1:-3].decode()
            assert body[:1] == b'\0' and body[-3:] == b'\0\0\0'
        elif kind == b'B':
            assert body[:4] == b'\0\0\0\0'
            count, offset, params = struct.unpack('!H', body[4:6])[0], 6, []
            for _ in range(count):
                length = struct.unpack('!i', body[offset:offset+4])[0]
                offset += 4
                params.append(None if length == -1 else body[offset:offset+length].decode())
                offset += max(length, 0)
            assert body[offset:] == b'\0\0'
            self.params = tuple(params)
        elif kind == b'S':
            if self.query == 'COMMIT' and self.fail_commit:
                raise OSError('SYNTHETIC-PRIVATE-COMMIT-DIAGNOSTIC')
            entry = self.script.get((self.query, self.params))
            if self.query == 'SET default_transaction_read_only=off':
                entry = Response(command_tag='SET')
            if entry is None:
                raise AssertionError('Unexpected query: ' + self.query)
            response = entry[0] if type(entry) is list else entry
            if type(entry) is list and len(entry) > 1:
                entry.pop(0)
            if self.query.startswith('BEGIN '): self.status = b'T'
            if self.query in ('COMMIT', 'ROLLBACK'): self.status = b'I'
            if response.end_status is not None:
                self.status = {TS.IDLE: b'I', TS.INTRANS: b'T', TS.INERROR: b'E'}[response.end_status]
            if response.sqlstate:
                self.input += packet(b'E', b'SERROR\0C' + response.sqlstate.encode() + b'\0MPRIVATE-SERVER-DETAIL\0\0') + packet(b'Z', self.status)
                return
            tag = response.command_tag
            if tag is None:
                tag = 'SELECT ' + str(len(response.rows)) if self.query.startswith('SELECT ') else 'INSERT 0 1' if self.query.startswith('INSERT ') else 'UPDATE 1' if self.query.startswith('UPDATE ') else self.query.split()[0]
            stream = packet(b'1', b'') + packet(b'2', b'') + row_response(response.rows, tag, self.status)
            if self.corrupt is not None:
                stream = self.corrupt
            self.input += stream


def profile(kind):
    tables = []
    for name in (*privileges.TABLES, 'alembic_version', 'local_users'):
        tables.append(dict(name=name, sel=name != 'local_users', ins=kind == 'writer' and name in privileges.INSERT_TABLES,
            maintain=kind == 'writer' and name in privileges.TABLES, upd=False,
            **{'del': False, 'trunc': False, 'ref': False, 'trg': False}))
    return dict(memberships=0, schema_usage=True, schema_create=kind == 'migrator', database_create=False,
        database_temp=False, superuser=False, bypassrls=False, replication_control=False,
        replication_role='origin', owned=0, tables=tables,
        sequences=[dict(name=name + '_id_seq', usage=kind == 'writer', sel=False, upd=False)
            for name in sorted(privileges.INSERT_TABLES)])


def attach(monkeypatch, wires):
    sockets = iter(wires)
    monkeypatch.setattr(wt.socket, 'socket', lambda *args: next(sockets))
    def wrap(context, raw, **kwargs):
        assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname and not context.hostname_checks_common_name
        assert kwargs == dict(server_hostname=raw.campaign.host, do_handshake_on_connect=False)
        return raw
    monkeypatch.setattr(ssl.SSLContext, 'wrap_socket', wrap)


@pytest.fixture
def livecase(sqlcase, certificates, monkeypatch):
    def prepare(operation='first-pair'):
        item = sqlcase(operation)
        # OS/filesystem and artifact reproduction are EXPLICIT doubles in this test.
        monkeypatch.setattr(la, 'verify_registry', lambda root, *args: root)
        monkeypatch.setattr(la, 'verify_artifacts', lambda *args: args[1])
        item.case.executor.policy = replace(item.case.policy, image_id_sha256=la.POSTGRES_IMAGE_ID)
        item.case.policy = item.case.executor.policy
        registry = dict(volume=item.case.campaign.database + '_exec_registry',
            created_at=item.case.policy.volume_created_at.isoformat(), mount_target='/var/lib/p101-qualification')
        resources = ex.resource_inventory(item.case.campaign, item.case.policy, runner_image_id='3' * 64, registry=registry)
        item.case.executor.resources = resources
        intent, signature = signed(item.case, operation)
        # This fixture exercises only the SQL/TLS state machine on doubles. It
        # bypasses LiveGuard solely for those protocol tests and never claims a
        # Docker attestation or successful production authorization.
        real_guard_check = la.LiveGuard.check
        monkeypatch.setattr(la.LiveGuard, 'check', lambda self: None)
        c = item.case.campaign
        facts = resource_profile.facts(c, registry)
        obs = Observation('docker', c.campaign_id, v.destination_fingerprint(c), 'unverified_external',
            'p101-docker-cli', NOW, NOW, c.campaign_id, tuple(sorted(facts.items())))
        supplemental = dict(context_name=item.case.policy.context_name, endpoint_sha256=item.case.policy.endpoint_sha256,
            image_id_sha256=la.POSTGRES_IMAGE_ID, container_networks=c.network_id, volume_engine_id=c.engine_id,
            volume_driver='local', volume_scope='local', volume_created_at=item.case.policy.volume_created_at.isoformat(timespec='microseconds'))
        packet = evidence.EvidencePacket(obs, tuple(sorted(supplemental.items())))
        collection = collectors.DockerCollection(packet,
            collectors.ResourceLimits(resources['postgres_memory'], resources['nano_cpus'], 67108864),
            collectors.ResourceLimits(resources['runner_memory'], resources['nano_cpus'], 67108864), '3' * 64)
        receipt = la.prepare_readiness(item.case.executor, intent, collection=collection,
            artifact_sha256='f' * 64, registry_root=item.case.root)
        guard = la.LiveGuard(item.case.executor, intent, signature, receipt=receipt,
            receipt_signature=item.case.private.sign(la.readiness_bytes(receipt)), artifact_lock=item.case.root / 'not-a-real-lock.json')
        writer_role = c.roles[1] if operation == 'migrate' else c.database + '_p101_writer'
        wires = []
        for index, raw in enumerate((item.writer, item.reader)):
            wire = ExtendedSocket(c, raw.socket.certificate, pid=1001+index)
            for (query, params), responses in raw.responses.items():
                if query == db.LOCK_SOURCES:
                    continue
                if query == collectors.IDENTITY_SQL:
                    responses = deepcopy(responses)
                    if index == 0:
                        for response in responses:
                            response.rows[0].update(session_role=writer_role, role=writer_role)
                native, values = wt.bound(query, params)
                encoded = tuple(None if value is None else wt.encode(value)[4:].decode() for value in values)
                if query in db.SEED_SELECTS.values():
                    native = native.removesuffix(' FOR SHARE')
                if query == db.plans.FUNCTIONS_SQL:
                    native = db.LIVE_FUNCTIONS_SQL
                wire.script[(native, encoded)] = list(responses)
            wire.script[(privileges.SQL, ())] = Response((profile('observer' if index else 'migrator' if operation == 'migrate' else 'writer'),))
            wire.script[(db.LIVE_LOCK, ())] = Response()
            for grant in privileges.grant_plan(c)[1:]:
                wire.script[(grant, ())] = Response(command_tag='GRANT')
            wires.append(wire)
        attach(monkeypatch, wires)
        item.guard, item.receipt, item.wires = guard, receipt, wires
        item.real_guard_check = real_guard_check
        item.credentials = {writer_role: PRIVATE, c.roles[3]: PRIVATE}
        return item
    return prepare


@pytest.mark.parametrize('operation', ['migrate', 'first-pair'])
def test_real_entry_uses_wire_and_existing_kernel_only_on_doubles(livecase, operation):
    item = livecase(operation)
    report = item.case.executor.execute_approved(item.guard, credentials=item.credentials)
    assert report.status == 'commit_confirmed', report.status
    assert report.commit_status == 'confirmed' and not report.cleanup_failed and not report.recording_failed
    for wire in item.wires:
        assert wire.closed == 1
        assert PRIVATE.encode() not in b''.join(wire.sent)
    parses = [body[6:-3].decode() for body in item.wires[0].sent if body[:1] == b'P']
    assert parses.count('COMMIT') == 1
    if operation == 'first-pair':
        assert parses.index(db.LIVE_LOCK) < parses.index(db.TRANSACTION_SQL)
        assert parses.index('SET CONSTRAINTS ALL IMMEDIATE') < parses.index('COMMIT')
        assert report.operation_key == item.pair.key
    else:
        for grant in privileges.grant_plan(item.case.campaign)[1:]:
            assert grant in parses
    assert not report.real_attested  # This report cannot attest the offline test environment.


def test_lost_commit_ack_never_reopens_or_retries(livecase):
    item = livecase()
    item.wires[0].fail_commit = True
    report = item.case.executor.execute_approved(item.guard, credentials=item.credentials)
    assert report.status == report.commit_status == 'uncertain'
    assert report.operation_key == item.pair.key and not item.wires[1].sent
    with pytest.raises(Rejected): item.case.executor.execute_approved(item.guard, credentials=item.credentials)


@pytest.mark.parametrize('fault', ['receipt_signature', 'intent_signature', 'inventory', 'expired', 'registry', 'check', 'docker'])
def test_live_receipt_refusals_precede_socket(livecase, monkeypatch, fault):
    item = livecase()
    monkeypatch.setattr(la.LiveGuard, 'check', item.real_guard_check)
    receipt = deepcopy(item.receipt)
    signature, intent_signature = item.guard._receipt_signature, item.guard.signature
    if fault == 'receipt_signature': signature = b'x' * 64
    if fault == 'intent_signature': intent_signature = b'x' * 64
    if fault == 'inventory': receipt['inventory']['engine_id'] = 'wrong'
    if fault == 'expired': receipt['expires_at'] = (NOW-timedelta(seconds=1)).isoformat()
    if fault == 'registry': receipt['registry_sha256'] = '0' * 64
    if fault == 'check': receipt['checks'] = []
    if fault == 'docker': receipt['docker']['observation']['facts'] = []
    if fault not in ('receipt_signature', 'intent_signature'):
        signature = item.case.private.sign(la.readiness_bytes(receipt))
    with pytest.raises(Rejected):
        la.LiveGuard(item.case.executor, item.guard.intent, intent_signature, receipt=receipt,
            receipt_signature=signature, artifact_lock=item.guard.artifact_lock)
    assert not any(wire.sent for wire in item.wires)


@pytest.mark.parametrize('fault', ['signed_unverified', 'signed_claim', 'missing_provenance', 'divergent_provenance'])
def test_signed_docker_declarations_never_authorize_real_execution(livecase, monkeypatch, fault):
    item = livecase()
    monkeypatch.setattr(la.LiveGuard, 'check', item.real_guard_check)
    receipt = deepcopy(item.receipt)
    obs = receipt['docker']['observation']
    if fault == 'signed_unverified':
        obs['provenance'] = 'unverified_external'
    elif fault == 'signed_claim':
        # Even a correctly signed assertion of a stronger provenance is not a
        # collector attestation and remains blocked by the absent collector.
        obs['provenance'] = 'authenticated_collector'
    elif fault == 'missing_provenance':
        obs.pop('provenance')
    else:
        obs['provenance'] = 'authenticated_collector'
        obs['campaign_id'] = 'another-campaign'
    signature = item.case.private.sign(la.readiness_bytes(receipt))
    with pytest.raises(Rejected):
        la.LiveGuard(item.case.executor, item.guard.intent, item.guard.signature, receipt=receipt,
            receipt_signature=signature, artifact_lock=item.guard.artifact_lock)
    assert not any(wire.sent for wire in item.wires)


@pytest.mark.parametrize('fault', ['unverified', 'missing', 'campaign', 'resources'])
def test_collector_provenance_must_match_the_observation(livecase, monkeypatch, fault):
    item = livecase()
    monkeypatch.setattr(la.LiveGuard, 'check', item.real_guard_check)
    receipt = deepcopy(item.receipt)
    obs = receipt['docker']['observation']
    if fault == 'unverified':
        obs['provenance'] = 'unverified_external'
    elif fault == 'missing':
        obs.pop('provenance')
    elif fault == 'campaign':
        obs['campaign_id'] = 'another-campaign'
    else:
        receipt['inventory']['engine_id'] = 'another-engine'
    signature = item.case.private.sign(la.readiness_bytes(receipt))
    with pytest.raises(Rejected):
        la.LiveGuard(item.case.executor, item.guard.intent, item.guard.signature, receipt=receipt,
            receipt_signature=signature, artifact_lock=item.guard.artifact_lock)
    assert not any(wire.sent for wire in item.wires)


def test_connect_requires_consumed_authorization_not_favorable_flag(livecase):
    item = livecase()
    connector = wt.LiveConnector(item.guard, item.credentials)
    with pytest.raises(Exception): connector.open(item.case.campaign.database + '_p101_writer', False)
    assert not item.wires[0].sent
    with pytest.raises(ExecutionDisabled): item.case.executor.run_live(item.guard, approved=True)


def test_injected_resource_configuration_is_never_live_engine_evidence(livecase):
    item = livecase()
    backend = db.PostgresBackend(item.case.campaign, item.case.policy,
        expected_campaign=item.case.campaign, resources=item.case.executor.resources,
        release=item.case.backend.release, operation='first-pair',
        connector=wt.LiveConnector(item.guard, item.credentials), clock=lambda: NOW)
    with pytest.raises(ExecutionDisabled):
        backend.engine_inventory()
    assert not any(wire.sent for wire in item.wires)


@pytest.mark.parametrize('fault', ['database', 'auth', 'san', 'peer', 'signature'])
def test_single_channel_authentication_and_destination_refusals(livecase, fault):
    item = livecase()
    wire = item.wires[0]
    if fault == 'database':
        response = wire.script[(collectors.IDENTITY_SQL, ())][0]
        response.rows[0]['database'] = 'industrial_predict_dev'
    if fault == 'auth': wire.auth = 0
    if fault == 'san': wire.handshake_error = ssl.SSLCertVerificationError('PRIVATE TLS ERROR')
    if fault == 'peer': wire.getpeername = lambda: ('127.0.0.1', 5432)
    if fault == 'signature': wire.bad_signature = True
    report = item.case.executor.execute_approved(item.guard, credentials=item.credentials)
    assert report.commit_status == 'not_attempted'
    assert all(b'INSERT INTO' not in message for message in wire.sent)
    assert wire.closed == 1


def test_bound_parameters_never_enter_parse_text():
    hostile = "');DROP TABLE public.companies;--"
    sql, values = wt.bound('INSERT INTO public.companies (name) VALUES (%s)', (hostile,))
    assert hostile not in sql and sql.endswith('($1)') and wt.encode(values[0])[4:] == hostile.encode()
    native = 'CREATE FUNCTION x() RETURNS void AS $$ DECLARE r x%ROWTYPE; BEGIN RETURN; END; $$ LANGUAGE plpgsql;'
    assert wt.bound(native, None) == (native, ())
    with pytest.raises(Exception): wt.bound('SELECT %s,%s', ('one',))
    for value in (float('nan'), float('inf'), object(), 'nul\0'):
        with pytest.raises(Exception): wt.encode(value)


@pytest.mark.parametrize('stream', [packet(b'Z', b'I'), packet(b'1', b'x'), packet(b'G', b''),
    packet(b'1', b'') + packet(b'2', b'') + packet(b'n', b'') + packet(b'C', b'COMMIT\0') + packet(b'Z', b'?')])
def test_unexpected_protocol_closes_without_private_diagnostics(livecase, stream):
    item = livecase()
    item.wires[0].corrupt = stream
    report = item.case.executor.execute_approved(item.guard, credentials=item.credentials)
    assert report.commit_status == 'not_attempted' and item.wires[0].closed == 1
    assert 'PRIVATE' not in repr(report)


@pytest.mark.parametrize('kind', ['writer', 'observer'])
def test_profile_grants_are_limited_and_b2b_runtime_is_not_a_writer(campaign, kind):
    value = profile(kind)
    privileges.review(value, kind=kind)
    value['tables'][0]['upd'] = True
    with pytest.raises(Rejected): privileges.review(value, kind=kind)
    grants = '\n'.join(privileges.grant_plan(campaign))
    assert campaign.roles[2] not in grants and campaign.database + '_p101_writer' in grants
    assert 'GRANT UPDATE' not in grants and 'GRANT DELETE' not in grants


@pytest.mark.parametrize('field', ['superuser', 'bypassrls'])
def test_counting_role_must_be_nonprivileged_and_not_bypass_rls(field):
    value = profile('writer')
    value[field] = True
    with pytest.raises(Rejected):
        privileges.review(value, kind='writer')


@pytest.mark.parametrize('fault', ['enabled', 'forced', 'policy_hides_rows', 'missing_relation'])
def test_rls_catalogue_refuses_masking_or_incomplete_inventory(sqlcase, fault):
    item = sqlcase()
    rows = deepcopy(catalog_data()['rls'])
    if fault == 'enabled':
        rows[0]['row_security'] = True
    elif fault == 'forced':
        rows[0]['force_row_security'] = True
    elif fault == 'policy_hides_rows':
        rows[0]['policies'] = [dict(name='mask_existing_rows', permissive=True, command='r',
            roles=['p101_writer'], using='false', with_check='true')]
    else:
        rows.pop()
    item.writer.add(db.RLS_SQL, None, Response(tuple(rows)))
    session = item.backend.open(item.case.campaign.roles[2], False)
    item.backend.begin(session)
    before = len(item.writer.events)
    with pytest.raises(Rejected):
        item.backend.business_empty(session)
    assert db.BUSINESS_SQL not in [sql for sql, _ in item.writer.events[before:]]
    item.backend.rollback(session)
    item.backend.close(session)


def test_operator_default_never_loads_config_or_connects(monkeypatch, capsys):
    monkeypatch.setattr(operator_cli, 'load_admin', lambda *args: pytest.fail('No config at default action'))
    assert operator_cli.main([]) == 0
    assert json.loads(capsys.readouterr().out)['default_execution'] is False


def test_real_openssl_memory_binding_ca_and_san(tls_material, base_campaign):
    # OpenSSL performs a real in-memory TLS handshake. Still NO TCP/PostgreSQL.
    context = wt.infra._context(tls_material[0])
    peer = memory_handshake(context, tls_material[2], base_campaign.host)
    assert peer.getpeercert(binary_form=True) == tls_material[1]
    with pytest.raises(ssl.SSLCertVerificationError):
        memory_handshake(context, tls_material[2], 'wrong.invalid')
    with pytest.raises(ssl.SSLCertVerificationError):
        memory_handshake(ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT), tls_material[2], base_campaign.host)


def test_server_errors_and_notices_are_drained_and_sanitized(livecase):
    item = livecase()
    # An authenticated SQL rejection before COMMIT remains rollbackable.
    query = next(key for key in item.wires[0].script if key[0].startswith('INSERT INTO public.companies'))
    item.wires[0].script[query] = Response(sqlstate='23505', end_status=TS.INERROR)
    report = item.case.executor.execute_approved(item.guard, credentials=item.credentials)
    assert report.status == 'rollback_confirmed' and report.commit_status == 'not_attempted'
    assert 'PRIVATE' not in repr(report)


def test_unpinned_or_modified_artifact_lock_refused(tmp_path, campaign):
    path = tmp_path / 'lock.json'
    path.write_text('{}', encoding='utf8')
    with pytest.raises(Rejected): la.verify_artifacts(path, '0' * 64, 'a' * 64, campaign)
    with pytest.raises(Rejected): la.verify_artifacts(path, sha256(path.read_bytes()).hexdigest(), 'a' * 64, campaign)


def test_windows_registry_cannot_be_asserted_linux(tmp_path, campaign):
    import os
    if os.name != 'posix':
        with pytest.raises(Rejected): la.verify_registry(tmp_path, campaign, dict(mount_target='/var/lib/p101-qualification'))


def test_driver_rejects_sql_outside_the_signed_plan(livecase):
    item = livecase()
    item.case.reservations.reserve(item.guard.intent, envelope_sha256='c' * 64)
    connector = wt.LiveConnector(item.guard, item.credentials)
    connector._armed = True  # Internal kernel action modeled explicitly, never an API switch.
    connection = connector.open(item.case.campaign.database + '_p101_writer', False)
    cursor = connection.cursor()
    with pytest.raises(wt.WireError): cursor.execute('DROP TABLE public.companies')
    assert all(b'DROP TABLE' not in message for message in item.wires[0].sent)
    assert item.wires[0].closed == 1


@pytest.mark.parametrize('fault', [None, 'extra_mount', 'wrong_registry', 'port', 'foreign_member', 'volume_time', 'image', 'bind_volume'])
def test_p101_resource_profile_exactly_bounds_new_registry_mount(campaign, policy, monkeypatch, tmp_path, fault):
    endpoint = 'unix:///synthetic/docker.sock'
    policy = replace(policy, endpoint_sha256=sha256(endpoint.encode()).hexdigest(), image_id_sha256=la.POSTGRES_IMAGE_ID)
    registry = dict(volume=campaign.database + '_exec_registry', created_at=policy.volume_created_at.isoformat(),
        mount_target='/var/lib/p101-qualification')
    resources = ex.resource_inventory(campaign, policy, runner_image_id='3' * 64, registry=registry)
    collector = resource_profile.P101ResourceCollector(campaign, policy, resources,
        executable=str(tmp_path / 'synthetic-docker'), clock=lambda: NOW)
    containers = []
    for index, identifier in enumerate((campaign.container_id, campaign.runner_id)):
        containers.append(dict(id=identifier, name='/' + (campaign.container_name if index == 0 else campaign.container_name.removesuffix('-postgres') + '-runner'),
            image='sha256:' + (policy.image_id_sha256 if index == 0 else resources['runner_image_id']),
            image_ref='docker.io/library/postgres@sha256:' + campaign.image_sha256 if index == 0 else 'synthetic-runner',
            networks={campaign.network_name: dict(NetworkID=campaign.network_id, IPAddress=campaign.server_address)},
            mounts=[dict(Type='volume', Name=campaign.volume_name if index == 0 else registry['volume'],
                Destination='/var/lib/postgresql/data' if index == 0 else registry['mount_target'], RW=True)],
            ports={}, status='running', privileged=False, restart='no',
            memory=resources['postgres_memory' if index == 0 else 'runner_memory'], cpus=resources['nano_cpus'],
            shm=67108864, readonly_root=True))
    if fault == 'extra_mount': containers[1]['mounts'].append(dict(Type='bind', Name='docker-socket'))
    if fault == 'wrong_registry': containers[1]['mounts'][0]['Name'] = 'DEV'
    if fault == 'port': containers[0]['ports'] = {'5432/tcp': [dict(HostPort='5432')]}
    if fault == 'image': containers[0]['image'] = 'sha256:' + 'f' * 64
    def query(deadline, *args):
        if args[0] == 'context': return endpoint
        if args[0] == 'info': return campaign.engine_id
        if args[0] == 'inspect': return containers[0 if args[-1] == campaign.container_id else 1]
        if args[0] == 'network':
            return dict(id=campaign.network_id, name=campaign.network_name, driver='bridge', internal=True,
                members=dict.fromkeys((campaign.container_id, campaign.runner_id, *(['foreign'] if fault == 'foreign_member' else []))),
                ipam=[dict(Subnet=campaign.subnet)])
        if args[0] == 'volume':
            return dict(name=args[2], driver='local', scope='local',
                created=(NOW if fault == 'volume_time' else policy.volume_created_at).isoformat(),
                options={'device': '/DEV', 'type': 'none'} if fault == 'bind_volume' else None,
                mountpoint='/var/lib/docker/volumes/' + args[2] + '/_data')
        if args[0] == 'image':
            return dict(id=args[2], os='linux', arch='amd64', digests=[containers[0]['image_ref']])
        pytest.fail('Unexpected Docker query')
    monkeypatch.setattr(collector.reader, '_query', query)
    if fault:
        with pytest.raises(Rejected): collector.collect()
    else:
        result = collector.collect()
        assert result.packet.observation.source_id == 'p101-docker-cli'
        assert result.packet.observation.provenance == 'unverified_external'
        assert dict(result.packet.observation.facts)['extra_mounts'].startswith('runner-volume:')


def test_approved_artifact_bytes_and_versions_are_checked(tmp_path, campaign, monkeypatch):
    # Synthetic files test hashing/validation, NOT wheel closure or reproducibility.
    files = []
    for name in ('requirements.lock', 'trusted-keys.json', 'synthetic-1-py3-none-any.whl'):
        path = tmp_path / name
        path.write_bytes(b'synthetic-artifact')
        files.append(dict(path=name, sha256=sha256(path.read_bytes()).hexdigest()))
    lock = dict(format='p101-real1-artifacts-v1', platform='linux/amd64', python='3.12.10',
        base_image='docker.io/library/python@sha256:' + 'a' * 64, postgres_image_id=la.POSTGRES_IMAGE_ID,
        postgres_repo_digest=campaign.image_sha256, program_sha256='b' * 64, packages=la.PACKAGES, files=files)
    path = tmp_path / 'artifacts.json'
    path.write_bytes(la.canonical(lock))
    digest = sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(la, 'version', lambda name: la.PACKAGES[name])
    monkeypatch.setattr(la, 'read_json', lambda *args: pytest.fail('Must parse captured/hash-verified bytes, not reopen'))
    assert la.verify_artifacts(path, digest, 'b' * 64, campaign) == digest
    (tmp_path / files[1]['path']).write_bytes(b'changed')
    with pytest.raises(Rejected): la.verify_artifacts(path, digest, 'b' * 64, campaign)


def test_execute_cli_cannot_select_a_submitted_trust_anchor(tmp_path, capsys):
    admin = tmp_path / 'admin.json'
    admin.write_text('{}', encoding='utf8')
    assert operator_cli.main(['execute-approved', '--admin-config', str(admin), '--trust-store', str(admin)]) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'refused'


def test_password_fallback_is_refused_before_secret_input(monkeypatch):
    import warnings
    consumed = []
    def fallback(prompt):
        warnings.warn('Synthetic non-TTY fallback', operator_cli.GetPassWarning)
        consumed.append(True)
        return PRIVATE
    monkeypatch.setattr(operator_cli, 'getpass', fallback)
    with pytest.raises(operator_cli.GetPassWarning): operator_cli.passwords(('synthetic-role',))
    assert consumed == []
