"""Offline deployment tests. All external execution is forbidden by default."""
from datetime import timedelta
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import manage
import b2b_activation as activation
import b2b_deployment as d


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bundle = self.root / 'evidence' / 'qualification'
        self.bundle.mkdir(parents=True)
        approved = copy.deepcopy(d.policy.policy())
        approved['profile'] = str(self.root / 'config.json')
        self.config = {**approved['destination'], '_path': approved['profile'], '_directory': str(self.root)}
        p = patch.object(d.policy, 'policy', return_value=approved)
        p.start(); self.addCleanup(p.stop)
        for name in ('b2b_deployment.create_engine', 'manage.create_engine', 'psycopg.connect',
                     'sqlalchemy.engine.Engine.connect', 'socket.socket.connect', 'socket.getaddrinfo',
                     'manage.subprocess.run', 'manage.db_url'):
            p = patch(name, side_effect=AssertionError('External access forbidden'))
            p.start(); self.addCleanup(p.stop)
        self.deployment = d.Deployment(manage, self.config)
        self.inventory = {**self.config, 'database': d.RESTORE_DATABASE, 'database_oid': 999,
                          'instance_id': '11111111-1111-1111-1111-111111111111'}
        (self.root / 'b2b-locks-restore.json').write_text(json.dumps({k: self.inventory[k] for k in
            ('database', 'database_oid', 'instance_id', 'cluster_identifier')}), encoding='utf-8')
        self.snapshot = {'all_rows': 'synthetic-fingerprint'}
        self.archive = self.bundle / d.ARCHIVE
        self.archive.write_bytes(b'PGDMP synthetic offline fixture')
        self.backup = d.write_receipt(self.bundle, 'backup', self.deployment.plan,
            archive_sha256=d.policy.file_digest(self.archive), snapshot=self.snapshot, acl=[])
        stamp = d.read_receipt(self.bundle / 'backup.json')[1]
        d.write_receipt(self.bundle, 'restore', self.deployment.plan, backup_sha256=stamp,
            archive_sha256=self.backup['archive_sha256'], verified=True,
            destination={k: self.inventory[k] for k in ('database', 'database_oid', 'instance_id', 'cluster_identifier')})
        self.binding = self.deployment.evidence(self.bundle)[1]

    def install_receipt(self, stage='install'):
        return d.write_receipt(self.bundle, stage, self.deployment.plan, binding=self.binding,
                               commit_confirmed=True, postcheck_verified=True, objects={'synthetic': 1})

    def connection(self):
        c = MagicMock()
        c.__enter__.return_value = c
        return c

    def engine(self):
        engine = MagicMock()
        c = self.connection()
        engine.connect.return_value = c
        return engine, c

    def test_pinned_sources_and_five_exact_bodies(self):
        bodies = d.capture()
        self.assertEqual(len(bodies), 3)
        for f in d.locks.FUNCTIONS:
            self.assertEqual(d.policy.digest(f['body'].encode('utf-8')), f['sha256'])
            self.assertIn('$body$' + f['body'] + '$body$', bodies['b2b-lock-install.review.sql'])
        for body in bodies.values():
            self.assertNotIn('\r', body)
            self.assertNotEqual(body.rstrip()[-9:], 'ROLLBACK;')

    def test_changed_source_and_invalid_framing_refused(self):
        with patch.dict(d.PINS, {'b2b_locks.py': '0' * 64}):
            with self.assertRaisesRegex(ValueError, 'Unapproved'):
                d.capture()
        for sql in (b'BEGIN;\nROLLBACK;\n', b'\nBEGIN;\r\nROLLBACK;\r\n', b'\nBEGIN;\nCOMMIT;\n'):
            with self.subTest(sql=sql), self.assertRaises(ValueError):
                d.executable(sql)

    def test_full_inverse_exact_seven_objects_no_global_cleanup(self):
        sql = d.inverse_sql()
        drops = [line for line in sql.splitlines() if line.startswith('DROP ')]
        self.assertEqual(len(drops), 7)
        for f in d.locks.FUNCTIONS:
            self.assertIn('DROP FUNCTION ' + f['signature'] + ' RESTRICT;', drops)
        self.assertIn('DROP SCHEMA b2b_lock RESTRICT;', drops)
        self.assertIn('DROP ROLE ui47_b2b_lock_owner;', drops)
        for forbidden in ('CASCADE', 'DROP OWNED', 'DROP TABLE', 'DROP SEQUENCE', 'ALTER TABLE'):
            self.assertNotIn(forbidden, sql)
        reverse = self.deployment.bodies['b2b-auth-revoke.review.sql']
        self.assertEqual(sum(line.startswith('REVOKE ') for line in reverse.splitlines()), 16)

    def test_acl_algebra_preserves_industrial_and_no_sensitive_app_update(self):
        baseline = [('table', 'public.measurements', '', 'ui47_app', 'ui47_migrator', 'UPDATE', False)]
        closed = d.expected_acl(baseline, 'closed')
        granted = d.expected_acl(baseline, 'granted')
        self.assertTrue(set(closed) < set(granted))
        self.assertIn(baseline[0], granted)
        updates = [row for row in granted if row[3] == 'ui47_app' and row[5] == 'UPDATE' and row[0] == 'column']
        self.assertEqual({(r[1], r[2]) for r in updates}, {('public.application_sessions', c) for c in ('last_activity_at', 'revoked_at', 'replaced_by')})
        self.assertFalse(any(row[3] == 'PUBLIC' for row in granted))

    def test_archive_mutation_refused(self):
        self.archive.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Archive fingerprint'):
            self.deployment.evidence(self.bundle)

    def test_receipt_mutation_refused(self):
        p = self.bundle / 'backup.json'
        value = json.loads(p.read_text())
        value['payload']['snapshot'] = {}
        p.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'fingerprint'):
            self.deployment.evidence(self.bundle)

    def test_expired_future_and_cross_plan_evidence_refused(self):
        p = self.bundle / 'restore.json'
        original = json.loads(p.read_text())['payload']
        for mutation in ({'created_at': (d.utcnow() - timedelta(hours=25)).isoformat()},
                         {'created_at': (d.utcnow() + timedelta(minutes=1)).isoformat()},
                         {'plan_sha256': 'wrong'}, {'backup_sha256': 'wrong'}, {'verified': False}):
            with self.subTest(mutation=mutation):
                p.write_text(json.dumps(d.seal({**original, **mutation})))
                with self.assertRaises(ValueError):
                    self.deployment.evidence(self.bundle)

    def test_restore_cannot_target_active_inventory(self):
        p = self.root / 'b2b-locks-restore.json'
        original = json.loads(p.read_text())
        for change in ({'database': self.config['database']}, {'database_oid': self.config['database_oid']},
                       {'instance_id': self.config['instance_id']}, {'cluster_identifier': 'other'}):
            p.write_text(json.dumps({**original, **change}))
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.deployment.restore_inventory()

    def test_profile_and_destination_fail_closed(self):
        for change in ({'runtime_profile': activation.CANDIDATE}, {'db_port': 5433}, {'database': 'other'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                d.Deployment(manage, {**self.config, **change})

    def test_wrong_identity_and_revision_using_real_manager_check(self):
        c = self.connection()
        proof = {**self.config, 'role': 'ui47_migrator', 'version': '17.10',
            'cluster_name': 'industrial-predict-development', 'superuser': False,
            'createdb': False, 'createrole': False, 'replication': False, 'bypassrls': False}
        c.execute.return_value.mappings.return_value.one.return_value = proof
        c.execute.return_value.scalar_one.return_value = manage.REVISION
        with self.assertRaisesRegex(ValueError, 'migration mismatch'):
            self.deployment.identity(c, 'migrator')
        c.execute.return_value.scalar_one.return_value = d.REVISION
        proof['database_oid'] = -1
        with self.assertRaisesRegex(ValueError, 'identity mismatch'):
            self.deployment.identity(c, 'migrator')

    def test_tls_rejected_before_password_or_engine(self):
        with patch.object(manage, 'runtime_connect_args', side_effect=ValueError('Unapproved CA')):
            with self.assertRaisesRegex(ValueError, 'Unapproved CA'):
                self.deployment.engine('app')
        manage.db_url.assert_not_called()
        d.create_engine.assert_not_called()

    def test_empty_restore_refuses_residual_tables_relations_routines_types(self):
        for residual in ('table', 'relation', 'routine', 'type'):
            with self.subTest(residual=residual):
                c = self.connection()
                def execute(sql):
                    result = MagicMock()
                    result.scalar_one.return_value = (self.config['cluster_identifier'] if 'system_identifier' in sql else
                        True if 'SELECT ssl' in sql or 'Unsafe' in sql or "rolname='ui47_migrator'" in sql else 'ui47_migrator' if 'nspowner' in sql else
                        int((residual == 'relation' and 'pg_class' in sql) or (residual == 'routine' and 'pg_proc' in sql) or (residual == 'type' and 'pg_type' in sql)))
                    result.scalars.return_value = ['public']
                    result.all.return_value = [('public.leftover', 'ui47_migrator')] if residual == 'table' else []
                    return result
                c.exec_driver_sql.side_effect = execute
                with patch.object(manage, 'inspect_connection', return_value={'superuser': False}), self.assertRaisesRegex(ValueError, 'not empty|Residual'):
                    self.deployment.identity(c, 'migrator', self.inventory, empty=True)

    def test_backup_orchestrates_complete_custom_export_and_readback(self):
        engine, c = self.engine()
        c.execution_options.return_value = c
        c.exec_driver_sql.return_value.scalar_one.return_value = 'approved-exported-snapshot'
        destination = self.bundle.parent / 'new-backup'
        calls = []
        def pgtool(config, name, args):
            calls.append((name, args))
            for arg in args:
                if arg.startswith('--file='):
                    Path(arg.removeprefix('--file=')).write_bytes(b'synthetic archive/readback')
            return b'synthetic table of contents'
        with patch.object(self.deployment, 'confirm'), patch.object(self.deployment, 'engine', return_value=engine), patch.object(self.deployment, 'identity'), patch.object(self.deployment, 'state', return_value='absent'), patch.object(self.deployment, 'snapshot', return_value=self.snapshot), patch.object(self.deployment, 'acl', return_value=[]), patch.object(manage, 'b2b_pgtool', side_effect=pgtool):
            receipt = self.deployment.backup(destination)
        self.assertEqual(receipt['stage'], 'backup')
        self.assertEqual(calls[0], ('pg_dump', ['--dbname=industrial_predict_dev', '--format=custom', '--snapshot=approved-exported-snapshot', '--file=' + str(destination.resolve() / d.ARCHIVE)]))
        self.assertEqual([name for name, _ in calls], ['pg_dump', 'pg_restore', 'pg_restore'])
        self.assertEqual(d.policy.file_digest(destination / d.ARCHIVE), receipt['archive_sha256'])

    def test_restore_orchestrates_only_explicit_isolated_destination(self):
        (self.bundle / 'restore.json').unlink()
        engine, c = self.engine()
        with patch.object(self.deployment, 'confirm'), patch.object(self.deployment, 'engine', return_value=engine) as factory, patch.object(self.deployment, 'identity') as identity, patch.object(self.deployment, 'snapshot', return_value=self.snapshot), patch.object(self.deployment, 'acl', return_value=[]), patch.object(manage, 'b2b_pgtool', return_value=b'') as pgtool:
            receipt = self.deployment.rehearse(self.bundle)
        factory.assert_called_once_with('migrator', self.inventory)
        self.assertTrue(identity.call_args_list[0].kwargs['empty'])
        self.assertEqual(pgtool.call_args.args[2], ['--dbname=' + d.RESTORE_DATABASE, '--exit-on-error', '--single-transaction', str(self.archive.resolve())])
        self.assertTrue(receipt['verified'])

    def test_nonempty_restore_stops_before_pg_restore(self):
        engine, c = self.engine()
        with patch.object(self.deployment, 'confirm'), patch.object(self.deployment, 'engine', return_value=engine), patch.object(self.deployment, 'identity', side_effect=ValueError('not empty')), patch.object(manage, 'b2b_pgtool') as pgtool:
            with self.assertRaisesRegex(ValueError, 'not empty'):
                self.deployment.rehearse(self.bundle)
        pgtool.assert_not_called()
        self.assertFalse((self.bundle / 'restore-intent.json').exists())

    def test_restore_drift_produces_no_success_evidence_and_no_retry(self):
        (self.bundle / 'restore.json').unlink()
        engine, c = self.engine()
        with patch.object(self.deployment, 'confirm'), patch.object(self.deployment, 'engine', return_value=engine), patch.object(self.deployment, 'identity'), patch.object(self.deployment, 'snapshot', return_value={'changed': True}), patch.object(manage, 'b2b_pgtool', return_value=b'') as pgtool:
            with self.assertRaisesRegex(ValueError, 'Restore verification'):
                self.deployment.rehearse(self.bundle)
            with self.assertRaisesRegex(ValueError, 'No automatic repeat'):
                self.deployment.rehearse(self.bundle)
        self.assertEqual(pgtool.call_count, 1)
        self.assertFalse((self.bundle / 'restore.json').exists())

    def test_snapshot_covers_six_b2b_alembic_and_eleven_sequences(self):
        c = self.connection()
        c.exec_driver_sql.return_value.scalars.return_value = []
        c.exec_driver_sql.return_value.one.return_value = (1, False)
        with patch.object(manage, 'b2b_snapshot', return_value={'industrial': 'preserved'}):
            value = self.deployment.snapshot(c)
        self.assertEqual(set(value['b2b_rows']), set(manage.B2B_TABLES) | {'alembic_version'})
        self.assertEqual(set(value['sequence_values']), manage.BUSINESS_SEQUENCES | manage.B2B_SEQUENCES)
        self.assertEqual(len(self.deployment.tables), 15)
        self.assertNotIn('rolpassword', ' '.join(call.args[0] for call in c.exec_driver_sql.call_args_list))

    def test_transact_success_commits_once_and_independent_postcheck(self):
        engine, c = self.engine()
        work, post = MagicMock(return_value='result'), MagicMock()
        self.assertEqual(self.deployment.transact(engine, work, post), 'result')
        c.begin.return_value.commit.assert_called_once()
        c.begin.return_value.rollback.assert_not_called()
        self.assertEqual(engine.connect.call_count, 2)
        post.assert_called_once_with(c)
        engine.dispose.assert_called_once()

    def test_work_failure_rolls_back_no_commit_no_postcheck(self):
        engine, c = self.engine()
        post = MagicMock()
        with self.assertRaisesRegex(ValueError, 'precommit'):
            self.deployment.transact(engine, MagicMock(side_effect=ValueError('precommit')), post)
        c.begin.return_value.rollback.assert_called_once()
        c.begin.return_value.commit.assert_not_called()
        post.assert_not_called()

    def test_commit_uncertain_never_retries_or_claims_rollback(self):
        engine, c = self.engine()
        c.begin.return_value.commit.side_effect = OSError('lost acknowledgement')
        post = MagicMock()
        with self.assertRaises(d.policy.CommitUncertain):
            self.deployment.transact(engine, MagicMock(), post)
        self.assertEqual(engine.connect.call_count, 1)
        c.begin.return_value.rollback.assert_not_called()
        post.assert_not_called()

    def test_disposal_failure_cannot_hide_uncertain_commit(self):
        engine, c = self.engine()
        c.begin.return_value.commit.side_effect = OSError('lost acknowledgement')
        engine.dispose.side_effect = OSError('disposal failed')
        with self.assertRaises(d.policy.CommitUncertain):
            self.deployment.transact(engine, MagicMock(), MagicMock())
        c.begin.return_value.commit.assert_called_once()
        c.begin.return_value.rollback.assert_not_called()

    def test_postcheck_failure_reports_confirmed_commit(self):
        engine, c = self.engine()
        with self.assertRaises(d.policy.PostcheckFailed):
            self.deployment.transact(engine, MagicMock(), MagicMock(side_effect=ValueError('drift')))
        c.begin.return_value.commit.assert_called_once()
        c.begin.return_value.rollback.assert_not_called()

    def test_every_operation_requires_approval_before_connection(self):
        self.install_receipt()
        for action in ('install', 'grant', 'rollback'):
            with self.subTest(action=action), patch.object(self.deployment, 'confirm', side_effect=ValueError('No approval')), patch.object(self.deployment, 'engine') as engine:
                with self.assertRaisesRegex(ValueError, 'No approval'):
                    self.deployment.operate(self.bundle, action)
                engine.assert_not_called()
        self.assertFalse(list(self.bundle.glob('intent-*')))

    def test_confirmation_prints_reviewable_inventory_without_private_config(self):
        self.config['private_sentinel'] = 'must-never-appear'
        with patch('sys.stdout', new_callable=io.StringIO) as output, patch.object(manage, 'b2b_confirm') as confirm:
            self.deployment.confirm('INSTALL-B2B-LOCKS-A', self.bundle, **self.binding)
        report = json.loads(output.getvalue())
        self.assertEqual(report['plan'], self.deployment.plan)
        self.assertNotIn('must-never-appear', output.getvalue())
        self.assertEqual(confirm.call_args.args[0], 'INSTALL-B2B-LOCKS-A')

    def test_backup_and_restore_require_distinct_approvals(self):
        for operation, path in ((self.deployment.backup, self.bundle.parent / 'new'), (self.deployment.rehearse, self.bundle)):
            with patch.object(self.deployment, 'confirm', side_effect=ValueError('No approval')), patch.object(self.deployment, 'engine') as engine:
                with self.assertRaisesRegex(ValueError, 'No approval'):
                    operation(path)
                engine.assert_not_called()
        self.assertFalse((self.bundle.parent / 'new').exists())

    def test_stage_b_requires_proven_stage_a(self):
        with patch.object(self.deployment, 'confirm') as confirm, self.assertRaises(ValueError):
            self.deployment.operate(self.bundle, 'grant')
        confirm.assert_not_called()

    def test_install_and_grant_are_never_combined(self):
        self.install_receipt()
        for action, token in (('install', 'INSTALL-B2B-LOCKS-A'), ('grant', 'GRANT-B2B-LOCKS-B')):
            with patch.object(self.deployment, 'confirm') as confirm, patch.object(self.deployment, 'verify_restore'), patch.object(self.deployment, '_step') as step:
                self.deployment.operate(self.bundle, action)
                step.assert_called_once_with(self.bundle, action, self.backup, self.binding)
                self.assertEqual(confirm.call_args.args[0], token)

    def test_attempt_marker_blocks_retry_and_ambiguous_inverse(self):
        self.install_receipt()
        (self.bundle / 'intent-grant.json').write_text('{}')
        for action in ('grant', 'rollback'):
            with self.subTest(action=action), patch.object(self.deployment, 'engine') as engine, self.assertRaises(ValueError):
                self.deployment.operate(self.bundle, action)
            engine.assert_not_called()

    def test_inverse_only_for_proven_delta_and_in_actor_order(self):
        self.install_receipt()
        self.install_receipt('grant')
        (self.bundle / 'intent-grant.json').write_text('{}')
        with patch.object(self.deployment, 'confirm'), patch.object(self.deployment, 'verify_restore'), patch.object(self.deployment, '_step', return_value={'post_state': 'absent'}) as step:
            result = self.deployment.operate(self.bundle, 'rollback')
        self.assertEqual([call.args[1] for call in step.call_args_list], ['rollback-acl', 'remove'])
        self.assertTrue(result['removed'])

    def test_inverse_stops_on_acl_substep_failure(self):
        self.install_receipt(); self.install_receipt('grant')
        (self.bundle / 'intent-grant.json').write_text('{}')
        with patch.object(self.deployment, 'confirm'), patch.object(self.deployment, 'verify_restore'), patch.object(self.deployment, '_step', side_effect=d.policy.CommitUncertain('stop')) as step:
            with self.assertRaises(d.policy.CommitUncertain):
                self.deployment.operate(self.bundle, 'rollback')
        self.assertEqual(step.call_count, 1)
        self.assertFalse((self.bundle / 'rollback.json').exists())

    def step_fixture(self, state='absent', acl=None, snapshot=None):
        c = self.connection()
        def execute(sql, **kwargs):
            value = MagicMock()
            value.scalar_one.return_value = True if 'pg_try_advisory' in sql else 0
            return value
        c.exec_driver_sql.side_effect = execute
        for name, value in (('identity', None), ('state', state), ('snapshot', self.snapshot if snapshot is None else snapshot),
                            ('acl', [] if acl is None else acl), ('engine', MagicMock())):
            p = patch.object(self.deployment, name, return_value=value)
            p.start(); self.addCleanup(p.stop)
        p = patch.object(self.deployment, 'transact', side_effect=lambda engine, work, post: work(c))
        p.start(); self.addCleanup(p.stop)
        return c

    def test_source_drift_and_excess_acl_block_before_write(self):
        c = self.step_fixture(snapshot={'changed': True})
        with self.assertRaisesRegex(ValueError, 'drift'):
            self.deployment._step(self.bundle, 'install', self.backup, self.binding)
        self.assertFalse(any('CREATE ROLE' in call.args[0] for call in c.exec_driver_sql.call_args_list))

    def test_extra_or_missing_acl_blocks_before_write(self):
        c = self.step_fixture(acl=[('column', 'public.local_users', 'id', 'ui47_app', 'ui47_migrator', 'UPDATE', False)])
        with self.assertRaisesRegex(ValueError, 'ACL delta'):
            self.deployment._step(self.bundle, 'install', self.backup, self.binding)
        self.assertFalse(any('CREATE ROLE' in call.args[0] for call in c.exec_driver_sql.call_args_list))

    def test_missing_technical_grant_blocks_stage_b(self):
        self.install_receipt()
        c = self.step_fixture(state='closed', acl=d.expected_acl([], 'closed')[1:])
        with self.assertRaisesRegex(ValueError, 'ACL delta'):
            self.deployment._step(self.bundle, 'grant', self.backup, self.binding)
        self.assertFalse(any('GRANT SELECT' in call.args[0] for call in c.exec_driver_sql.call_args_list))

    def test_function_hash_metadata_and_public_checks_reused_fail_closed(self):
        # Exercise the actual existing checker with all scalar results expected,
        # then independently corrupt hash/metadata and PUBLIC-related results.
        checks = list(d.locks.checks(app_access=False, columns=activation.COLUMNS))
        for label in (d.locks.FUNCTIONS[0]['signature'], d.locks.FUNCTIONS[0]['signature'] + ' ACL', 'lock schema public/delegation'):
            c = self.connection()
            outcomes = {query: wanted for _, query, wanted in checks}
            outcomes["SELECT to_regnamespace('b2b_lock')::text"] = 'b2b_lock'
            query = next(query for name, query, wanted in checks if name == label)
            outcomes[query] = 999
            def execute(sql):
                result = MagicMock()
                result.scalar_one.return_value = outcomes[sql]
                return result
            c.exec_driver_sql.side_effect = execute
            with self.subTest(label=label), self.assertRaises(ValueError):
                activation.inspect_lock_acl(c, app_access=False)

    def test_approved_evidence_cannot_be_swapped_before_write(self):
        c = self.step_fixture()
        with patch.object(self.deployment, 'evidence', return_value=(self.backup, {**self.binding, 'restore_sha256': 'swapped'})), self.assertRaisesRegex(ValueError, 'evidence changed'):
            self.deployment._step(self.bundle, 'install', self.backup, self.binding)
        self.assertFalse(any('CREATE ROLE' in call.args[0] for call in c.exec_driver_sql.call_args_list))

    def test_independent_app_connection_failure_is_postcommit_failure(self):
        with patch.object(self.deployment, 'engine', side_effect=[MagicMock(), ValueError('app unavailable')]), patch.object(self.deployment, 'transact', return_value={'post_state': 'closed'}):
            with self.assertRaises(d.policy.PostcheckFailed):
                self.deployment._step(self.bundle, 'install', self.backup, self.binding)
        self.assertFalse((self.bundle / 'install.json').exists())

    def test_stage_a_precommit_postcommit_and_app_checks(self):
        engine, c = self.engine()
        app, app_c = self.engine()
        def query(sql, **kwargs):
            result = MagicMock()
            result.scalar_one.return_value = True if 'pg_try_advisory' in sql else 0
            return result
        c.exec_driver_sql.side_effect = query
        with patch.object(self.deployment, 'engine', side_effect=[engine, app]) as engines, patch.object(self.deployment, 'object_ids', return_value={'synthetic': 1}), patch.object(self.deployment, 'identity'), patch.object(self.deployment, 'state', side_effect=['absent', 'closed', 'closed']), patch.object(self.deployment, 'snapshot', return_value=self.snapshot), patch.object(self.deployment, 'acl', side_effect=[[], d.expected_acl([], 'closed'), d.expected_acl([], 'closed')]), patch.object(manage, 'inspect_runtime_connection') as app_identity, patch.object(manage, 'inspect_runtime_schema') as app_schema:
            result = self.deployment._step(self.bundle, 'install', self.backup, self.binding)
        self.assertTrue(result['postcheck_verified'])
        self.assertEqual([call.args[0] for call in engines.call_args_list], ['admin', 'app'])
        c.begin.return_value.commit.assert_called_once()
        app_identity.assert_called_once_with(app_c, self.config)
        app_schema.assert_called_once_with(app_c, profile=activation.PREPARATION)
        sql = [call.args[0] for call in c.exec_driver_sql.call_args_list]
        body = self.deployment.bodies['b2b-lock-install.review.sql']
        self.assertIn(body, sql)
        self.assertTrue(any(s.startswith('LOCK TABLE public.companies') for s in sql))
        self.assertNotIn(self.deployment.bodies['b2b-auth-grants.review.sql'], sql)

    def test_replaced_objects_block_inverse_before_drop(self):
        self.install_receipt()
        c = self.step_fixture(state='closed', acl=d.expected_acl([], 'closed'))
        with patch.object(self.deployment, 'object_ids', return_value={'synthetic': 2}), self.assertRaisesRegex(ValueError, 'objects replaced'):
            self.deployment._step(self.bundle, 'remove', self.backup, self.binding)
        self.assertFalse(any('DROP FUNCTION' in call.args[0] for call in c.exec_driver_sql.call_args_list))

    def test_candidate_cli_rejected_for_deployment_too(self):
        with patch('sys.argv', ['manage.py', 'b2b-locks-grant', '--config', 'not-read', '--runtime-profile', activation.CANDIDATE]), patch.object(manage, 'load_config') as load:
            with self.assertRaises(SystemExit):
                manage.main()
            load.assert_not_called()

    def test_runtime_candidate_cannot_launch_via_cli(self):
        with patch('sys.argv', ['manage.py', 'api', '--config', 'not-read', '--runtime-profile', activation.CANDIDATE]), patch.object(manage, 'load_config') as load:
            with self.assertRaises(SystemExit):
                manage.main()
            load.assert_not_called()

    def test_cli_dispatches_only_requested_stage(self):
        for action in ('install', 'grant', 'rollback'):
            with patch('sys.argv', ['manage.py', 'b2b-locks-' + action, '--config', 'not-read', '--bundle', 'private']), patch.object(manage, 'load_config', return_value=self.config), patch.object(d, 'Deployment') as factory:
                factory.return_value.operate.return_value = {'stage': action}
                manage.main()
                factory.return_value.operate.assert_called_once_with('private', action)


if __name__ == '__main__':
    unittest.main()
