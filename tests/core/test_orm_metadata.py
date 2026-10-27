"""ORM import/metadata regressions: isolated processes, no application DB or Alembic run."""

import ast
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
MODELS = (
    "Company", "Site", "Equipment", "Sensor", "Measurement", "MaintenanceRecord",
    "PredictionRecord", "MaintenanceRecommendation",
)
TABLES = {
    "companies", "sites", "equipments", "sensors", "measurements",
    "maintenance_records", "prediction_records", "maintenance_recommendations",
}

GUARDS = """
import builtins
from contextlib import ExitStack
import importlib.abc
import io
from pathlib import Path
import sys
from unittest.mock import Mock, patch
import sqlalchemy
import sqlalchemy.orm

sys.path.insert(0, sys.argv[1])

def forbidden(*args, **kwargs):
    raise AssertionError('Runtime/configuration access forbidden in metadata tests')

class NoConfiguration(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('app.core.config', 'app.core.database', 'pydantic_settings', 'dotenv'):
            forbidden()

sys.meta_path.insert(0, NoConfiguration())

def guarded_open(original):
    def open_file(file, *args, **kwargs):
        if isinstance(file, (str, bytes, Path)):
            name = Path(file.decode() if isinstance(file, bytes) else file).name
            if name == '.env' or name.startswith('.env.'):
                forbidden()
        return original(file, *args, **kwargs)
    return open_file

guards = ExitStack()
guards.enter_context(patch('builtins.open', guarded_open(builtins.open)))
guards.enter_context(patch('io.open', guarded_open(io.open)))
for name in ('sqlalchemy.create_engine', 'sqlalchemy.engine_from_config',
             'sqlalchemy.orm.sessionmaker', 'sqlalchemy.orm.Session',
             'sqlalchemy.engine.Engine.connect', 'sqlalchemy.engine.Engine.begin',
             'sqlalchemy.schema.MetaData.create_all', 'socket.create_connection',
             'socket.socket.connect'):
    guards.enter_context(patch(name, side_effect=forbidden))
"""


