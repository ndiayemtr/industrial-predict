"""Official auth-only launcher, synthetic files/SQL catalog and in-process ASGI.

No actual PostgreSQL, Docker, Google, private DEV configuration or HTTPS server.
"""
import asyncio
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

import httpx

import manage
import test_manage as runtime_support
import test_b2b_activation as acl_support


class AuthLauncherTests(unittest.TestCase):
    def setUp(self):
        # Windows' private asyncio wakeup pair is the only local socket pair.
        self.loop = asyncio.new_event_loop()
        self.addCleanup(self.close_loop)
        self.support = runtime_support.RuntimePreparationTests('test_runtime_engine_pins_tls_and_app_role_without_environment_url')
        self.support.setUp()
        self.addCleanup(self.support.doCleanups)
        self.config = self.support.config
        directory = Path(self.support.temp.name)
        self.config.update(_path=str(directory/'config.json'), mode='local-development')
        (directory/'config.json').write_text('{}', encoding='utf-8')
        policy = manage.b2b.policy()
        patch('manage.b2b.policy', return_value={**policy, 'profile': self.config['_path']}).start()
        self.file = directory/'auth-only.json'
        self.secret = directory/'google-client-secret.txt'
        self.secret.write_text('synthetic-google-secret\n', encoding='utf-8')
        self.settings = {'profile': 'auth-only', 'origin': 'https://localhost:4443',
            'approved_domains': ['factory.example'], 'oidc': {
                'issuer': 'https://accounts.google.com', 'client_id': 'synthetic-client',
                'callback_url': 'https://localhost:4443/auth/oidc/google/callback',
                'signature_algorithms': ['RS256'], 'deployment_mode': 'development',
                'transaction_ttl_seconds': 300, 'clock_skew_seconds': 0, 'max_id_token_age_seconds': 300}}
        self.write()
        engine = self.support.engine_factory.return_value
        engine.echo = False
        engine.hide_parameters = True
        engine.logger.isEnabledFor.return_value = False
        self.transport = Mock(spec=httpx.BaseTransport)
        patch('httpx.HTTPTransport', return_value=self.transport).start()
        patch('manage.subprocess.run', side_effect=AssertionError('No process/Docker')).start()
        self.connection()

    def write(self):
        self.file.write_text(json.dumps(self.settings), encoding='utf-8')

    def close_loop(self):
        self.loop.run_until_complete(self.loop.shutdown_asyncgens())
        self.loop.run_until_complete(self.loop.shutdown_default_executor())
        self.loop.close()

    def connection(self, *, acl_changes=None, **changes):
        connection, state = self.support.connection(**changes)
        acl = acl_support.ActivationTests().connection(**(acl_changes or {}))
        execute = connection.execute.side_effect
        driver = connection.exec_driver_sql.side_effect
        lock_sql = {sql for _, sql, _ in manage.activation.locks.checks(
            app_access=True, columns=manage.activation.COLUMNS)}
        def dispatch(statement, params=None):
            if (params and 'role' in params) or str(statement) in lock_sql:
                return acl.execute(statement, params)
            return execute(statement, params)
        connection.execute.side_effect = dispatch
        connection.exec_driver_sql.side_effect = lambda sql: (
            acl.exec_driver_sql(sql) if sql == 'SELECT current_user' or 'to_regnamespace' in sql else driver(sql))
        self.sql = connection
        return state

    def request(self, app, path, *, origin='https://localhost:4443', method='GET'):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=origin) as client:
                return await client.request(method, path)
        return self.loop.run_until_complete(send())

    def test_only_explicit_cli_api_and_app_role_can_select_auth_only(self):
        args = ['manage.py', 'api', '--config', 'synthetic-unread', '--runtime-profile', 'auth-only', '--role', 'ui47_app']
        with patch('sys.argv', args), patch('manage.load_config', return_value=self.config), patch('manage.api') as launch:
            manage.main()
        launch.assert_called_once_with(self.config, profile=manage.AUTH_ONLY)
        with patch('sys.argv', ['manage.py', 'api', '--config', 'synthetic-unread']), \
                patch('manage.load_config', return_value=self.config), patch('manage.api') as launch:
            manage.main()
        launch.assert_called_once_with(self.config)

    def test_auth_only_flag_cannot_reach_other_commands_or_migration_options(self):
        variants = [([action], []) for action in ('frontend', 'check-db', 'migrate', 'db-start', 'db-stop', 'b2b-migrate', 'b2b-locks-install')]
        variants += [(['api'], extra) for extra in ([], ['--role', 'ui47_admin'], ['--role', 'ui47_migrator'],
            ['--role', 'ui47_app', '--bundle', 'no'], ['--role', 'ui47_app', '--qualification-campaign', 'no'],
            ['--role', 'ui47_app', '--current-revision', manage.RUNTIME_REVISION])]
        for action, extra in variants:
            with self.subTest(action=action, extra=extra), patch('sys.argv', ['manage.py', *action, '--config', 'unread',
                    '--runtime-profile', 'auth-only', *extra]), patch('manage.load_config') as load, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                manage.main()
            load.assert_not_called()

    def test_base_profile_or_companion_cannot_activate_preparation_implicitly(self):
        app = manage.prepare_runtime_app(self.config)
        self.assertEqual({r.path for r in app.routes}, {'/health', '/__dev/identity'})
        self.support.engine_factory.return_value.connect.assert_not_called()
        with self.assertRaises(ValueError):
            manage.prepare_auth_only_app({**self.config, 'runtime_profile': 'auth-only'})

    def test_absent_malformed_and_ambiguous_settings_fail_before_engine_creation(self):
        for body in (None, '{}', '{', '{"profile":"auth-only","profile":"auth-only"}'):
            if body is None:
                self.file.unlink()
            else:
                self.file.write_text(body, encoding='utf-8')
            with self.subTest(body=body), self.assertRaises((ValueError, FileNotFoundError)):
                manage.prepare_auth_only_app(self.config)
        self.support.engine_factory.assert_not_called()

    def test_origin_callback_issuer_algorithm_and_optout_are_strict(self):
        original = copy.deepcopy(self.settings)
        changes = [('origin', 'http://localhost:4443'), ('origin', 'https://localhost:4443/'),
            ('callback_url', 'https://other.test/auth/oidc/google/callback'), ('issuer', 'https://other.test'),
            ('signature_algorithms', ['HS256']), ('allow_http_loopback_callback', True)]
        for key, value in changes:
            self.settings = copy.deepcopy(original)
            if key == 'origin': self.settings[key] = value
            else: self.settings['oidc'][key] = value
            self.write()
            with self.subTest(key=key), self.assertRaises(ValueError):
                manage.prepare_auth_only_app(self.config)
        self.support.engine_factory.assert_not_called()

    def test_unapproved_private_directory_or_profile_is_rejected(self):
        for changes in ({'_path': str(self.file)}, {'_directory': str(manage.REPO)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                manage.prepare_auth_only_app({**self.config, **changes})
        self.support.engine_factory.assert_not_called()

    def test_invalid_professional_domains_dispose_resources_before_serving(self):
        self.settings['approved_domains'] = ['gmail.com']
        self.write()
        with self.assertRaises(ValueError): manage.prepare_auth_only_app(self.config)
        self.support.engine_factory.return_value.dispose.assert_called_once()
        self.transport.close.assert_called_once()
        self.transport.handle_request.assert_not_called()

    def test_missing_malformed_secret_and_weak_tls_block_before_engine(self):
        for value in ('', 'secret with space', 'a\nb'):
            self.secret.write_text(value, encoding='utf-8')
            with self.subTest(value=value), self.assertRaises(ValueError):
                manage.prepare_auth_only_app(self.config)
        self.secret.unlink()
        with self.assertRaises(FileNotFoundError): manage.prepare_auth_only_app(self.config)
        with patch('manage.load_auth_settings', return_value=('unused', None, (), Mock())) as settings:
            for transport in (None, {**self.config['b2b_transport'], 'sslmode': 'require'},
                    {**self.config['b2b_transport'], 'ca_sha256': '0'*64}):
                with self.subTest(transport=transport), self.assertRaises(ValueError):
                    manage.prepare_auth_only_app({**self.config, 'b2b_transport': transport})
            settings.return_value[3].assert_not_called()
        self.support.engine_factory.assert_not_called()

    def test_full_guard_keeps_identity_revision_tls_and_candidate_acl_checks(self):
        from app.core.caller_session import CallerProviderUnavailable
        variants = [dict(revision=manage.REVISION), dict(identity_changes={'role': 'ui47_admin'}),
            dict(identity_changes={'instance_id': 'wrong'}), dict(schema_changes={'cluster': 'wrong'}),
            dict(schema_changes={'ssl': False}), dict(schema_changes={'schema_create': True}),
            dict(acl_changes={'locks_installed': False}), dict(acl_changes={'unsafe': True}),
            dict(acl_changes={'flip_column': ('local_users', 'id', 'UPDATE')}),
            dict(acl_changes={'flip_table': ('oidc_transactions', 'DELETE')}),
            dict(acl_changes={'lock_fault': 'lock owner'})]
        for changes in variants:
            self.connection(**changes)
            with self.subTest(changes=changes), self.assertRaises(CallerProviderUnavailable):
                manage.prepare_auth_only_app(self.config)
            self.assertIn('ROLLBACK', [call.args[0] for call in self.sql.exec_driver_sql.call_args_list])
        self.support.engine_factory.return_value.dispose.assert_called()

    def test_assembly_uses_one_engine_real_components_and_no_legacy_routes(self):
        import builtins
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name in ('app.main', 'app.core.database'):
                raise AssertionError('Legacy assembly forbidden')
            return original(name, *args, **kwargs)
        with patch('builtins.__import__', side_effect=guarded):
            app = manage.prepare_auth_only_app(self.config)
        self.support.engine_factory.assert_called_once()
        self.assertIs(app.state.sql_runtime.engine, self.support.engine_factory.return_value)
        self.assertIs(app.state.b2b_auth_runtime.sql, app.state.sql_runtime)
        self.assertFalse(hasattr(app.state, 'b2b_runtime'))
        response = self.request(app, '/api/v1/auth/readiness')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'status': 'ready', 'profile': 'auth-only',
            'bridgeVersion': 'industrial-predict:b2b-session:v1'})
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.assertEqual(self.request(app, '/health').json()['runtime_mode'], 'auth-only')
        self.assertEqual(self.request(app, '/__dev/identity').json()['runtime_mode'], 'auth-only')
        for path, method, status in (('/auth/oidc/google/callback', 'GET', 401),
                ('/api/v1/auth/me', 'GET', 401), ('/api/v1/auth/logout', 'POST', 401),
                ('/api/v1/companies', 'GET', 404), ('/api/v1/equipments/1/predictions', 'GET', 404),
                ('/api/v1/maintenance', 'POST', 404), ('/openapi.json', 'GET', 404)):
            self.assertEqual(self.request(app, path, method=method).status_code, status)
        self.transport.handle_request.assert_not_called()  # No Google exchange, fake login or session.
        self.assertNotIn('synthetic-google-secret', response.text)
        self.sql.commit.assert_not_called()

    def test_readiness_fails_on_live_drift_or_secret_removal_without_retry(self):
        app = manage.prepare_auth_only_app(self.config)
        self.connection(schema_changes={'ssl': False})
        self.assertEqual(self.request(app, '/api/v1/auth/readiness').status_code, 503)
        self.connection()
        self.secret.unlink()
        response = self.request(app, '/api/v1/auth/readiness')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.secret), response.text)
        self.assertEqual(self.request(app, '/api/v1/auth/readiness', origin='http://localhost:4443').status_code, 503)

    def test_api_loopback_logging_proxy_and_lifespan_cleanup(self):
        with patch('manage.free_port'), patch('uvicorn.run') as run:
            manage.api(self.config, profile=manage.AUTH_ONLY)
        self.assertEqual(run.call_args.kwargs, {'host': '127.0.0.1', 'port': 8001,
            'log_level': 'warning', 'access_log': False, 'proxy_headers': True, 'forwarded_allow_ips': '127.0.0.1'})
        app = run.call_args.args[0]
        async def lifecycle():
            async with app.router.lifespan_context(app): pass
        self.loop.run_until_complete(lifecycle())
        self.transport.close.assert_called_once()
        self.support.engine_factory.return_value.dispose.assert_called_once()

    def test_failed_start_never_runs_uvicorn_and_cli_redacts_exceptions(self):
        self.secret.unlink()
        with patch('manage.free_port'), patch('uvicorn.run') as run, self.assertRaises(FileNotFoundError):
            manage.api(self.config, profile=manage.AUTH_ONLY)
        run.assert_not_called()
        output = io.StringIO()
        with patch('manage.main', side_effect=ValueError('synthetic-google-secret')), contextlib.redirect_stderr(output):
            self.assertEqual(manage.cli(), 2)
        self.assertNotIn('synthetic-google-secret', output.getvalue())
        self.assertIn('No fallback', output.getvalue())


if __name__ == '__main__':
    unittest.main()
