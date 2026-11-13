"""DEV B2B guards and actual Alembic SQL rendering; never real PostgreSQL."""
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import b2b_policy as b2b
import manage


# Keep the real runner available to exercise Alembic, beyond orchestration mocks.
APPLY_APPROVED_RELEASE = manage.b2b_apply_release


def recording_connection(connection):
    """Record PostgreSQL SQL compilation on a double, with an outer transaction."""
    from sqlalchemy.dialects import postgresql
    connection.dialect = postgresql.dialect()
    connection.in_transaction.return_value = True
    statements = []
    def execute(statement, *args, **kwargs):
        statements.append(str(statement.compile(dialect=connection.dialect)))
        return MagicMock(rowcount=1)
    connection.execute.side_effect = execute
    return statements


class B2BTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        p = b2b.policy()
        self.config = {**p['destination'], '_path': p['profile'], '_directory': str(self.directory)}
        self.target = p['target']
        self.now = datetime.now(timezone.utc)
        # Every accidental path to database/network/client execution is fatal.
        for name in ('manage.create_engine', 'sqlalchemy.engine.Engine.connect',
                     'psycopg.connect', 'socket.socket.connect', 'socket.getaddrinfo',
                     'manage.subprocess.run', 'manage.b2b_apply_release'):
            guard = patch(name, side_effect=AssertionError('External operation forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def plan(self):
        return manage.b2b_plan(self.config, self.target)[0]

    def bundle(self):
        directory = self.directory / 'evidence' / 'test-only'
        directory.mkdir(parents=True)
        archive = directory / 'before-b2b.dump'
        archive.write_bytes(b'not-a-real-dump-only-an-evidence-fixture')
        snapshot = {'fixture': 'no-business-data'}
        common = {'format': 'dev-b2b-evidence-v1', 'plan_sha256': b2b.digest(b2b.canonical(self.plan())),
                  'archive_sha256': b2b.file_digest(archive), 'created_at': self.now.isoformat()}
        backup = {**common, 'stage': 'backup', 'snapshot': snapshot}
        restore = {**common, 'stage': 'restore', 'verified': True, 'restored_snapshot': snapshot,
                   'database': b2b.policy()['restore_database'], 'database_oid': 99999,
                   'instance_id': '00000000-0000-4000-8000-000000000002'}
        for stage, value in (('backup', backup), ('restore', restore)):
            (directory / (stage + '.json')).write_text(json.dumps(value), encoding='utf-8')
        return directory

    def alter(self, directory, stage_name, **updates):
        path = directory / (stage_name + '.json')
        value = b2b.read_json(path)
        value.update(updates)
        path.write_text(json.dumps(value), encoding='utf-8')

    def test_exact_sequence_accepted_only_as_offline_prevalidation(self):
        with patch('manage.db_url', side_effect=AssertionError('Secret read forbidden')):
            report = b2b.report(self.config, current=manage.REVISION,
                                role='ui47_migrator', target=self.target)
        self.assertTrue(report['accepted'])
        self.assertEqual(report['stage'], 'offline_prevalidation')
        self.assertEqual(report['plan']['sequence'], ['12e2fc65f372','4b7e2a91c6d0',
                                                     'b2b_0001_sessions','b2b_0002_analyze'])
        for flag in ('execution_enabled','live_verified','approval_verified','backup_verified'):
            self.assertIs(report[flag], False)
        _, bodies = manage.b2b_plan(self.config, self.target)
        self.assertEqual(len(bodies), 4)
        self.assertNotIn('p101_0001_operations', [body[0] for body in bodies])

    def test_destination_mismatches(self):
        changes = {'database': 'industrial_predict', 'db_host': 'localhost', 'db_port': 5433,
                   'database_oid': 999, 'cluster_identifier': '123', 'instance_id': 'other',
                   'container': 'other', 'mode': 'production', '_path': str(self.directory / 'config.json')}
        for field, wrong in changes.items():
            with self.subTest(field=field), self.assertRaises(ValueError):
                manage.b2b_plan({**self.config, field: wrong}, self.target)

    def test_unexpected_initial_versions(self):
        for current in (None, '', 'head', 'b2b_0001_sessions', 'b2b_0002_analyze', 'p101_0001_operations'):
            with self.subTest(current=current), self.assertRaises(ValueError):
                b2b.release(self.config, current=current, role='ui47_migrator', target=self.target)

    def test_unknown_p101_dynamic_and_downgrade_targets_refused(self):
        for target in ('head', 'heads', 'base', '-1', 'p101_0001_operations', 'p101_0001', '4b7e2a91c6d0', 'unknown'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                manage.b2b_plan(self.config, target)

    def test_wrong_sql_roles(self):
        for role in ('ui47_admin', 'ui47_app', 'postgres', 'migrator', None):
            with self.subTest(role=role), self.assertRaises(ValueError):
                b2b.release(self.config, current=manage.REVISION, role=role, target=self.target)

    def test_unexpected_graph(self):
        from app import general_migrations as guards
        with patch.object(guards, 'resolve_upgrade', return_value=('p101_0001_operations',)), self.assertRaises(ValueError):
            self.plan()

    def test_source_fingerprint_divergence(self):
        from app import general_migrations as guards
        from dataclasses import replace
        snapshot = guards.inspect_sources()
        altered = replace(snapshot, sources=(replace(snapshot.sources[0], sha256='0'*64), *snapshot.sources[1:]))
        with patch.object(guards, 'inspect_sources', return_value=altered), self.assertRaises(ValueError):
            self.plan()

    def test_changed_source_during_capture_refused(self):
        from app import general_migrations as guards
        snapshot = guards.inspect_sources()
        read = Path.read_text
        def changed(path, *args, **kwargs):
            source = read(path, *args, **kwargs)
            return source + '\n# changed\n' if path.name == 'b2b_0001_sessions.py' else source
        with patch.object(guards, 'inspect_sources', return_value=snapshot), \
             patch.object(Path, 'read_text', changed), self.assertRaises(ValueError):
            self.plan()

    def test_policy_fingerprint_and_duplicate_json_refused(self):
        path = self.directory / 'policy.json'
        path.write_text('{}')
        with patch.object(b2b, 'POLICY', path), self.assertRaises(ValueError):
            b2b.policy()
        with self.assertRaises(ValueError):
            b2b.parse_json('{"verified":true,"verified":false}')

    def test_missing_backup_or_restore_refused_before_connection(self):
        directory = self.bundle()
        (directory / 'restore.json').unlink()
        with self.assertRaises(FileNotFoundError):
            manage.migrate_b2b(self.config, directory, self.target)
        (directory / 'backup.json').unlink()
        with self.assertRaises(FileNotFoundError):
            manage.migrate_b2b(self.config, directory, self.target)

    def test_valid_evidence_is_not_approval_or_execution(self):
        directory = self.bundle()
        backup, restored = b2b.evidence(self.config, directory, self.plan(), now=self.now)
        self.assertTrue(restored['verified'])
        self.assertEqual(backup['snapshot'], restored['restored_snapshot'])
        with patch('manage.b2b_restore_config', return_value={**self.config,
                **{k: restored[k] for k in ('database','database_oid','instance_id')}}), \
             patch('manage.b2b.transport', return_value={}), \
             patch('manage.sys.stdin.isatty', return_value=False), self.assertRaises(ValueError):
            manage.migrate_b2b(self.config, directory, self.target)

    def test_unvalidated_or_wrong_restore(self):
        directory = self.bundle()
        original = b2b.read_json(directory / 'restore.json')
        for update in ({'verified': False}, {'database': self.config['database']},
                       {'database_oid': self.config['database_oid']}, {'instance_id': self.config['instance_id']},
                       {'restored_snapshot': {'changed': True}}, {'plan_sha256': '0'*64},
                       {'archive_sha256': '0'*64}):
            self.alter(directory, 'restore', **{**original, **update})
            with self.subTest(update=update), self.assertRaises(ValueError):
                b2b.evidence(self.config, directory, self.plan(), now=self.now)

    def test_expired_future_and_naive_evidence_refused(self):
        directory = self.bundle()
        for instant in (self.now-timedelta(hours=25), self.now+timedelta(seconds=1), self.now.replace(tzinfo=None)):
            self.alter(directory, 'backup', created_at=instant.isoformat())
            with self.subTest(instant=instant), self.assertRaises(ValueError):
                b2b.evidence(self.config, directory, self.plan(), now=self.now)

    def test_archive_changed_refused(self):
        directory = self.bundle()
        (directory / 'before-b2b.dump').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            b2b.evidence(self.config, directory, self.plan(), now=self.now)

    def test_evidence_outside_private_profile_refused(self):
        with self.assertRaises(ValueError):
            b2b.private_directory(self.config, self.directory)

    def test_no_yes_switch_or_stdin_confirmation(self):
        plan = self.plan()
        for terminal in (False, True):
            with patch('manage.sys.stdin.isatty', return_value=terminal), \
                 patch('manage.sys.stdout.isatty', return_value=True), \
                 patch('builtins.input', return_value='yes'), patch('builtins.print'), self.assertRaises(ValueError):
                manage.b2b_confirm('MIGRATE-B2B', plan)

    def test_exact_interactive_confirmation_is_action_bound(self):
        plan = self.plan()
        token = 'MIGRATE-B2B ' + b2b.digest(b2b.canonical(plan)) + ' archive-hash'
        with patch('manage.sys.stdin.isatty', return_value=True), \
             patch('manage.sys.stdout.isatty', return_value=True), \
             patch('builtins.input', return_value=token), patch('builtins.print'):
            manage.b2b_confirm('MIGRATE-B2B', plan, archive_hash='archive-hash')
            with self.assertRaises(ValueError):
                manage.b2b_confirm('BACKUP-B2B', plan, archive_hash='archive-hash')

    def test_transport_missing_weak_or_wrong_ca_refused(self):
        with self.assertRaises(ValueError):
            b2b.transport(self.config)
        ca = self.directory / 'ca.crt'
        ca.write_bytes(b'fixture-not-a-real-certificate')
        valid = {'sslmode':'verify-full','sslrootcert':str(ca),'ca_sha256':b2b.file_digest(ca)}
        self.assertEqual(b2b.transport({**self.config,'b2b_transport':valid})['sslmode'], 'verify-full')
        for update in ({'sslmode':'prefer'}, {'ca_sha256':'0'*64}, {'extra':True}):
            with self.subTest(update=update), self.assertRaises(ValueError):
                b2b.transport({**self.config,'b2b_transport':{**valid, **update}})

    def test_restore_inventory_never_active_dev(self):
        valid = {'database': b2b.policy()['restore_database'], 'database_oid':99999,
                 'instance_id':'00000000-0000-4000-8000-000000000002',
                 'cluster_identifier':self.config['cluster_identifier']}
        file = self.directory / 'b2b-restore.json'
        file.write_text(json.dumps(valid))
        self.assertEqual(manage.b2b_restore_config(self.config)['database'], valid['database'])
        for update in ({'database':self.config['database']}, {'database':'industrial_predict'},
                       {'database_oid':self.config['database_oid']}, {'instance_id':self.config['instance_id']},
                       {'cluster_identifier':'other'}):
            file.write_text(json.dumps({**valid, **update}))
            with self.subTest(update=update), self.assertRaises(ValueError):
                manage.b2b_restore_config(self.config)

    def test_existing_restore_receipt_prevents_replay(self):
        directory = self.bundle()
        with self.assertRaises(ValueError):
            manage.b2b_rehearse(self.config, directory, self.target)

    def test_live_role_and_revision_checks_before_ddl(self):
        proof = dict(database=self.config['database'], role='ui47_migrator', version='17.10',
                     database_oid=16384, instance_id=self.config['instance_id'],
                     cluster_name='industrial-predict-development', backend_pid=1,
                     superuser=False, createdb=False, createrole=False, replication=False, bypassrls=False)
        for wrong_role in ('ui47_app', 'ui47_admin'):
            connection = MagicMock()
            connection.execute.return_value.mappings.return_value.one.return_value = {**proof, 'role':wrong_role}
            with self.subTest(role=wrong_role), self.assertRaises(ValueError):
                manage.b2b_identity(connection, self.config, expected_revision=manage.REVISION)
        for versions in ([], ['wrong'], [manage.REVISION, 'b2b_0001_sessions']):
            connection = MagicMock()
            connection.execute.return_value.mappings.return_value.one.return_value = proof
            connection.execute.return_value.scalars.return_value.all.return_value = versions
            with self.subTest(versions=versions), self.assertRaises(ValueError):
                manage.b2b_identity(connection, self.config, expected_revision=manage.REVISION)

    def test_cli_preflight_never_creates_engine_or_reads_secret(self):
        with patch('manage.sys.argv', ['manage.py','b2b-preflight','--config','fixture',
                    '--current-revision',manage.REVISION]), \
             patch('manage.load_config', return_value=self.config), patch('builtins.print') as output, \
             patch('manage.db_url', side_effect=AssertionError('Secret read forbidden')):
            manage.main()
            self.assertFalse(json.loads(output.call_args.args[0])['execution_enabled'])

    def test_missing_cli_current_revision_and_wrong_role_refused(self):
        cases = [['b2b-preflight','--config','fixture'],
                 ['b2b-migrate','--config','fixture','--bundle','fixture','--role','ui47_admin']]
        for arguments in cases:
            with self.subTest(arguments=arguments), patch('manage.sys.argv',['manage.py',*arguments]), \
                 patch('manage.load_config',return_value=self.config), patch('sys.stderr'), self.assertRaises(SystemExit):
                manage.main()

    def simulate_migration(self):
        """Mock all DB work including the Alembic runner; no revision executes."""
        directory = self.bundle()
        backup, restored = b2b.evidence(self.config, directory, self.plan())
        engine = MagicMock()
        connection = engine.connect.return_value.__enter__.return_value
        connection.exec_driver_sql.return_value.scalar_one.return_value = True
        transaction = connection.begin.return_value
        patches = {
            'manage.b2b_engine': lambda *a: engine,
            'manage.b2b_confirm': lambda *a, **kw: None,
            'manage.b2b_verify_restore': MagicMock(),
            'manage.b2b.transport': lambda *a: {},
            'manage.b2b_restore_config': lambda *a: {**self.config, **{k:restored[k] for k in ('database','database_oid','instance_id')}},
            'manage.b2b_identity': MagicMock(),
            'manage.b2b_snapshot': MagicMock(return_value=backup['snapshot']),
            'manage.b2b_apply_release': MagicMock(),
            'manage.b2b_installed_shape': MagicMock(),
        }
        for name, value in patches.items():
            guard = patch(name, value)
            guard.start()
            self.addCleanup(guard.stop)
        return directory, engine, connection, transaction, patches

    def test_live_guard_failure_never_calls_alembic(self):
        directory, engine, connection, transaction, patched = self.simulate_migration()
        patched['manage.b2b_identity'].side_effect = ValueError('wrong live identity')
        with self.assertRaises(ValueError):
            manage.migrate_b2b(self.config, directory, self.target)
        patched['manage.b2b_apply_release'].assert_not_called()
        transaction.commit.assert_not_called()
        transaction.rollback.assert_called_once()

    def test_snapshot_drift_never_calls_alembic(self):
        directory, engine, connection, transaction, patched = self.simulate_migration()
        patched['manage.b2b_snapshot'].return_value = {'changed':True}
        with self.assertRaises(ValueError):
            manage.migrate_b2b(self.config, directory, self.target)
        patched['manage.b2b_apply_release'].assert_not_called()
        transaction.rollback.assert_called_once()

    def test_mocked_execution_is_one_outer_commit_and_exact_sequence(self):
        directory, engine, connection, transaction, patched = self.simulate_migration()
        result = manage.migrate_b2b(self.config, directory, self.target)
        self.assertTrue(result['commit_confirmed'])
        transaction.commit.assert_called_once()
        args = patched['manage.b2b_apply_release'].call_args.args
        self.assertEqual(tuple(r[0] for r in args[2]), tuple(self.plan()['sequence']))
        self.assertEqual(args[1]['target'], 'b2b_0002_analyze')
        # Runner is a mock; no upgrade function was imported or invoked.
        self.assertEqual(patched['manage.b2b_apply_release'].call_count, 1)

    def test_lost_commit_ack_is_uncertain_and_never_retried(self):
        directory, engine, connection, transaction, patched = self.simulate_migration()
        transaction.commit.side_effect = RuntimeError('lost acknowledgement')
        with self.assertRaisesRegex(RuntimeError, 'B2B_COMMIT_UNCERTAIN'):
            manage.migrate_b2b(self.config, directory, self.target)
        transaction.commit.assert_called_once()
        self.assertEqual(patched['manage.b2b_apply_release'].call_count, 1)

    def test_post_commit_failure_is_distinct(self):
        directory, engine, connection, transaction, patched = self.simulate_migration()
        patched['manage.b2b_identity'].side_effect = [None, None, ValueError('postcheck')]
        with self.assertRaisesRegex(RuntimeError, 'B2B_COMMIT_CONFIRMED_POSTCHECK_FAILED'):
            manage.migrate_b2b(self.config, directory, self.target)
        transaction.commit.assert_called_once()

    def test_real_alembic_runner_rolls_back_on_final_validation_failure(self):
        from alembic.runtime.migration import MigrationContext
        directory, engine, connection, transaction, patched = self.simulate_migration()
        statements = recording_connection(connection)
        patched['manage.b2b_installed_shape'].side_effect = ValueError('injected final validation failure')
        # Only the starting version SELECT is simulated. The real context,
        # RevisionMap, steps, operations and version updates run against a double.
        with patch('manage.b2b_apply_release', APPLY_APPROVED_RELEASE), \
             patch.object(MigrationContext, 'get_current_heads', return_value=(manage.REVISION,)), \
             self.assertRaisesRegex(ValueError, 'injected final validation failure'):
            manage.migrate_b2b(self.config, directory, self.target)
        self.assertEqual(len(statements), 18)  # fourteen DDL + four version updates
        connection.begin.assert_called_once()
        transaction.rollback.assert_called_once()
        transaction.commit.assert_not_called()
        connection.commit.assert_not_called()

    def test_real_alembic_runner_rolls_back_when_a_later_revision_fails(self):
        from alembic.runtime.migration import MigrationContext
        directory, engine, connection, transaction, patched = self.simulate_migration()
        statements = recording_connection(connection)
        record = connection.execute.side_effect
        def fail_later(statement, *args, **kwargs):
            result = record(statement, *args, **kwargs)
            if 'CREATE TABLE public.company_memberships' in statements[-1]:
                raise ValueError('injected later revision failure')
            return result
        connection.execute.side_effect = fail_later
        with patch('manage.b2b_apply_release', APPLY_APPROVED_RELEASE), \
             patch.object(MigrationContext, 'get_current_heads', return_value=(manage.REVISION,)), \
             self.assertRaisesRegex(ValueError, 'injected later revision failure'):
            manage.migrate_b2b(self.config, directory, self.target)
        self.assertTrue(any(s.startswith('UPDATE public.alembic_version') for s in statements))
        patched['manage.b2b_installed_shape'].assert_not_called()
        connection.begin.assert_called_once()
        transaction.rollback.assert_called_once()
        transaction.commit.assert_not_called()
        connection.commit.assert_not_called()

    def test_client_credentials_not_in_argv_or_parent_environment(self):
        import os
        from sqlalchemy.engine import URL
        from types import SimpleNamespace
        original = dict(os.environ)
        calls = []
        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            return SimpleNamespace(returncode=0, stdout='pg_dump (PostgreSQL) 17.10' if '--version' in argv else b'')
        with patch('manage.shutil.which', return_value='pg_dump.exe'), \
             patch('manage.subprocess.run', side_effect=run), \
             patch('manage.db_url', return_value=URL.create('postgresql+psycopg',password='synthetic-test-secret')), \
             patch('manage.b2b.transport',return_value={'sslmode':'verify-full','sslrootcert':'fixture-ca'}):
            manage.b2b_pgtool(self.config, 'pg_dump', ['--dbname=industrial_predict_dev','--format=custom'])
        self.assertNotIn('synthetic-test-secret', str(calls[-1][0]))
        self.assertEqual(dict(os.environ), original)
        self.assertNotIn('PGPASSWORD', calls[-1][1]['env'])  # erased after child completion

    def test_backup_failure_does_not_emit_success_receipt(self):
        directory = self.directory / 'evidence' / 'failed-backup'
        directory.parent.mkdir()
        engine = MagicMock()
        connection = engine.connect.return_value.execution_options.return_value.__enter__.return_value
        with patch('manage.b2b.transport',return_value={}), patch('manage.b2b_confirm'), \
             patch('manage.b2b_engine',return_value=engine), patch('manage.b2b_identity'), \
             patch('manage.b2b_snapshot',return_value={}), \
             patch('manage.b2b_pgtool',side_effect=ValueError('backup failed')), self.assertRaises(ValueError):
            manage.b2b_backup(self.config,directory,self.target)
        self.assertFalse((directory/'backup.json').exists())

    def test_active_restore_target_refused_before_any_connection(self):
        directory = self.bundle()
        (directory/'restore.json').unlink()
        inventory = {'database':self.config['database'], 'database_oid':self.config['database_oid'],
                     'instance_id':self.config['instance_id'], 'cluster_identifier':self.config['cluster_identifier']}
        (self.directory/'b2b-restore.json').write_text(json.dumps(inventory))
        with self.assertRaises(ValueError):
            manage.b2b_rehearse(self.config,directory,self.target)

    def test_restore_nonempty_destination_refused(self):
        connection = MagicMock()
        # System identifier, safe privileges, then a nonempty public table set.
        connection.exec_driver_sql.side_effect = [
            MagicMock(scalar_one=MagicMock(return_value=self.config['cluster_identifier'])),
            MagicMock(scalar_one=MagicMock(return_value=True)),
            MagicMock(scalars=MagicMock(return_value=['unexpected_table']))]
        with patch('manage.inspect_connection'), self.assertRaisesRegex(ValueError,'not empty'):
            manage.b2b_identity(connection,self.config,expected_revision=None,empty=True)

    def test_live_restore_recheck_refuses_changed_data(self):
        directory = self.bundle()
        backup, restored = b2b.evidence(self.config,directory,self.plan())
        engine = MagicMock()
        destination = {**self.config, **{k:restored[k] for k in ('database','database_oid','instance_id')}}
        with patch('manage.b2b_restore_config',return_value=destination), \
             patch('manage.b2b_engine',return_value=engine), patch('manage.b2b_identity'), \
             patch('manage.b2b_snapshot',return_value={'changed':True}), self.assertRaisesRegex(ValueError,'no longer verified'):
            manage.b2b_verify_restore(self.config,backup,restored)

    def test_restore_failure_does_not_emit_success_receipt(self):
        directory = self.bundle()
        (directory/'restore.json').unlink()
        inventory = {**self.config, 'database':b2b.policy()['restore_database'], 'database_oid':99999,
                     'instance_id':'00000000-0000-4000-8000-000000000002'}
        engine = MagicMock()
        with patch('manage.b2b_restore_config',return_value=inventory), patch('manage.b2b.transport',return_value={}), \
             patch('manage.b2b_confirm'), patch('manage.b2b_engine',return_value=engine), \
             patch('manage.b2b_identity'), patch('manage.b2b_pgtool',side_effect=ValueError('restore failed')), \
             self.assertRaises(ValueError):
            manage.b2b_rehearse(self.config,directory,self.target)
        self.assertFalse((directory/'restore.json').exists())

    def test_cli_exposes_safe_commit_phase_without_driver_details(self):
        for exception, code, marker in (
                (b2b.CommitUncertain('synthetic-sensitive-driver-details'),3,'B2B_COMMIT_UNCERTAIN'),
                (b2b.PostcheckFailed('synthetic-sensitive-driver-details'),4,'B2B_COMMIT_CONFIRMED_POSTCHECK_FAILED')):
            with self.subTest(code=code), patch('manage.main',side_effect=exception), patch('builtins.print') as output:
                self.assertEqual(manage.cli(),code)
                message = output.call_args.args[0]
                self.assertIn(marker,message)
                self.assertNotIn('synthetic-sensitive-driver-details',message)


class B2BAlembicCompatibilityTests(unittest.TestCase):
    def setUp(self):
        p = b2b.policy()
        config = {**p['destination'], '_path': p['profile'], '_directory': 'UNUSED-SYNTHETIC'}
        self.plan, self.bodies = manage.b2b_plan(config, p['target'])
        for name in ('manage.create_engine', 'manage.load_config', 'manage.db_url',
                     'sqlalchemy.engine.Engine.connect', 'sqlalchemy.engine.Engine.raw_connection',
                     'psycopg.connect', 'psycopg.Connection.connect', 'socket.socket.connect',
                     'socket.socket.connect_ex', 'socket.getaddrinfo', 'manage.subprocess.run'):
            guard = patch(name, side_effect=AssertionError('External I/O or secret read forbidden'))
            guard.start()
            self.addCleanup(guard.stop)

    def test_real_alembic_renders_all_four_approved_revisions_offline(self):
        from alembic.runtime.migration import MigrationContext
        configure = MigrationContext.configure
        output = io.StringIO()
        def offline(connection, opts):
            self.assertIsNone(connection)
            return configure(dialect_name='postgresql', opts={
                **opts, 'as_sql': True, 'starting_rev': manage.REVISION, 'output_buffer': output})
        with patch.object(MigrationContext, 'configure', side_effect=offline):
            APPLY_APPROVED_RELEASE(None, self.plan, self.bodies)
        sql = output.getvalue()
        self.assertEqual(sql.count('CREATE TABLE public.'), 6)
        self.assertEqual(sql.count('CREATE INDEX '), 5)
        self.assertEqual(sql.count('UPDATE public.alembic_version'), 4)
        for revision in self.plan['sequence']:
            self.assertIn("SET version_num='" + revision + "'", sql)
        self.assertNotIn('p101_prediction_operations', sql)
        self.assertNotIn('COMMIT;', sql)

    def test_real_alembic_keeps_the_existing_outer_transaction(self):
        from alembic.runtime.migration import MigrationContext
        from sqlalchemy.engine import Connection
        connection = MagicMock(spec=Connection)
        statements = recording_connection(connection)
        with patch.object(MigrationContext, 'get_current_heads', return_value=(manage.REVISION,)):
            APPLY_APPROVED_RELEASE(connection, self.plan, self.bodies)
        self.assertEqual(len(statements), 18)
        self.assertEqual(sum(s.startswith('UPDATE public.alembic_version') for s in statements), 4)
        self.assertFalse(any('p101_prediction_operations' in s for s in statements))
        connection.begin.assert_not_called()
        connection.commit.assert_not_called()
        connection.rollback.assert_not_called()


if __name__ == '__main__':
    unittest.main()
