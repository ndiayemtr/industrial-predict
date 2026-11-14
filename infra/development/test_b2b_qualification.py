"""Synthetic-only qualification tests; real processes/sockets/DB are forbidden."""
from datetime import datetime, timedelta, timezone
import copy
import io
import ipaddress
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

import manage
import b2b_deployment as deployment
import b2b_qualification as q
import b2b_qualification_relay as relay


def certificates(ip='127.0.0.1'):
    now = datetime.now(timezone.utc)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic qualification CA')])
    ca = x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1).not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1)).add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True).sign(key, hashes.SHA256())
    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server = x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'Synthetic server')])).issuer_name(name).public_key(server_key.public_key()).serial_number(2).not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1)).add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True).add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address(ip))]), critical=False).sign(key, hashes.SHA256())
    return ca.public_bytes(serialization.Encoding.PEM), server.public_bytes(serialization.Encoding.PEM)


class QualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ca, cls.server = certificates()
        cls.other_ca, cls.other_server = certificates('127.0.0.2')

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve() / q.CONTAINER
        self.root.mkdir()
        self.path = self.root / 'qualification.json'
        self.raw = {'format': 'b2b-isolated-qualification-v1', 'enabled': True,
            'qualification_campaign': q.CAMPAIGN, 'synthetic_only': True,
            'mode': 'isolated-qualification', 'runtime_profile': 'b2b-preparation',
            'db_host': '127.0.0.1', 'db_port': 55443, 'database': q.DATABASE,
            'cluster_name': q.CLUSTER, 'container': q.CONTAINER, 'volume': q.VOLUME,
            'image_id': q.IMAGE, 'database_oid': 20000, 'restore_database_oid': 20001,
            'instance_id': '11111111-1111-4111-8111-111111111111',
            'restore_instance_id': '22222222-2222-4222-8222-222222222222',
            'run_id': '33333333-3333-4333-8333-333333333333',
            'cluster_identifier': '1234567890123456789', 'container_id': 'a' * 64,
            'volume_created_at': '2026-11-14T12:00:00Z',
            'ca_sha256': q.policy.digest(self.ca), 'server_certificate_sha256': q.policy.digest(self.server)}
        self.path.write_text(json.dumps(self.raw))
        (self.root / 'ca.crt').write_bytes(self.ca)
        (self.root / 'server.crt').write_bytes(self.server)
        for role in ('admin', 'migrator', 'app'):
            (self.root / (role + '-password.txt')).write_text('b' * 64)
        for name in ('b2b_qualification.subprocess.run', 'b2b_qualification_relay.subprocess.Popen',
                     'b2b_qualification_relay.socket.socket', 'manage.create_engine',
                     'b2b_deployment.create_engine', 'sqlalchemy.engine.Engine.connect', 'psycopg.connect'):
            p = patch(name, side_effect=AssertionError('Real external operation forbidden'))
            p.start(); self.addCleanup(p.stop)
        self.qualification = q.Qualification.load(self.path, q.CAMPAIGN)
        self.manager = self.qualification.manager(manage)

    def config(self, **changes):
        return q.Qualification({**self.raw, **changes}, self.path)

    def resources(self):
        volume = {'Name': q.VOLUME, 'Labels': self.qualification.labels(), 'CreatedAt': self.raw['volume_created_at'],
            'Driver': 'local', 'Scope': 'local', 'Options': None, 'Mountpoint': '/synthetic/data'}
        container = {'id': self.raw['container_id'], 'name': '/' + q.CONTAINER, 'image': q.IMAGE,
            'labels': self.qualification.labels(), 'network': 'none', 'bindings': {}, 'ports': {'5432/tcp': None},
            'running': True, 'privileged': False, 'tmpfs': {}, 'pid_mode': '', 'ipc_mode': 'private',
            'mounts': [{'Type': 'volume', 'Name': q.VOLUME, 'Source': volume['Mountpoint'],
                        'Destination': '/var/lib/postgresql/data', 'RW': True}]}
        return container, [volume]

    def test_explicit_campaign_required(self):
        for campaign in (None, '', 'dev', q.CAMPAIGN.upper()):
            with self.subTest(campaign=campaign), self.assertRaises(ValueError):
                q.Qualification.load(self.path, campaign)

    def test_disabled_or_implicit_configuration_refused(self):
        for changes in ({'enabled': False}, {'enabled': 1}, {'synthetic_only': False}, {'mode': 'local-development'},
                        {'runtime_profile': 'b2b-auth-candidate'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.config(**changes).validate()
        with self.assertRaises(ValueError):
            deployment.Deployment(manage, self.qualification.config)

    def test_all_dev_destinations_ports_resources_forbidden(self):
        dev = q.policy.policy()['destination']
        for changes in ({'database': 'industrial_predict_dev'}, {'db_port': 5433}, {'db_port': 5434},
                        {'db_host': 'localhost'}, {'container': dev['container']},
                        {'volume': 'industrial-predict-postgres-ui47-data'}, {'database_oid': dev['database_oid']},
                        {'cluster_identifier': dev['cluster_identifier']}, {'instance_id': dev['instance_id']},
                        {'restore_database_oid': self.raw['database_oid']}, {'image_id': 'postgres:latest'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.config(**changes).validate()

    def test_no_dev_private_file_open(self):
        with patch.object(q.policy, 'read_json') as read, self.assertRaises(ValueError):
            q.Qualification.load(q.DEV_ROOT / 'config.json', q.CAMPAIGN)
        read.assert_not_called()
        for name in ('../app-password.txt', 'server.key', 'ca.key', 'config.json'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.qualification.file(name)

    def test_tls_hash_signature_and_san_refusals(self):
        self.assertEqual(self.qualification.transport()['sslmode'], 'verify-full')
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            self.config(ca_sha256='0' * 64).transport()
        (self.root / 'ca.crt').write_bytes(self.other_ca)
        with self.assertRaises(Exception):
            self.config(ca_sha256=q.policy.digest(self.other_ca)).transport()
        (self.root / 'server.crt').write_bytes(self.other_server)
        with self.assertRaisesRegex(ValueError, 'SAN'):
            self.config(ca_sha256=q.policy.digest(self.other_ca), server_certificate_sha256=q.policy.digest(self.other_server)).transport()

    def test_ambient_pg_settings_rejected(self):
        with patch.dict(q.os.environ, {'PGSERVICE': 'dev'}), self.assertRaisesRegex(ValueError, 'Ambient'):
            self.qualification.transport()

    def test_resource_identity_and_mounts(self):
        container, volumes = self.resources()
        self.qualification.check_resources(container, volumes)
        for changes in ({'id': 'b' * 64}, {'name': '/industrial-predict-postgres-ui47'},
                        {'labels': {}}, {'image': 'sha256:' + '0' * 64}, {'network': 'bridge'},
                        {'bindings': {'5432/tcp': [{'HostPort': '55443'}]}},
                        {'ports': {'5432/tcp': [{'HostPort': '5434'}]}}, {'privileged': True},
                        {'tmpfs': {'/unexpected': 'rw'}}, {'pid_mode': 'host'}, {'running': False}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.qualification.check_resources({**container, **changes}, volumes)
        for changes in ({'Name': 'industrial-predict-postgres-ui47-data'}, {'CreatedAt': 'different'},
                        {'Labels': {}}, {'Options': {'device': '/private'}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.qualification.check_resources(container, [{**volumes[0], **changes}])
        for changes in ({'Type': 'bind'}, {'RW': False}, {'Source': '/dev-data'}, {'Destination': '/other'}):
            altered = copy.deepcopy(container)
            altered['mounts'][0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.qualification.check_resources(altered, volumes)
        with self.assertRaises(ValueError):
            self.qualification.check_resources({**container, 'mounts': container['mounts'] * 2}, volumes)

    def test_name_resolved_before_inspection_of_id(self):
        with patch.object(self.qualification, 'docker', return_value=b'wrong-id') as docker, self.assertRaises(ValueError):
            self.qualification.verify_resources()
        self.assertEqual(docker.call_count, 1)
        self.assertIn('name=^/' + q.CONTAINER + '$', docker.call_args.args)

    def test_only_pinned_image_inherited_labels_are_allowed(self):
        container, volumes = self.resources()
        inherited = {'maintainer': 'synthetic official-image label'}
        container['labels'].update(inherited)
        self.qualification.check_resources(container, volumes, inherited)
        with self.assertRaises(ValueError):
            self.qualification.check_resources(container, volumes)
        with self.assertRaises(ValueError):
            self.qualification.check_resources(container, volumes, self.qualification.labels())

    def test_complete_resource_inspection_and_wrong_architecture(self):
        container, volumes = self.resources()
        image = [{'Id': q.IMAGE, 'Os': 'linux', 'Architecture': 'amd64'}]
        output = [self.raw['container_id'].encode(), json.dumps(image).encode(), json.dumps(container).encode(), json.dumps(volumes).encode()]
        with patch.object(self.qualification, 'docker', side_effect=output):
            self.assertEqual(self.qualification.verify_resources(), self.raw['container_id'])
        image[0]['Architecture'] = 'arm64'
        with patch.object(self.qualification, 'docker', side_effect=[output[0], json.dumps(image).encode()]), self.assertRaises(ValueError):
            self.qualification.verify_resources()
        self.assertNotIn('Env', q.INSPECT)

    def test_rendered_identity_distinct_bodies_and_acl_tails_unchanged(self):
        original = deployment.capture()
        rendered = self.qualification.render(original)
        for name, sql in rendered.items():
            self.assertIn(q.DATABASE, sql)
            self.assertIn(q.CLUSTER, sql)
            self.assertIn('55443', sql)
            self.assertNotIn('industrial_predict_dev', sql)
            self.assertNotIn('7697614558579179559', sql)
            boundary = 'CREATE ROLE ui47_b2b_lock_owner' if name.startswith('b2b-lock-install') else '-- Named-role ACL assertion:'
            self.assertEqual(sql.split(boundary, 1)[1], original[name].split(boundary, 1)[1])
        for f in q.locks.FUNCTIONS:
            self.assertIn('$body$' + f['body'] + '$body$', rendered['b2b-lock-install.review.sql'])
            self.assertEqual(q.policy.digest(f['body'].encode()), f['sha256'])

    def test_qualification_plan_and_restore_do_not_use_dev_identity(self):
        instance = deployment.Deployment(self.manager, self.qualification.config, qualification=self.qualification)
        self.assertEqual(instance.plan['operation'], 'isolated-b2b-locks-qualification-v1')
        self.assertEqual(instance.restore_inventory()['database'], q.RESTORE)
        self.assertNotEqual(instance.restore_inventory()['instance_id'], self.raw['instance_id'])
        self.assertFalse(instance.plan['runtime_enabled'])

    def test_dev_guard_and_sources_unchanged(self):
        original = deployment.capture()
        self.assertIn('industrial_predict_dev', original['b2b-lock-install.review.sql'])
        self.assertEqual(q.policy.policy()['destination']['db_port'], 5434)
        # New context is not used by normal load_config.
        with self.assertRaisesRegex(ValueError, 'target mismatch'):
            manage.load_config(self.path)

    def test_identity_checks_exact_cluster_database_version_and_transport(self):
        c = MagicMock()
        proof = {**self.qualification.config, 'role': 'ui47_migrator', 'version': '17.10',
                 'superuser': False, 'createdb': False, 'createrole': False, 'replication': False, 'bypassrls': False}
        c.execute.return_value.mappings.return_value.one.return_value = proof
        c.execute.return_value.scalar_one.return_value = 'b2b_0002_analyze'
        c.exec_driver_sql.return_value.one.return_value = ('127.0.0.1', 55443)
        self.manager.inspect_connection(c, self.qualification.config, 'migrator', expected_revision='b2b_0002_analyze')
        for change in ({'cluster_name': 'industrial-predict-development'}, {'database': 'industrial_predict_dev'},
                       {'version': '17.10.1'}, {'role': 'ui47_app'}, {'superuser': True}):
            c.execute.return_value.mappings.return_value.one.return_value = {**proof, **change}
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.manager.inspect_connection(c, self.qualification.config, 'migrator', expected_revision='b2b_0002_analyze')
        c.execute.return_value.mappings.return_value.one.return_value = proof
        c.exec_driver_sql.return_value.one.return_value = ('127.0.0.1', 5434)
        with self.assertRaises(ValueError):
            self.manager.inspect_connection(c, self.qualification.config, 'migrator', expected_revision='b2b_0002_analyze')

    def test_pgtools_pin_tls_and_never_put_password_in_argv(self):
        evidence = self.root / 'evidence'
        evidence.mkdir()
        archive = evidence / 'synthetic.dump'
        version = MagicMock(returncode=0, stdout=b'pg_dump (PostgreSQL) 17.10')
        result = MagicMock(returncode=0, stdout=b'archive-output')
        records = []
        def run(argv, **kwargs):
            records.append((argv, {**kwargs.get('env', {})}))
            return version if '--version' in argv else result
        with patch.object(self.qualification, 'verify_resources'), patch.object(q.shutil, 'which', return_value='qualified-pg_dump'), patch.object(q.subprocess, 'run', side_effect=run), patch('sys.stdout', new_callable=io.StringIO) as output:
            self.manager.b2b_pgtool(self.qualification.config, 'pg_dump', ['--dbname=' + q.DATABASE, '--format=custom', '--snapshot=0001-0002-1', '--file=' + str(archive)])
        argv, env = records[-1]
        self.assertIn('--port=55443', argv)
        self.assertEqual(env['PGSSLMODE'], 'verify-full')
        self.assertEqual(env['PGGSSENCMODE'], 'disable')
        self.assertNotIn('b' * 64, str(argv) + output.getvalue())
        self.assertEqual(env['PGPASSWORD'], 'b' * 64)

    def test_pgtool_rejects_other_database_or_option_before_external_io(self):
        for args in (['--dbname=industrial_predict_dev'], ['--dbname=' + q.DATABASE, '--port=5434'],
                     ['--dbname=' + q.DATABASE, '--host=evil'], ['--dbname=' + q.DATABASE, '--file=../private'],
                     ['--dbname=' + q.DATABASE, '--snapshot=bad;sql']):
            with self.subTest(args=args), self.assertRaises(ValueError):
                self.manager.b2b_pgtool(self.qualification.config, 'pg_dump', args)
        q.subprocess.run.assert_not_called()

    def test_cli_rejects_qualification_on_runtime_or_wrong_campaign(self):
        for action, campaign in (('api', q.CAMPAIGN), ('b2b-locks-install', 'incorrect')):
            with patch('sys.argv', ['manage.py', action, '--config', str(self.path), '--qualification-campaign', campaign]), self.assertRaises((ValueError, SystemExit)):
                manage.main()

    def test_cli_dispatch_explicit_context_preserves_operator_boundary(self):
        with patch('sys.argv', ['manage.py', 'b2b-locks-install', '--config', str(self.path), '--qualification-campaign', q.CAMPAIGN, '--bundle', str(self.root / 'evidence' / 'fresh')]), patch.object(deployment, 'Deployment') as factory:
            factory.return_value.operate.return_value = {'stage': 'install'}
            manage.main()
            self.assertIsInstance(factory.call_args.kwargs['qualification'], q.Qualification)
            self.assertEqual(factory.return_value.operate.call_args.args[1], 'install')

    def test_relay_explicit_flag_required_before_private_config(self):
        with patch('sys.argv', ['manage.py', 'b2b-locks-relay', '--config', 'not-read']), patch.object(manage, 'load_config') as load, self.assertRaises(SystemExit):
            manage.main()
        load.assert_not_called()

    def test_relay_listener_exact_address_exclusive_and_closed_on_stop(self):
        listener = MagicMock()
        listener.__enter__.return_value = listener
        listener.accept.side_effect = KeyboardInterrupt
        r = relay.Relay(self.qualification)
        with patch.object(self.qualification, 'verify_resources', return_value=self.raw['container_id']), patch.object(manage, 'b2b_confirm') as confirmation, patch.object(relay.socket, 'socket', return_value=listener):
            r.run()
        confirmation.assert_called_once()
        listener.bind.assert_called_once_with(('127.0.0.1', 55443))
        listener.setsockopt.assert_called_once_with(relay.socket.SOL_SOCKET, relay.socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.__exit__.assert_called_once()
        self.assertIsNone(r.listener)
        relay.subprocess.Popen.assert_not_called()

    def test_relay_without_approval_never_binds(self):
        with patch.object(self.qualification, 'verify_resources'), patch.object(manage, 'b2b_confirm', side_effect=ValueError('No approval')), self.assertRaisesRegex(ValueError, 'No approval'):
            relay.Relay(self.qualification).run()
        relay.socket.socket.assert_not_called()

    def test_relay_monitor_failure_stops_without_retry(self):
        r = relay.Relay(self.qualification)
        # Do not wait for a real timer; drive exactly one monitoring interval.
        with patch.object(r.stop, 'wait', side_effect=[False, True]), patch.object(self.qualification, 'verify_resources', side_effect=ValueError('changed')) as verify:
            r.monitor()
        verify.assert_called_once()
        self.assertTrue(r.failed.is_set())

    def test_qualification_keeps_commit_uncertain_and_rollback_contract(self):
        instance = deployment.Deployment(self.manager, self.qualification.config, qualification=self.qualification)
        engine, c = MagicMock(), MagicMock()
        c.__enter__.return_value = c
        engine.connect.return_value = c
        c.begin.return_value.commit.side_effect = OSError('lost acknowledgement')
        with self.assertRaises(q.policy.CommitUncertain):
            instance.transact(engine, MagicMock(), MagicMock())
        c.begin.return_value.commit.assert_called_once()
        c.begin.return_value.rollback.assert_not_called()
        c.reset_mock()
        with self.assertRaises(ValueError):
            instance.transact(engine, MagicMock(side_effect=ValueError('before commit')), MagicMock())
        c.begin.return_value.rollback.assert_called_once()
        c.begin.return_value.commit.assert_not_called()

    def test_binary_relay_preserves_all_octets_partial_writes_and_utf8(self):
        payload = ('SELECT \'é\n日本語\';\n'.encode() + bytes(range(256))) * 7
        class ShortWriter:
            def __init__(self): self.data = bytearray()
            def write(self, data):
                count = min(3, len(data)); self.data.extend(data[:count]); return count
            def close(self): pass
        upload = ShortWriter()
        process = MagicMock()
        process.stdin, process.stdout = upload, io.BytesIO(payload[::-1])
        process.wait.return_value = 0
        process.poll.return_value = 0
        client = MagicMock()
        client.recv.side_effect = [payload[:17], payload[17:], b'']
        received = bytearray()
        client.sendall.side_effect = received.extend
        r = relay.Relay(self.qualification)
        with patch.object(self.qualification, 'verify_resources', return_value=self.raw['container_id']), patch.object(relay.shutil, 'which', return_value='docker'), patch.object(relay.subprocess, 'Popen', return_value=process) as popen:
            r.transfer(client)
        self.assertFalse(r.failed.is_set())
        self.assertEqual(bytes(upload.data), payload)
        self.assertEqual(bytes(received), payload[::-1])
        command = popen.call_args.args[0]
        self.assertIn(self.raw['container_id'], command)
        self.assertNotIn('-t', command)
        self.assertNotIn('text', popen.call_args.kwargs)
        self.assertNotIn('5434', relay.BRIDGE)
        self.assertNotIn('5433', relay.BRIDGE)
        self.assertEqual(q.policy.digest(bytes(upload.data)), q.policy.digest(payload))

    def test_relay_no_child_if_identity_wrong(self):
        r = relay.Relay(self.qualification)
        with patch.object(self.qualification, 'verify_resources', side_effect=ValueError('mismatch')):
            r.transfer(MagicMock())
        self.assertTrue(r.failed.is_set())
        relay.subprocess.Popen.assert_not_called()

    def test_short_write_failure_does_not_retry(self):
        writer = MagicMock()
        writer.write.return_value = 0
        with self.assertRaises(OSError):
            relay.write_all(writer, b'UTF-8\n')
        writer.write.assert_called_once()


if __name__ == '__main__':
    unittest.main()
