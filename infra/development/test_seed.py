"""Seed safety and idempotence tests on SQLite memory only, never PostgreSQL."""
import copy
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine, event, insert, select, text, update

import seed


class FixtureTests(unittest.TestCase):
    def test_counts_contracts_and_business_relations(self):
        records = seed.compile_fixture(seed.load_fixture())
        self.assertEqual({name:sum(r.table == name for r in records) for name in seed.manage.TABLES},
                         dict(companies=2,sites=3,equipments=4,sensors=6,measurements=18,
                              maintenance_records=3,prediction_records=0,maintenance_recommendations=0))
        self.assertEqual({r.values['criticality'] for r in records if r.table == 'equipments'},
                         {'low','medium','high','critical'})
        self.assertTrue(all('id' not in r.values and not any(k.endswith('_id') for k in r.values) for r in records))
        self.assertTrue(all(r.values['timestamp'].tzinfo is not None for r in records if r.table == 'measurements'))
        self.assertTrue(all(r.values['created_at'].tzinfo is None for r in records if r.table == 'companies'))
        self.assertEqual(next(r for r in records if r.table == 'sensors').values['unit'],'°C')

    def test_bad_enum_and_dates_are_rejected_before_any_connection(self):
        for table,field,value in [('equipments','status','running'),('equipments','criticality','urgent'),
                                  ('measurements','timestamp','2026-10-14T08:00:00'),
                                  ('maintenance_records','cost',-1),('maintenance_records','completed_at','2026-10-14T08:00:00Z')]:
            data = seed.load_fixture(); data[table][0][field] = value
            with self.subTest(table=table,field=field), self.assertRaises(ValidationError):
                seed.compile_fixture(data)

    def test_duplicate_unknown_parent_and_extra_fields_block(self):
        for kind in ('duplicate','parent','field','namespace'):
            data = seed.load_fixture()
            if kind == 'duplicate': data['measurements'].append(copy.deepcopy(data['measurements'][0]))
            elif kind == 'parent': data['sites'][0]['company_code'] = 'unknown'
            elif kind == 'field': data['sites'][0]['company_id'] = 900
            else: data['companies'][0]['code'] = 'OTHER'
            with self.subTest(kind=kind), self.assertRaises(ValueError): seed.compile_fixture(data)

    def test_missing_config_and_protected_target_block_before_engine(self):
        with patch('seed.create_engine') as engine:
            with self.assertRaises(FileNotFoundError): seed.manage.load_config('missing-development-seed-config.json')
            with tempfile.TemporaryDirectory() as directory:
                filename = Path(directory)/'protected.json'
                filename.write_text(json.dumps({'database':'industrial_predict','db_port':5433}),encoding='utf-8')
                with patch('seed.sys.argv',['seed.py','apply','--config',str(filename)]):
                    with self.assertRaises(ValueError): seed.main()
            engine.assert_not_called()

    def test_wrong_http_identity_and_redirects_are_not_accepted(self):
        config = dict(mode='local-development',database='industrial_predict_dev',instance_id='instance',database_oid=16384)
        with patch('seed.build_opener') as opener:
            response = opener.return_value.open.return_value.__enter__.return_value
            response.headers = {'X-Industrial-Predict-Environment':'local-development'}
            response.read.return_value = json.dumps({'database':'industrial_predict'}).encode()
            with self.assertRaises(ValueError): seed.verify_http(config,8001)
        self.assertIsNone(seed.NoRedirect().redirect_request(None,None,302,'',{},'http://127.0.0.1:8000'))

    def test_no_reset_command_exists(self):
        with patch('seed.sys.argv',['seed.py','reset','--config','unused']), patch('seed.run') as run, patch('seed.sys.stderr'):
            with self.assertRaises(SystemExit) as stopped: seed.main()
            self.assertEqual(stopped.exception.code,2)
            run.assert_not_called()


class TransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Explicit SQLite setting before importing any actual ORM metadata.
        os.environ['DATABASE_URL'] = 'sqlite+pysqlite:///:memory:'
        for module in ('company','site','equipment','sensor','measurement','maintenance_record','prediction_record','maintenance_recommendation'):
            importlib.import_module('app.models.'+module)
        from app.core.database import Base
        cls.metadata = Base.metadata

    def setUp(self):
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        self.addCleanup(self.engine.dispose)
        @event.listens_for(self.engine,'connect')
        def foreign_keys(dbapi, _): dbapi.execute('PRAGMA foreign_keys=ON')
        for table in self.metadata.tables.values(): table.dialect_options['sqlite']['autoincrement'] = True
        self.metadata.create_all(self.engine)
        self.tables = {name:self.metadata.tables[name] for name in seed.manage.TABLES}
        self.records = seed.compile_fixture(seed.load_fixture())

    def apply(self, write=True):
        with self.engine.begin() as connection:
            return seed.apply_seed(connection,self.tables,self.records,write=write)

    def snapshot(self):
        with self.engine.connect() as connection:
            return {name:[tuple(row) for row in connection.execute(select(table).order_by(table.c.id))]
                    for name,table in self.tables.items()}

    def test_check_is_read_only_and_initial_load_is_atomic(self):
        before = self.snapshot()
        self.assertEqual(self.apply(False)['action'],'ready')
        self.assertEqual(self.snapshot(),before)
        self.assertEqual(self.apply()['inserted'],36)

    def test_second_execution_is_identical_and_issues_no_dml(self):
        self.apply(); before = self.snapshot(); statements = []
        @event.listens_for(self.engine,'before_cursor_execute')
        def record_sql(conn,cursor,statement,parameters,context,executemany): statements.append(statement.upper().lstrip())
        result = self.apply()
        self.assertEqual(result['action'],'unchanged')
        self.assertEqual(result['inserted'],0)
        self.assertFalse(any(sql.startswith(('INSERT','UPDATE','DELETE')) for sql in statements))
        self.assertEqual(self.snapshot(),before)

    def test_relations_use_business_codes_with_non_contiguous_ids(self):
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO sqlite_sequence(name,seq) VALUES('companies',100),('sites',200),('equipments',300),('sensors',400)"))
        self.apply()
        with self.engine.connect() as connection:
            companies = {r.code:r.id for r in connection.execute(select(self.tables['companies']))}
            self.assertGreater(companies['UI47-COMP-A'],100)
            sites = connection.execute(select(self.tables['sites'])).mappings().all()
            self.assertEqual(next(r for r in sites if r['code']=='UI47-SITE-B-ENER')['company_id'],companies['UI47-COMP-B'])

    def test_unrelated_initial_data_is_not_changed(self):
        with self.engine.begin() as connection:
            connection.execute(insert(self.tables['companies']).values(code='FOREIGN',name='Foreign company'))
        before = self.snapshot()
        with self.assertRaises(seed.SeedConflict): self.apply()
        self.assertEqual(self.snapshot(),before)

    def test_partial_seed_is_not_completed_or_overwritten(self):
        with self.engine.begin() as connection:
            connection.execute(insert(self.tables['companies']).values(**self.records[0].values))
        before = self.snapshot()
        with self.assertRaises(seed.SeedConflict): self.apply()
        self.assertEqual(self.snapshot(),before)

    def test_changed_seed_data_is_preserved_and_conflict_reported(self):
        self.apply()
        with self.engine.begin() as connection:
            connection.execute(update(self.tables['sites']).where(self.tables['sites'].c.code=='UI47-SITE-A-PROD').values(name='User edit'))
        before = self.snapshot()
        with self.assertRaises(seed.SeedConflict): self.apply()
        self.assertEqual(self.snapshot(),before)

    def test_other_data_added_after_seed_stays_untouched(self):
        self.apply()
        with self.engine.begin() as connection:
            connection.execute(insert(self.tables['companies']).values(code='FOREIGN',name='Foreign company'))
        before = self.snapshot()
        self.assertEqual(self.apply()['action'],'unchanged')
        self.assertEqual(self.snapshot(),before)

    def test_ambiguous_measurement_natural_key_blocks_without_changes(self):
        self.apply()
        with self.engine.begin() as connection:
            row = dict(connection.execute(select(self.tables['measurements'])).mappings().first())
            row.pop('id'); connection.execute(insert(self.tables['measurements']).values(**row))
        before = self.snapshot()
        with self.assertRaises(seed.SeedConflict): self.apply()
        self.assertEqual(self.snapshot(),before)

    def test_sql_length_violation_is_detected_before_inserts(self):
        self.records[0].values['name'] = 'x'*151
        with self.assertRaises(ValueError): self.apply()
        self.assertTrue(all(not rows for rows in self.snapshot().values()))

    def test_unexpected_failure_rolls_back_all_rows(self):
        def fail_on_sensor(conn,cursor,statement,parameters,context,executemany):
            if statement.upper().startswith('INSERT INTO SENSORS'): raise RuntimeError('Simulated failure')
        event.listen(self.engine,'before_cursor_execute',fail_on_sensor)
        with self.assertRaises(RuntimeError): self.apply()
        self.assertTrue(all(not rows for rows in self.snapshot().values()))


if __name__ == '__main__': unittest.main()