class OrmMetadataTests(unittest.TestCase):
    def isolated(self, body):
        # -I ignores user Python configuration; an empty cwd cannot supply a project .env.
        env = {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP")
               if k in os.environ}
        env["DATABASE_URL"] = "invalid://must-not-be-consulted"
        with tempfile.TemporaryDirectory(prefix="orm-metadata-") as cwd:
            result = subprocess.run(
                [sys.executable, "-B", "-I", "-c", GUARDS + textwrap.dedent(body), str(BACKEND)],
                cwd=cwd, env=env, capture_output=True, text=True, timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_base_import_has_no_configuration_or_runtime(self):
        self.isolated("""
            from app.core.orm import Base
            from sqlalchemy.orm import DeclarativeBase
            assert issubclass(Base, DeclarativeBase)
            assert not Base.metadata.tables
            assert 'app.core.config' not in sys.modules
            assert 'app.core.database' not in sys.modules
        """)

    def test_models_share_one_registry_without_configuration_or_runtime(self):
        self.isolated(f"""
            import app.models as models
            from app.core.orm import Base
            from sqlalchemy.orm import configure_mappers
            configure_mappers()
            assert set(Base.metadata.tables) == {TABLES!r}
            assert len(tuple(Base.registry.mappers)) == 8
            for name in {MODELS!r}:
                model = getattr(models, name)
                assert issubclass(model, Base)
                assert model.metadata is Base.metadata
                assert model.registry is Base.registry
                assert model.__table__ is Base.metadata.tables[model.__tablename__]
            assert 'app.core.config' not in sys.modules
            assert 'app.core.database' not in sys.modules
        """)

    def test_legacy_reexport_and_session_lifecycle_in_both_import_orders(self):
        for models_first in (False, True):
            with self.subTest(models_first=models_first):
                self.isolated(f"""
                    import types
                    from app.core.orm import Base
                    if {models_first!r}:
                        import app.models
                    fake = types.ModuleType('app.core.config')
                    fake.settings = types.SimpleNamespace(database_url='sqlite:///:memory:')
                    sys.modules['app.core.config'] = fake
                    sys.meta_path = [f for f in sys.meta_path if not isinstance(f, NoConfiguration)]
                    engine, session = Mock(), Mock()
                    factory = Mock(return_value=session)
                    with patch('sqlalchemy.create_engine', return_value=engine) as make_engine, \
                         patch('sqlalchemy.orm.sessionmaker', return_value=factory) as make_sessions:
                        import app.core.database as legacy
                    import app.models
                    assert legacy.Base is Base
                    assert legacy.Base.metadata is Base.metadata
                    assert set(Base.metadata.tables) == {TABLES!r}
                    make_engine.assert_called_once_with('sqlite:///:memory:', pool_pre_ping=True)
                    make_sessions.assert_called_once_with(bind=engine, autoflush=False, autocommit=False)
                    assert legacy.engine is engine and legacy.SessionLocal is factory
                    dependency = legacy.get_db()
                    assert next(dependency) is session
                    dependency.close()
                    session.close.assert_called_once_with()
                    session.commit.assert_not_called()
                """)

    def test_table_columns_types_and_nullability_are_preserved(self):
        self.isolated("""
            import app.models
            from app.core.orm import Base
            from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String
            expected = {
                'companies': 'id name code description created_at updated_at',
                'sites': 'id name code description company_id created_at updated_at',
                'equipments': 'id name code equipment_type description status site_id created_at updated_at criticality',
                'sensors': 'id name code sensor_type unit description status equipment_id created_at updated_at',
                'measurements': 'id sensor_id timestamp value quality',
                'maintenance_records': 'id equipment_id maintenance_type status priority title description failure_code root_cause action_taken technician planned_at started_at completed_at downtime_minutes cost created_at updated_at',
                'prediction_records': 'id equipment_id sensor_id measurement_id prediction_type score level is_alert model_name model_version horizon_hours details predicted_at created_at',
                'maintenance_recommendations': 'id equipment_id priority recommendation_type title reason recommended_action signals generated_at created_at',
            }
            for name, columns in expected.items():
                table = Base.metadata.tables[name]
                assert set(table.c.keys()) == set(columns.split()), name
                assert list(table.primary_key.columns.keys()) == ['id']
                assert isinstance(table.c.id.type, Integer)
                assert not table.c.id.nullable
            p = Base.metadata.tables['prediction_records'].c
            for name, kind in (('score', Float), ('is_alert', Boolean), ('details', JSON),
                               ('predicted_at', DateTime), ('created_at', DateTime)):
                assert isinstance(p[name].type, kind)
            assert p.predicted_at.type.timezone and p.created_at.type.timezone
            assert not p.equipment_id.nullable and not p.score.nullable
            assert p.sensor_id.nullable and p.measurement_id.nullable and p.details.nullable
            assert p.prediction_type.type.length == 50 and p.model_name.type.length == 100
            assert p.model_version.type.length == 50 and p.level.type.length == 50
            m = Base.metadata.tables['measurements'].c
            assert m.timestamp.type.timezone and not m.timestamp.nullable
            assert isinstance(m.value.type, Float) and not m.value.nullable
            assert m.quality.default.arg == 'good'
            assert Base.metadata.tables['equipments'].c.criticality.default.arg == 'medium'
        """)

    def test_industrial_foreign_keys_and_indexes_are_preserved(self):
        self.isolated("""
            import app.models
            from app.core.orm import Base
            expected = {
                ('sites', 'company_id', 'companies.id'),
                ('equipments', 'site_id', 'sites.id'),
                ('sensors', 'equipment_id', 'equipments.id'),
                ('measurements', 'sensor_id', 'sensors.id'),
                ('maintenance_records', 'equipment_id', 'equipments.id'),
                ('prediction_records', 'equipment_id', 'equipments.id'),
                ('prediction_records', 'sensor_id', 'sensors.id'),
                ('prediction_records', 'measurement_id', 'measurements.id'),
                ('maintenance_recommendations', 'equipment_id', 'equipments.id'),
            }
            actual = set()
            for table in Base.metadata.tables.values():
                for fk in table.foreign_keys:
                    actual.add((table.name, fk.parent.name, fk.target_fullname))
                    assert fk.ondelete == 'CASCADE'
            assert actual == expected
            p = Base.metadata.tables['prediction_records']
            assert {i.name for i in p.indexes} == {
                'ix_prediction_records_' + c for c in
                ('id', 'equipment_id', 'sensor_id', 'measurement_id', 'prediction_type', 'level', 'predicted_at')}
            assert all(not i.unique for i in p.indexes)
            for table in ('companies', 'sites', 'equipments', 'sensors'):
                index = next(i for i in Base.metadata.tables[table].indexes if list(i.columns.keys()) == ['code'])
                assert index.unique
            assert Base.metadata.tables['equipments'].c.criticality.index
        """)

    def test_relationships_and_delete_orphan_cascades_are_preserved(self):
        self.isolated("""
            import app.models as m
            from sqlalchemy import inspect
            expected = {
                'Company': {'sites': ('Site', 'company')},
                'Site': {'company': ('Company', 'sites'), 'equipments': ('Equipment', 'site')},
                'Equipment': {'site': ('Site', 'equipments'), 'sensors': ('Sensor', 'equipment'),
                    'maintenance_records': ('MaintenanceRecord', 'equipment'),
                    'maintenance_recommendations': ('MaintenanceRecommendation', 'equipment')},
                'Sensor': {'equipment': ('Equipment', 'sensors'), 'measurements': ('Measurement', 'sensor')},
                'Measurement': {'sensor': ('Sensor', 'measurements')},
                'MaintenanceRecord': {'equipment': ('Equipment', 'maintenance_records')},
                'MaintenanceRecommendation': {'equipment': ('Equipment', 'maintenance_recommendations')},
                'PredictionRecord': {},
            }
            for name, relationships in expected.items():
                found = inspect(getattr(m, name)).relationships
                assert set(found.keys()) == set(relationships), name
                for key, (target, back) in relationships.items():
                    rel = found[key]
                    assert rel.mapper.class_ is getattr(m, target)
                    assert rel.back_populates == back
                    if rel.uselist:
                        assert 'delete-orphan' in rel.cascade and 'delete' in rel.cascade
        """)

    def test_alembic_metadata_wiring_without_executing_environment(self):
        source = (BACKEND / "migrations/env.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = [n for n in tree.body if isinstance(n, ast.ImportFrom)]
        self.assertTrue(any(n.module == "app.core.orm" and any(a.name == "Base" for a in n.names)
                            for n in imports))
        self.assertFalse(any(n.module == "app.core.database" for n in imports))
        self.assertEqual({a.name for n in imports if n.module == "app.models" for a in n.names},
                         set(MODELS))
        self.assertTrue(any(isinstance(n, ast.Assign)
                            and any(isinstance(t, ast.Name) and t.id == "target_metadata" for t in n.targets)
                            and ast.unparse(n.value) == "Base.metadata" for n in tree.body))
        # The historical configuration and online/offline paths remain in place.
        self.assertIn('config.set_main_option("sqlalchemy.url", settings.database_url)', source)
        self.assertIn('url=settings.database_url', source)
        self.assertIn('connection=connection, target_metadata=target_metadata', source)
        self.assertIn('poolclass=pool.NullPool', source)


if __name__ == "__main__":
    unittest.main()
