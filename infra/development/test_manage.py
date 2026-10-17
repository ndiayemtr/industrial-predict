"""Configuration guard tests. No database or HTTP writes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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


if __name__ == '__main__':
    unittest.main()
