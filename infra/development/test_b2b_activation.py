"""Targeted offline ACL/profile tests. Real connections and secrets forbidden."""
import contextlib
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import b2b_activation as activation
import manage


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        for name in ('sqlalchemy.engine.Engine.connect', 'psycopg.connect',
                     'psycopg.Connection.connect', 'socket.socket.connect', 'socket.getaddrinfo'):
            patch(name, side_effect=AssertionError('Network/DB forbidden')).start()

    def connection(self, *, profile=activation.CANDIDATE, role='ui47_app', memberships=0,
                   unsafe=False, changed_shape=None, flip_table=None, flip_column=None):
        expected = activation.matrix(profile)
        connection = MagicMock()
        def driver(sql):
            result = MagicMock()
            if sql == 'SELECT current_user':
                result.scalar_one.return_value = role
            elif 'pg_auth_members' in sql:
                result.scalar_one.return_value = memberships
            else:
                raise AssertionError('Unexpected SQL')
            return result
        def execute(statement, params):
            sql = str(statement)
            table = params['name'].split('.')[1]
            result = MagicMock()
            if 'SELECT a.attname' in sql:
                columns = activation.COLUMNS[table]
                result.scalars.return_value.all.return_value = (
                    (*columns, 'unexpected') if table == changed_shape else columns)
            elif 'aclexplode' in sql:
                self.assertIn('grantee=0', sql)
                self.assertIn('is_grantable', sql)
                self.assertIn('a.attacl', sql)
                result.scalar_one.return_value = int(unsafe)
            elif 'has_table_privilege' in sql:
                key = (table, params['privilege'])
                value = params['privilege'] in expected[table]['table']
                result.scalar_one.return_value = not value if key == flip_table else value
            elif 'has_column_privilege' in sql:
                key = (table, params['column'], params['privilege'])
                value = params['column'] in expected[table]['columns'].get(params['privilege'], ())
                result.scalar_one.return_value = not value if key == flip_column else value
            else:
                raise AssertionError('Unexpected SQL')
            return result
        connection.exec_driver_sql.side_effect = driver
        connection.execute.side_effect = execute
        return connection

    def test_exact_candidate_is_accepted_only_as_acl_qualification(self):
        connection = self.connection()
        proof = activation.inspect_acl(connection, profile=activation.CANDIDATE)
        self.assertTrue(proof['acl_exact'])
        self.assertFalse(proof['activation_available'])
        connection.commit.assert_not_called()
        self.assertTrue(all(str(c.args[0]).lstrip().startswith('SELECT')
                            for c in connection.execute.call_args_list))

    def test_each_missing_or_excessive_table_and_column_privilege_is_rejected(self):
        for table, columns in activation.COLUMNS.items():
            for privilege in activation.TABLE_PRIVILEGES:
                with self.subTest(table=table, privilege=privilege), self.assertRaises(ValueError):
                    activation.inspect_acl(self.connection(flip_table=(table, privilege)), profile=activation.CANDIDATE)
            for column in columns:
                for privilege in activation.COLUMN_PRIVILEGES:
                    with self.subTest(table=table, column=column, privilege=privilege), self.assertRaises(ValueError):
                        activation.inspect_acl(self.connection(flip_column=(table, column, privilege)), profile=activation.CANDIDATE)

    def test_public_grants_or_grant_options_fail_even_with_matching_effective_rights(self):
        with self.assertRaisesRegex(ValueError, 'PUBLIC or delegable'):
            activation.inspect_acl(self.connection(unsafe=True), profile=activation.CANDIDATE)

    def test_inherited_or_switchable_roles_and_wrong_sql_roles_fail(self):
        for changes in ({'memberships': 1}, {'role': 'ui47_migrator'}, {'role': 'ui47_admin'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                activation.inspect_acl(self.connection(**changes), profile=activation.CANDIDATE)

    def test_extra_or_missing_column_shape_fails(self):
        for table in activation.COLUMNS:
            with self.subTest(table=table), self.assertRaises(ValueError):
                activation.inspect_acl(self.connection(changed_shape=table), profile=activation.CANDIDATE)

    def test_preparation_cannot_accept_candidate_acl(self):
        with self.assertRaises(ValueError):
            activation.inspect_acl(self.connection(), profile=activation.PREPARATION)
        self.assertTrue(activation.inspect_acl(self.connection(profile=activation.PREPARATION),
                        profile=activation.PREPARATION)['acl_exact'])

    def test_unknown_implicit_and_explicit_activation_are_blocked_before_resources(self):
        with patch('manage.runtime_engine') as engine, patch('manage.inspect_db') as inspect:
            for config, profile in (({}, activation.CANDIDATE), ({'runtime_profile': activation.CANDIDATE}, activation.PREPARATION),
                                    ({'runtime_profile': None}, activation.PREPARATION), ({}, 'unknown')):
                with self.subTest(config=config, profile=profile), self.assertRaises(ValueError):
                    manage.prepare_runtime_app(config, profile=profile)
            for operation in (manage.api, manage.frontend):
                with self.assertRaises(ValueError):
                    operation({'runtime_profile': activation.CANDIDATE})
            engine.assert_not_called()
            inspect.assert_not_called()

    def test_cli_candidate_cannot_launch_any_other_action_or_read_private_config(self):
        for action in ('api', 'frontend', 'check-db', 'migrate', 'b2b-migrate', 'db-start'):
            with (self.subTest(action=action), patch('sys.argv', ['manage.py', action, '--config', 'unread',
                    '--runtime-profile', activation.CANDIDATE]), patch('manage.load_config') as load,
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit)):
                manage.main()
            load.assert_not_called()

    def test_offline_plan_needs_explicit_profile_and_approved_path_without_private_io(self):
        path = manage.b2b.policy()['profile']
        for args, valid in (([], False), (['--runtime-profile', activation.CANDIDATE], True)):
            output = io.StringIO()
            with patch('sys.argv', ['manage.py', 'b2b-auth-plan', '--config', path, '--role', 'ui47_app', *args]), \
                    patch('manage.load_config', side_effect=AssertionError('Private profile forbidden')), \
                    patch('manage.db_url', side_effect=AssertionError('Secret forbidden')), \
                    patch('manage.create_engine', side_effect=AssertionError('Engine forbidden')), \
                    contextlib.redirect_stdout(output):
                if valid:
                    manage.main()
                    proof = json.loads(output.getvalue())
                    self.assertEqual(proof['role'], 'ui47_app')
                    self.assertEqual(proof['revision'], 'b2b_0002_analyze')
                    self.assertFalse(proof['live_checks_performed'])
                    self.assertFalse(proof['activation_available'])
                    self.assertFalse(proof['google_routes_enabled'])
                else:
                    with self.assertRaises(ValueError):
                        manage.main()
        with patch('sys.argv', ['manage.py', 'b2b-auth-plan', '--config', 'wrong',
                '--role', 'ui47_app', '--runtime-profile', activation.CANDIDATE]), contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit):
            manage.main()

    def test_cli_plan_refuses_migrator_or_admin_as_application_role(self):
        for role in ('ui47_migrator', 'ui47_admin'):
            with patch('sys.argv', ['manage.py', 'b2b-auth-plan', '--config', 'unread', '--role', role,
                    '--runtime-profile', activation.CANDIDATE]), contextlib.redirect_stderr(io.StringIO()), \
                    self.assertRaises(SystemExit):
                manage.main()

    def test_matrix_matches_locking_and_session_operations_without_provisioning(self):
        rights = activation.matrix(activation.CANDIDATE)
        self.assertEqual(rights['local_users']['columns'], {'SELECT': ['id', 'state'], 'UPDATE': ['id']})
        self.assertEqual(rights['membership_permissions']['columns']['UPDATE'], ['membership_id'])
        self.assertEqual(rights['application_sessions']['columns']['UPDATE'],
                         ['last_activity_at', 'revoked_at', 'replaced_by'])
        self.assertEqual(rights['oidc_transactions']['table'], ['DELETE'])
        self.assertEqual(rights['oidc_transactions']['columns']['UPDATE'], ['transaction_id'])
        self.assertEqual({t for t, r in rights.items() if 'INSERT' in r['columns']},
                         {'application_sessions', 'oidc_transactions'})

    def test_sql_templates_are_inverse_column_scoped_and_rollback_by_default(self):
        grant, revoke = activation.sql_delta(), activation.sql_delta(reverse=True)
        self.assertTrue(grant.endswith('ROLLBACK;'))
        self.assertTrue(revoke.endswith('ROLLBACK;'))
        self.assertIn('BEGIN;', grant)
        self.assertIn('END; $guard$;', grant)
        statements = [line for line in grant.splitlines() if line.startswith('GRANT ')]
        inverse = [line for line in revoke.splitlines() if line.startswith('REVOKE ')]
        self.assertEqual(inverse, [s.replace('GRANT ', 'REVOKE ', 1).replace(' TO ui47_app;', ' FROM ui47_app;')
                                  for s in statements])
        self.assertEqual(len(statements), 15)
        for forbidden in ('CASCADE', 'ALL PRIVILEGES', 'SEQUENCE', 'PUBLIC;', 'WITH GRANT OPTION', 'INSERT INTO', 'DELETE FROM'):
            self.assertNotIn(forbidden, grant)
            self.assertNotIn(forbidden, revoke)

    def test_review_files_equal_plan_and_column_lists_match_approved_migrations(self):
        import ast
        from pathlib import Path
        directory = Path(__file__).parent
        self.assertEqual((directory / 'b2b-auth-grants.review.sql').read_text(encoding='utf-8'),
                         activation.sql_delta() + '\n')
        self.assertEqual((directory / 'b2b-auth-revoke.review.sql').read_text(encoding='utf-8'),
                         activation.sql_delta(reverse=True) + '\n')
        versions = directory.parents[1] / 'backend' / 'general_migrations' / 'versions'
        found = {}
        for filename in ('12e2fc65f372_create_oidc_transactions.py',
                         '4b7e2a91c6d0_create_professional_accounts.py', 'b2b_0001_sessions.py'):
            for node in ast.walk(ast.parse((versions / filename).read_text(encoding='utf-8'))):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'create_table'):
                    found[node.args[0].value] = tuple(arg.args[0].value for arg in node.args[1:]
                        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) and arg.func.attr == 'Column')
        self.assertEqual(found, activation.COLUMNS)


if __name__ == '__main__':
    unittest.main()
