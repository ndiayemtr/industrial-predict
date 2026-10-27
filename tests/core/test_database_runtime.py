"""Runtime construction/lifecycle tests, without any PostgreSQL connection."""

from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from pydantic import SecretStr
import sqlalchemy
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.application_config import ApplicationConfig
from app.core.config_loader import ConfigurationError, load_application_config
from app.core import database_runtime as module


SECRET = "SYNTHETIC-RUNTIME-PASSWORD-ONLY"
URL = f"postgresql+psycopg://test_role:{SECRET}@sql.example.invalid:6543/test_database"


class DatabaseRuntimeTests(unittest.TestCase):
    def config(self):
        return load_application_config({"database_url": URL})

    def test_explicit_creation_preserves_historical_session_options(self):
        engine, factory = Mock(), Mock()
        with patch.object(module, "create_engine", return_value=engine) as make_engine, \
             patch.object(module, "sessionmaker", return_value=factory) as make_sessions:
            runtime = module.create_sql_runtime(self.config())
        args, kwargs = make_engine.call_args
        self.assertEqual(args, (sqlalchemy.engine.make_url(URL),))
        self.assertEqual(kwargs, {"pool_pre_ping": True, "echo": False, "hide_parameters": True})
        make_sessions.assert_called_once_with(bind=engine, autoflush=False, autocommit=False)
        self.assertIs(runtime.engine, engine)
        engine.connect.assert_not_called()
        engine.begin.assert_not_called()
        factory.assert_not_called()
        runtime.dispose()
        engine.dispose.assert_called_once_with()

    def test_absent_wrong_or_unvalidated_inputs_rejected_before_engine(self):
        bad = (None, {}, {"database_url": URL}, URL, object(),
               ApplicationConfig.model_construct(),
               ApplicationConfig.model_construct(database_url=SecretStr("invalid")),
               self.config().model_copy(update={"database_url": SecretStr("sqlite:///:memory:")}),
               self.config().model_copy(update={"unexpected": True}))
        with patch.object(module, "create_engine") as engine, patch.object(module, "sessionmaker") as factory:
            for position, config in enumerate(bad):
                with self.subTest(case=position), self.assertRaises(ConfigurationError):
                    module.create_sql_runtime(config)
            engine.assert_not_called()
            factory.assert_not_called()

    def test_sessions_are_distinct_closed_and_never_automatically_committed(self):
        engine, first, second = Mock(), Mock(), Mock()
        factory = Mock(side_effect=[first, second])
        runtime = module.SqlRuntime(engine, factory)
        with runtime.session() as one:
            self.assertIs(one, first)
            first.close.assert_not_called()
        with runtime.session() as two:
            self.assertIs(two, second)
            self.assertIsNot(one, two)
        self.assertEqual(factory.call_count, 2)
        for session in (first, second):
            session.close.assert_called_once_with()
            session.commit.assert_not_called()
            session.begin.assert_not_called()

    def test_session_closes_on_body_failure_and_preserves_original_exception(self):
        db = Mock()
        runtime = module.SqlRuntime(Mock(), Mock(return_value=db))
        failure = ValueError("Synthetic operation failure")
        with self.assertRaises(ValueError) as caught:
            with runtime.session():
                raise failure
        self.assertIs(caught.exception, failure)
        db.close.assert_called_once_with()
        db.commit.assert_not_called()

    def test_commit_is_only_caller_initiated(self):
        db = Mock()
        runtime = module.SqlRuntime(Mock(), Mock(return_value=db))
        with runtime.session() as session:
            session.commit()
        db.commit.assert_called_once_with()
        db.close.assert_called_once_with()

    def test_dispose_blocks_new_sessions_including_prepared_context(self):
        engine, factory = Mock(), Mock()
        runtime = module.SqlRuntime(engine, factory)
        prepared = runtime.session()
        runtime.dispose()
        engine.dispose.assert_called_once_with()
        with self.assertRaises(module.SqlRuntimeError):
            with prepared:
                self.fail("Closed runtime entered")
        factory.assert_not_called()

    def test_disposal_does_not_steal_an_active_session(self):
        engine, db = Mock(), Mock()
        runtime = module.SqlRuntime(engine, Mock(return_value=db))
        with runtime.session():
            runtime.dispose()
            db.close.assert_not_called()
        db.close.assert_called_once_with()
        db.commit.assert_not_called()

    def test_engine_is_cleaned_up_if_session_factory_construction_fails(self):
        engine = Mock()
        with patch.object(module, "create_engine", return_value=engine), \
             patch.object(module, "sessionmaker", side_effect=RuntimeError(URL)):
            with self.assertRaises(module.SqlRuntimeError) as caught:
                module.create_sql_runtime(self.config())
        engine.dispose.assert_called_once_with()
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertIsNone(caught.exception.__context__)

    def test_engine_construction_failure_is_sanitized_without_retry(self):
        with patch.object(module, "create_engine", side_effect=RuntimeError(URL)) as engine, \
             patch.object(module, "sessionmaker") as factory:
            with self.assertRaises(module.SqlRuntimeError) as caught:
                module.create_sql_runtime(self.config())
        engine.assert_called_once()
        factory.assert_not_called()
        self.assertNotIn(SECRET, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)

    def test_construction_cleanup_failure_is_sanitized_without_retaining_driver_error(self):
        engine = Mock()
        engine.dispose.side_effect = RuntimeError(URL)
        with patch.object(module, "create_engine", return_value=engine), \
             patch.object(module, "sessionmaker", side_effect=RuntimeError(URL)):
            with self.assertRaises(module.SqlRuntimeError) as caught:
                module.create_sql_runtime(self.config())
        engine.dispose.assert_called_once_with()
        self.assertNotIn(SECRET, repr(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertIsNone(caught.exception.__context__)

    def test_dispose_failure_is_sanitized_and_runtime_stays_closed(self):
        engine, factory = Mock(), Mock()
        engine.dispose.side_effect = [RuntimeError(URL), None]
        runtime = module.SqlRuntime(engine, factory)
        with self.assertRaises(module.SqlRuntimeError) as caught:
            runtime.dispose()
        self.assertNotIn(SECRET, repr(caught.exception))
        self.assertIsNone(caught.exception.__context__)
        with self.assertRaises(module.SqlRuntimeError):
            with runtime.session():
                pass
        factory.assert_not_called()
        runtime.dispose()  # Explicit cleanup retry, never a reconstruction.
        self.assertEqual(engine.dispose.call_count, 2)

    def test_environment_does_not_override_explicit_engine_construction(self):
        config = self.config()
        with patch.dict(os.environ, {"DATABASE_URL": "invalid://ambient", "PGHOST": "ambient.invalid",
                                    "PGPORT": "1", "PGUSER": "ambient", "PGDATABASE": "ambient"}, clear=True), \
             patch.object(module, "create_engine", return_value=Mock()) as engine, \
             patch.object(module, "sessionmaker"):
            runtime = module.create_sql_runtime(config)
            self.assertEqual(engine.call_args.args[0], sqlalchemy.engine.make_url(URL))
            runtime.dispose()

    def test_real_sqlalchemy_engine_and_sessions_remain_unconnected(self):
        # Real SQLAlchemy objects, but the DBAPI/network entry points must never run.
        import psycopg
        with ExitStack() as guards:
            spies = [guards.enter_context(patch(name, side_effect=AssertionError("Connection/DDL forbidden")))
                     for name in ("psycopg.connect", "socket.create_connection", "socket.socket.connect",
                                  "sqlalchemy.engine.Engine.connect", "sqlalchemy.engine.Engine.begin",
                                  "sqlalchemy.schema.MetaData.create_all", "sqlalchemy.orm.Session.commit")]
            runtime = module.create_sql_runtime(self.config())
            try:
                with runtime.session() as first, runtime.session() as second:
                    self.assertIsInstance(first, Session)
                    self.assertIsNot(first, second)
                    self.assertIs(first.get_bind(), runtime.engine)
                    self.assertFalse(first.autoflush)
                    self.assertTrue(first.expire_on_commit)  # Historical default retained.
                    self.assertFalse(first.in_transaction())
                    self.assertFalse(second.in_transaction())
                for spy in spies:
                    spy.assert_not_called()
            finally:
                runtime.dispose()

    def test_import_is_inert_and_explicit_factory_does_not_read_files_or_legacy(self):
        script = r'''
            import builtins, importlib.abc, io, sys
            from contextlib import ExitStack
            from unittest.mock import Mock, patch
            import pydantic, sqlalchemy, sqlalchemy.orm
            sys.path.insert(0, sys.argv[1])
            def forbidden(*args, **kwargs):
                raise AssertionError('Implicit configuration, SQL or I/O forbidden')
            class BlockLegacy(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname in ('app.core.config','app.core.database','app.main','pydantic_settings','dotenv'):
                        forbidden()
            sys.meta_path.insert(0, BlockLegacy())
            with ExitStack() as guards:
                for name in ('sqlalchemy.create_engine','sqlalchemy.engine_from_config',
                             'sqlalchemy.orm.sessionmaker','sqlalchemy.orm.Session',
                             'sqlalchemy.engine.Engine.connect','socket.create_connection','socket.socket.connect'):
                    guards.enter_context(patch(name,side_effect=forbidden))
                from app.core import database_runtime as runtime
                from app.core.config_loader import load_application_config
                config = load_application_config({'database_url':sys.argv[2]})
                with patch('builtins.open',side_effect=forbidden), patch('io.open',side_effect=forbidden), \
                     patch.object(runtime,'create_engine',return_value=Mock()) as engine, \
                     patch.object(runtime,'sessionmaker',return_value=Mock()):
                    instance = runtime.create_sql_runtime(config)
                    engine.assert_called_once()
                    instance.dispose()
                assert 'app.core.config' not in sys.modules
                assert 'app.core.database' not in sys.modules
                assert 'app.main' not in sys.modules
        '''
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP")
               if key in os.environ}
        env.update(DATABASE_URL="invalid://ambient", PGHOST="ambient.invalid")
        result = subprocess.run(
            [sys.executable, "-B", "-I", "-c", textwrap.dedent(script), str(ROOT / "backend"), URL],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
