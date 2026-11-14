"""Configuration guard tests. No database or HTTP writes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

import manage


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.file = Path(self.directory.name) / 'config.json'
        self.config = dict(mode='local-development', db_host='127.0.0.1', db_port=5434,
                           database='industrial_predict_dev', api_port=8001, frontend_port=4201,
                           container='industrial-predict-postgres-ui47', volume='industrial-predict-postgres-ui47-data',
                           database_oid=16384, volume_created_at='2026-10-17T12:30:00Z',
                           cluster_identifier='1234567890123456789', instance_id='00000000-0000-0000-0000-000000000001')

    def load(self):
        self.file.write_text(json.dumps(self.config), encoding='utf-8')
        return manage.load_config(self.file)

    def test_explicit_target_and_app_identity(self):
        config = self.load()
        (self.file.parent/'app-password.txt').write_text('a'*64)
        url = manage.db_url(config, 'app')
        self.assertEqual((url.host, url.port, url.database, url.username),
                         ('127.0.0.1', 5434, 'industrial_predict_dev', 'ui47_app'))

    def test_each_missing_target_field_blocks(self):
        original = copy.deepcopy(self.config)
        for key in original:
            with self.subTest(key=key):
                self.config = {k:v for k,v in original.items() if k != key}
                with self.assertRaises(ValueError): self.load()

    def test_protected_and_wrong_targets_block(self):
        for key, value in [('database','industrial_predict'),('db_port',5433),('api_port',8000),
                           ('db_host','0.0.0.0'),('frontend_port',4200),('cluster_identifier',manage.SOURCE_CLUSTER),
                           ('container','industrial-predict-postgres'),('volume','industrial-predict_postgres_data')]:
            original = self.config[key]
            with self.subTest(key=key):
                self.config[key] = value
                with self.assertRaises(ValueError): self.load()
            self.config[key] = original

    def test_missing_configuration_blocks(self):
        with self.assertRaises(FileNotFoundError): manage.load_config(self.file)

    def test_in_repository_configuration_blocks(self):
        with self.assertRaises(ValueError): manage.load_config(Path(manage.__file__))

    def test_missing_or_malformed_secret_blocks(self):
        config = self.load()
        with self.assertRaises(FileNotFoundError): manage.db_url(config, 'app')
        (self.file.parent/'app-password.txt').write_text('')
        with self.assertRaises(ValueError): manage.db_url(config, 'app')
        with self.assertRaises(ValueError): manage.db_url(config, 'source')

    def test_container_collision_blocks_start_and_stop(self):
        metadata = {'Config':{'Labels':{'com.docker.compose.project':'industrial-predict-ui47'}},
                    'Mounts':[{'Destination':'/var/lib/postgresql/data','Name':self.config['volume']}],
                    'HostConfig':{'PortBindings':{'5432/tcp':[{'HostIp':'127.0.0.1','HostPort':'5434'}]}}}
        with patch('manage.subprocess.run') as run:
            run.return_value.stdout = json.dumps([metadata])
            manage.verify_container(self.config)
            for changed in ('project','volume','binding'):
                invalid = copy.deepcopy(metadata)
                if changed == 'project': invalid['Config']['Labels']['com.docker.compose.project'] = 'industrial-predict'
                if changed == 'volume': invalid['Mounts'][0]['Name'] = 'industrial-predict_postgres_data'
                if changed == 'binding': invalid['HostConfig']['PortBindings']['5432/tcp'][0]['HostIp'] = '0.0.0.0'
                run.return_value.stdout = json.dumps([invalid])
                with self.assertRaises(ValueError): manage.verify_container(self.config)

    def test_actual_database_identity_must_match(self):
        config = self.load()
        proof = dict(database=config['database'], role='ui47_app', version='17.10',
                     database_oid=16384,
                     instance_id=config['instance_id'], cluster_name='industrial-predict-development',
                     backend_pid=1, superuser=False, createdb=False, createrole=False,
                     replication=False, bypassrls=False)
        from unittest.mock import MagicMock
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value.one.return_value = proof
        connection.execute.return_value.scalar_one.return_value = manage.REVISION
        self.assertEqual(manage.inspect_connection(connection, config)['revision'], manage.REVISION)
        for key, value in [('database','industrial_predict'),('database_oid',99),('role','ui47_admin'),
                           ('instance_id','wrong'),('cluster_name','old'),('version','16.0'),('superuser',True)]:
            connection.execute.return_value.mappings.return_value.one.return_value = {**proof,key:value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                manage.inspect_connection(connection, config)
        connection.execute.return_value.mappings.return_value.one.return_value = proof
        connection.execute.return_value.scalar_one.return_value = 'wrong-revision'
        with self.assertRaises(ValueError): manage.inspect_connection(connection, config)

    def test_volume_identity_and_absence_block_recreation(self):
        with patch('manage.subprocess.run') as run:
            run.return_value.stdout = json.dumps([{'Name':self.config['volume'],'CreatedAt':self.config['volume_created_at']}])
            manage.verify_volume(self.config)
            run.return_value.stdout = json.dumps([{'Name':self.config['volume'],'CreatedAt':'changed'}])
            with self.assertRaises(ValueError): manage.verify_volume(self.config)
            from subprocess import CalledProcessError
            run.side_effect = CalledProcessError(1, 'docker volume inspect')
            with self.assertRaises(CalledProcessError): manage.verify_volume(self.config)

    def test_db_start_never_provisions_or_recreates(self):
        config = self.load()
        with patch('manage.sys.argv',['manage.py','db-start','--config',str(self.file)]), \
             patch('manage.verify_container'), patch('manage.verify_volume') as volume, \
             patch('manage.inspect_db'), patch('manage.subprocess.run') as run:
            manage.main()
            command = run.call_args.args[0]
            self.assertIn('start', command)
            self.assertNotIn('up', command)
            self.assertNotIn('--force-recreate', command)
            self.assertEqual(command[-1], 'postgres-ui47')
            run.reset_mock()
            volume.side_effect = ValueError('Volume mismatch')
            with self.assertRaises(ValueError): manage.main()
            run.assert_not_called()


class RuntimePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        directory = Path(self.temp.name)
        policy = manage.b2b.policy()
        self.config = {**policy['destination'], '_path': policy['profile'], '_directory': str(directory),
                       'api_port': 8001, 'frontend_port': 4201}
        ca = directory / 'synthetic-ca.crt'
        ca.write_bytes(b'synthetic CA bytes; no real certificate or secret')
        self.config['b2b_transport'] = {'sslmode': 'verify-full', 'sslrootcert': str(ca),
                                        'ca_sha256': manage.b2b.file_digest(ca)}
        from sqlalchemy.engine import URL
        self.url = URL.create('postgresql+psycopg', username='ui47_app', password='synthetic-test-only',
                              host='127.0.0.1', port=5434, database='industrial_predict_dev')
        self.url_mock = patch('manage.db_url', return_value=self.url).start()
        self.addCleanup(patch.stopall)
        self.engine_factory = patch('manage.create_engine').start()
        import os
        patch.dict(os.environ, {k:v for k,v in os.environ.items() if not k.upper().startswith('PG')}, clear=True).start()
        for name in ('sqlalchemy.engine.Engine.connect', 'psycopg.connect', 'psycopg.Connection.connect',
                     'socket.socket.connect', 'socket.getaddrinfo'):
            patch(name, side_effect=AssertionError('Real network/DB forbidden')).start()

    def connection(self, *, revision=None, identity_changes=None, schema_changes=None):
        config = self.config
        proof = dict(database=config['database'], database_oid=config['database_oid'], role='ui47_app',
                     version='17.10', instance_id=config['instance_id'], cluster_name='industrial-predict-development',
                     backend_pid=1, superuser=False, createdb=False, createrole=False, replication=False, bypassrls=False)
        proof.update(identity_changes or {})
        state = {'tables': {n:'ui47_migrator' for n in (*manage.TABLES,*manage.B2B_TABLES,'alembic_version')},
                 'sequences': {n:'ui47_migrator' for n in manage.BUSINESS_SEQUENCES | manage.B2B_SEQUENCES},
                 'cluster': config['cluster_identifier'], 'ssl': True, 'schema_owner': 'ui47_migrator',
                 'b2b_grant': False, 'sequence_extra': None, 'missing_business_select': False,
                 'extra_business_privilege': False, 'schema_create': False,
                 'role_memberships': 0, 'owns_business_tables': 0, 'metadata_update': False}
        state.update(schema_changes or {})
        connection = MagicMock()
        connection.execution_options.return_value = connection
        connection.__enter__.return_value = connection
        def execute(statement, params=None):
            sql, params = str(statement), params or {}
            result = MagicMock()
            if 'current_database() AS database' in sql:
                result.mappings.return_value.one.return_value = proof
            elif 'SELECT version_num' in sql:
                result.scalar_one.return_value = revision or manage.RUNTIME_REVISION
            elif 'has_sequence_privilege' in sql:
                key = (params['name'].split('.')[1], params['privilege'])
                result.scalar_one.return_value = key == state['sequence_extra'] or (
                    key[0] in manage.BUSINESS_SEQUENCES and key[1] == 'USAGE')
            elif 'has_table_privilege' in sql or 'has_any_column_privilege' in sql:
                name, privilege = params.get('table', params.get('name', '')).split('.')[-1], params.get('privilege', '')
                result.scalar_one.return_value = (name in manage.TABLES and privilege in ('SELECT','INSERT','UPDATE','DELETE')) or (
                    name in manage.B2B_TABLES and state['b2b_grant'])
                if name in manage.TABLES and privilege == 'SELECT' and state['missing_business_select']:
                    result.scalar_one.return_value = False
                if name in manage.TABLES and privilege == 'TRUNCATE' and state['extra_business_privilege']:
                    result.scalar_one.return_value = True
                if 'public.alembic_version' in sql:
                    result.scalar_one.return_value = state['metadata_update']
            elif 'count(*) FROM pg_tables' in sql:
                result.scalar_one.return_value = state['owns_business_tables']
            elif 'pg_auth_members' in sql:
                result.scalar_one.return_value = state['role_memberships']
            elif 'has_schema_privilege' in sql:
                result.scalar_one.return_value = state['schema_create']
            else:
                result.scalar_one.return_value = False
            return result
        def driver(sql):
            result = MagicMock()
            if 'system_identifier' in sql:
                result.scalar_one.return_value = state['cluster']
            elif 'pg_stat_ssl' in sql:
                result.scalar_one.return_value = state['ssl']
            elif 'tablename,tableowner' in sql:
                result.all.return_value = list(state['tables'].items())
            elif 'sequencename,sequenceowner' in sql:
                result.all.return_value = list(state['sequences'].items())
            elif 'nspowner' in sql:
                result.scalar_one.return_value = state['schema_owner']
            else:
                result.scalar_one.return_value = 0
            return result
        connection.execute.side_effect = execute
        connection.exec_driver_sql.side_effect = driver
        self.engine_factory.return_value.connect.return_value = connection
        return connection, state

    def test_runtime_engine_pins_tls_and_app_role_without_environment_url(self):
        import os
        before = dict(os.environ)
        manage.runtime_engine(self.config)
        self.url_mock.assert_called_once_with(self.config, 'app')
        call = self.engine_factory.call_args
        self.assertEqual(call.args, (self.url,))
        self.assertFalse(call.kwargs['echo'])
        self.assertTrue(call.kwargs['hide_parameters'])
        self.assertEqual(call.kwargs['connect_args']['sslmode'], 'verify-full')
        self.assertEqual(Path(call.kwargs['connect_args']['sslrootcert']), Path(self.config['b2b_transport']['sslrootcert']))
        self.assertEqual(call.kwargs['connect_args']['gssencmode'], 'disable')
        self.assertEqual(dict(os.environ), before)

    def test_missing_weak_or_changed_ca_refused_before_secret_or_engine(self):
        original = self.config['b2b_transport']
        for value in (None, {**original,'sslmode':'require'}, {**original,'sslmode':'prefer'},
                      {**original,'ca_sha256':'0'*64}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                manage.runtime_engine({**self.config,'b2b_transport':value})
        self.url_mock.assert_not_called()
        self.engine_factory.assert_not_called()

    def test_wrong_target_inventory_or_ambient_pg_settings_refused(self):
        import os
        for key, value in (('database','industrial_predict'),('database_oid',99),('db_port',5433),
                           ('instance_id','wrong'),('cluster_identifier','123'),('_path',str(Path(self.temp.name)/'other.json'))):
            with self.subTest(key=key), self.assertRaises(ValueError):
                manage.runtime_engine({**self.config,key:value})
        with patch.dict(os.environ, {'PGSSLMODE':'disable'}), self.assertRaises(ValueError):
            manage.runtime_engine(self.config)
        self.url_mock.assert_not_called()

    def test_runtime_accepts_only_exact_b2b_revision(self):
        connection, _ = self.connection()
        self.assertEqual(manage.inspect_runtime_connection(connection,self.config)['revision'], manage.RUNTIME_REVISION)
        for revision in (manage.REVISION,'head','p101_0001_operations'):
            connection, _ = self.connection(revision=revision)
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                manage.inspect_runtime_connection(connection,self.config)
        self.assertEqual(manage.REVISION,'09ac8101e9fe')  # approved migration start unchanged

    def test_candidate_qualification_keeps_identity_tls_schema_and_closed_proof(self):
        self.connection()
        with patch('manage.activation.inspect_acl', return_value={'acl_exact': True, 'activation_available': False}) as acl:
            proof = manage.inspect_db(self.config, profile=manage.activation.CANDIDATE)
        self.assertFalse(proof['activation_available'])
        self.assertFalse(proof['business_routes_enabled'])
        self.assertEqual(proof['runtime_mode'], 'b2b-preparation')
        acl.assert_called_once()
        for changes in ({'revision': manage.REVISION}, {'identity_changes': {'role': 'ui47_admin'}},
                        {'schema_changes': {'ssl': False}}, {'schema_changes': {'cluster': 'wrong'}}):
            self.connection(**changes)
            with self.subTest(changes=changes), patch('manage.activation.inspect_acl') as acl, self.assertRaises(ValueError):
                manage.inspect_db(self.config, profile=manage.activation.CANDIDATE)
            acl.assert_not_called()

    def test_candidate_acl_failure_blocks_qualification(self):
        connection, _ = self.connection()
        with patch('manage.activation.inspect_acl', side_effect=ValueError('ACL mismatch')), self.assertRaises(ValueError):
            manage.inspect_db(self.config, profile=manage.activation.CANDIDATE)
        self.assertIn('ROLLBACK', [c.args[0] for c in connection.exec_driver_sql.call_args_list])

    def test_runtime_refuses_wrong_live_identity_cluster_or_plaintext(self):
        for key, value in (('database','industrial_predict'),('database_oid',99),('role','ui47_admin'),
                           ('instance_id','wrong'),('cluster_name','wrong'),('superuser',True),('createdb',True)):
            connection, _ = self.connection(identity_changes={key:value})
            with self.subTest(key=key), self.assertRaises(ValueError):
                manage.inspect_runtime_connection(connection,self.config)
        for change in ({'cluster':'999'},{'ssl':False}):
            connection, _ = self.connection(schema_changes=change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                manage.inspect_runtime_connection(connection,self.config)

    def test_runtime_exact_fifteen_tables_eleven_sequences_and_no_b2b_grants(self):
        connection, _ = self.connection()
        proof = manage.inspect_db(self.config)
        self.assertEqual(len(proof['counts']),8)
        self.assertEqual(proof['b2b_access'],'not_enabled')
        self.assertTrue(proof['sequence_usage_only'])
        self.assertFalse(proof['business_routes_enabled'])
        self.assertEqual(proof['runtime_mode'],'b2b-preparation')
        self.assertIn('ROLLBACK',[c.args[0] for c in connection.exec_driver_sql.call_args_list])
        self.assertFalse(any(c.args[0].startswith(('GRANT','CREATE','ALTER')) for c in connection.exec_driver_sql.call_args_list))

    def test_missing_extra_objects_owners_and_sequence_privileges_refused(self):
        connection, state = self.connection()
        tests = [
            {'tables':{k:v for k,v in state['tables'].items() if k!='application_sessions'}},
            {'tables':{**state['tables'],'p101_prediction_operations':'ui47_migrator'}},
            {'tables':{**state['tables'],'companies':'ui47_app'}},
            {'schema_owner':'ui47_app'},
            {'sequences':{k:v for k,v in state['sequences'].items() if k not in manage.B2B_SEQUENCES}},
            {'sequences':{**state['sequences'],'extra_seq':'ui47_migrator'}},
            {'sequence_extra':('local_users_id_seq','USAGE')},
            {'sequence_extra':('companies_id_seq','UPDATE')},
            {'b2b_grant':True}]
        for changes in tests:
            connection, _ = self.connection(schema_changes=changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                manage.inspect_runtime_schema(connection)

    def test_prepared_app_has_only_diagnostics_and_does_not_import_legacy_assembly(self):
        import builtins
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name in ('app.main','app.core.database'):
                raise AssertionError('Legacy assembly/.env discovery forbidden')
            return original(name,*args,**kwargs)
        with patch('builtins.__import__',side_effect=guarded):
            app = manage.prepare_runtime_app(self.config)
        self.assertEqual({r.path for r in app.routes},{'/health','/__dev/identity'})
        self.assertTrue(all(r.methods=={'GET'} for r in app.routes))
        self.assertIs(app.state.sql_runtime.engine,self.engine_factory.return_value)
        self.assertFalse(hasattr(app.state,'b2b_runtime'))
        self.engine_factory.return_value.connect.assert_not_called()

    def test_historical_runtime_privilege_guards_still_refuse_excess_or_missing_rights(self):
        for changes in ({'missing_business_select':True},{'extra_business_privilege':True},
                        {'schema_create':True},{'role_memberships':1},
                        {'owns_business_tables':1},{'metadata_update':True}):
            self.connection(schema_changes=changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                manage.inspect_db(self.config)

    def test_api_launch_uses_prepared_surface_and_disposes_engine(self):
        import os
        before = dict(os.environ)
        with patch('manage.inspect_db'), patch('manage.free_port'), patch('uvicorn.run') as run:
            manage.api(self.config)
        app = run.call_args.args[0]
        self.assertEqual({r.path for r in app.routes},{'/health','/__dev/identity'})
        self.assertFalse(hasattr(app.state,'b2b_runtime'))
        self.engine_factory.return_value.dispose.assert_called_once()
        self.assertEqual(dict(os.environ),before)

    def test_check_api_requires_runtime_tls_and_closed_surface_proof(self):
        connection, _ = self.connection()
        proof = {**manage.inspect_runtime_connection(connection,self.config),'mode':self.config['mode']}
        response = MagicMock()
        response.__enter__.return_value = response
        response.headers.get.return_value = 'local-development'
        with patch('manage.urlopen',return_value=response):
            response.read.return_value = json.dumps(proof)
            self.assertEqual(manage.check_api(self.config)['revision'],manage.RUNTIME_REVISION)
            for changes in ({'revision':manage.REVISION},{'database_oid':99},{'ssl':False},
                            {'tls_verify_full':False},{'business_routes_enabled':True},{'role':'ui47_migrator'}):
                response.read.return_value = json.dumps({**proof,**changes})
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    manage.check_api(self.config)


if __name__ == '__main__':
    unittest.main()
