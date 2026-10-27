"""Application assembly with simulated runtimes and real, in-process ASGI lifespans."""

from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from fastapi import Depends, FastAPI, HTTPException
import httpx
from sqlalchemy.orm import Session
from starlette.datastructures import State


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app import application as module
from app.core import database_lifespan
from app.core.config_loader import ConfigurationError, load_application_config
from app.core.database_runtime import SqlRuntime
from app.core.dependencies import get_db


URL = "postgresql+psycopg://fake_role:FAKE_ONLY@sql.example.invalid:6543/fake_database"
SENSITIVE = "SYNTHETIC-BINDING-DETAIL-NEVER-PUBLIC"


def resource(marker="test"):
    engine, db = Mock(), Mock(spec=Session)
    db.info = {"marker": marker}
    factory = Mock(return_value=db)
    return SqlRuntime(engine, factory), engine, factory, db


def add_probe(app):
    @app.get("/test-probe")
    def probe(db=Depends(get_db)):
        return {"marker": db.info["marker"]}


class UnreadableRuntimeState(State):
    def __getattr__(self, name):
        if name == "sql_runtime":
            raise RuntimeError(SENSITIVE)
        return super().__getattr__(name)


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        for name in ("sqlalchemy.create_engine", "sqlalchemy.orm.sessionmaker",
                     "app.core.database_runtime.create_engine", "app.core.database_runtime.sessionmaker",
                     "sqlalchemy.engine.Engine.connect", "sqlalchemy.schema.MetaData.create_all",
                     "socket.create_connection", "socket.socket.connect"):
            self.guards.enter_context(patch(name, side_effect=AssertionError("SQL/network forbidden")))
        self.create = self.guards.enter_context(patch.object(
            database_lifespan, "create_sql_runtime", side_effect=AssertionError("Factory must be simulated")))

    def config(self):
        return load_application_config({"database_url": URL})

    def assert_detached(self, app):
        self.assertFalse(hasattr(app.state, "sql_runtime"))

    async def request(self, app, path="/test-probe"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://asgi.test") as client:
            return await client.get(path)

    async def test_construction_delegates_to_existing_lifespan_without_sql_resources(self):
        config = self.config()
        with patch.object(module, "create_sql_lifespan", wraps=module.create_sql_lifespan) as lifespan:
            app = module.create_app(config=config)
        lifespan.assert_called_once_with(config=config, runtime=None)
        self.assertIsInstance(app, FastAPI)
        self.assertEqual(app.routes, [])
        self.assert_detached(app)
        self.create.assert_not_called()

    async def test_absent_contradictory_and_invalid_inputs_are_rejected(self):
        runtime, engine, factory, _ = resource()
        for kwargs in ({}, {"config": self.config(), "runtime": runtime}, {"config": {}},
                       {"config": URL}, {"runtime": object()}, {"runtime": Mock(spec=SqlRuntime)}):
            with self.subTest(keys=list(kwargs)), self.assertRaises(database_lifespan.SqlLifespanError):
                module.create_app(**kwargs)
        invalid = self.config().model_copy(update={"database_url": "invalid"})
        with self.assertRaises(ConfigurationError):
            module.create_app(config=invalid)
        self.create.assert_not_called()
        factory.assert_not_called()
        engine.dispose.assert_not_called()

    async def test_default_metadata_and_disabled_documentation(self):
        app = module.create_app(config=self.config())
        self.assertEqual(app.title, "Industrial Predict AI API")
        self.assertEqual(app.version, "0.1.0")
        self.assertEqual(app.description, "API de maintenance prédictive industrielle")
        self.assertIsNone(app.docs_url)
        self.assertIsNone(app.redoc_url)
        self.assertIsNone(app.openapi_url)
        schema = app.openapi()  # Memory-only inspection, no documentation HTTP endpoint.
        self.assertEqual(schema["info"]["title"], app.title)
        self.assertEqual(schema["info"]["version"], app.version)
        self.assertEqual(schema["info"]["description"], app.description)
        self.assertEqual(schema["paths"], {})
        self.assertNotIn(URL, str(schema))
        self.create.assert_not_called()

    async def test_custom_public_metadata_is_kept_exactly(self):
        values = {"title": "API de test indépendante", "version": "test-v2", "description": "Description de test"}
        app = module.create_app(config=self.config(), **values)
        for key, value in values.items():
            self.assertEqual(getattr(app, key), value)
            self.assertEqual(app.openapi()["info"][key], value)
        empty_description = module.create_app(config=self.config(), description="")
        self.assertEqual(empty_description.description, "")
        self.create.assert_not_called()

    async def test_empty_or_non_text_metadata_is_rejected_without_exposing_inputs(self):
        for values in ({"title": ""}, {"title": " \t"}, {"version": ""}, {"version": "  "},
                       {"title": None}, {"version": 1}, {"description": None}, {"title": {SENSITIVE: URL}}):
            with self.subTest(keys=list(values)), self.assertRaises(module.ApplicationFactoryError) as caught:
                module.create_app(config=self.config(), **values)
            self.assertEqual(str(caught.exception), "INVALID_API_METADATA")
            self.assertNotIn(SENSITIVE, repr(caught.exception))
        self.create.assert_not_called()

    async def test_no_historical_or_documentation_endpoints_exist(self):
        app = module.create_app(config=self.config())
        self.assertEqual(app.routes, [])
        for path in ("/health", "/api/v1", "/api/v1/companies", "/docs", "/redoc", "/openapi.json"):
            with self.subTest(path=path):
                self.assertEqual((await self.request(app, path)).status_code, 404)
        self.create.assert_not_called()

    async def test_owned_lifespan_installs_expected_runtime_and_disposes_once(self):
        expected, engine, factory, db = resource()
        self.create.side_effect = [expected]
        app = module.create_app(config=self.config())
        self.create.assert_not_called()
        self.assert_detached(app)
        # Explicit entry/exit: requests alone would not start the ASGI lifespan.
        async with app.router.lifespan_context(app):
            module.assert_sql_runtime_binding(app, expected_runtime=expected)
            factory.assert_not_called()
            engine.dispose.assert_not_called()
        self.assert_detached(app)
        self.create.assert_called_once()
        engine.dispose.assert_called_once_with()
        factory.assert_not_called()
        db.commit.assert_not_called()

    async def test_borrowed_lifespan_does_not_take_engine_ownership(self):
        expected, engine, factory, db = resource()
        app = module.create_app(runtime=expected)
        self.assert_detached(app)
        async with app.router.lifespan_context(app):
            module.assert_sql_runtime_binding(app, expected_runtime=expected)
        self.assert_detached(app)
        self.create.assert_not_called()
        engine.dispose.assert_not_called()
        factory.assert_not_called()
        db.commit.assert_not_called()

    async def test_binding_rejects_absent_wrong_and_different_runtimes_with_constant_error(self):
        expected, engine, factory, _ = resource()
        other, foreign_engine, foreign_factory, _ = resource()
        app = module.create_app(runtime=expected)
        for actual in (None, object(), SENSITIVE, Mock(spec=SqlRuntime), other):
            app.state.sql_runtime = actual
            with self.subTest(kind=type(actual).__name__), self.assertRaises(module.ApplicationFactoryError) as caught:
                module.assert_sql_runtime_binding(app, expected_runtime=expected)
            self.assertEqual(str(caught.exception), "SQL_RUNTIME_BINDING_MISMATCH")
            self.assertNotIn(SENSITIVE, repr(caught.exception))
        del app.state.sql_runtime
        with self.assertRaises(module.ApplicationFactoryError):
            module.assert_sql_runtime_binding(app, expected_runtime=expected)
        for invalid in (None, object(), Mock(spec=SqlRuntime)):
            with self.assertRaises(module.ApplicationFactoryError):
                module.assert_sql_runtime_binding(app, expected_runtime=invalid)
        with self.assertRaises(module.ApplicationFactoryError):
            module.assert_sql_runtime_binding(object(), expected_runtime=expected)
        for candidate in (engine, foreign_engine):
            candidate.dispose.assert_not_called()
        factory.assert_not_called()
        foreign_factory.assert_not_called()

    async def test_binding_sanitizes_unreadable_slot_without_sql_access(self):
        expected, engine, factory, _ = resource()
        app = module.create_app(runtime=expected)
        app.state = UnreadableRuntimeState()
        with self.assertRaises(module.ApplicationFactoryError) as caught:
            module.assert_sql_runtime_binding(app, expected_runtime=expected)
        error = caught.exception
        self.assertEqual(str(error), "SQL_RUNTIME_BINDING_MISMATCH")
        self.assertNotIn(SENSITIVE, repr(error))
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)
        engine.dispose.assert_not_called()
        factory.assert_not_called()

    async def test_dependency_is_503_before_after_and_works_inside_lifespan(self):
        expected, engine, factory, db = resource("during")
        app = module.create_app(runtime=expected)
        add_probe(app)
        before = await self.request(app)
        self.assertEqual((before.status_code, before.json()), (503, {"detail": "SQL_RUNTIME_UNAVAILABLE"}))
        async with app.router.lifespan_context(app):
            during = await self.request(app)
            self.assertEqual((during.status_code, during.json()), (200, {"marker": "during"}))
        after = await self.request(app)
        self.assertEqual((after.status_code, after.json()), (503, {"detail": "SQL_RUNTIME_UNAVAILABLE"}))
        factory.assert_called_once_with()
        db.close.assert_called_once_with()
        db.commit.assert_not_called()
        engine.dispose.assert_not_called()

    async def test_multiple_owned_applications_are_independent(self):
        a, engine_a, factory_a, db_a = resource("a")
        b, engine_b, factory_b, db_b = resource("b")
        self.create.side_effect = [a, b]
        app_a, app_b = module.create_app(config=self.config()), module.create_app(config=self.config())
        self.assertIsNot(app_a, app_b)
        self.assertIsNot(app_a.state, app_b.state)
        self.assertIsNot(app_a.dependency_overrides, app_b.dependency_overrides)
        add_probe(app_a)
        add_probe(app_b)
        async with app_a.router.lifespan_context(app_a), app_b.router.lifespan_context(app_b):
            module.assert_sql_runtime_binding(app_a, expected_runtime=a)
            module.assert_sql_runtime_binding(app_b, expected_runtime=b)
            with self.assertRaises(module.ApplicationFactoryError):
                module.assert_sql_runtime_binding(app_a, expected_runtime=b)
            self.assertEqual((await self.request(app_a)).json(), {"marker": "a"})
            self.assertEqual((await self.request(app_b)).json(), {"marker": "b"})
        self.assert_detached(app_a)
        self.assert_detached(app_b)
        for engine, factory, db in ((engine_a, factory_a, db_a), (engine_b, factory_b, db_b)):
            engine.dispose.assert_called_once_with()
            factory.assert_called_once_with()
            db.close.assert_called_once_with()
            db.commit.assert_not_called()

    async def test_override_of_new_dependency_is_effective_and_app_local(self):
        a, engine_a, factory_a, _ = resource("a")
        b, engine_b, factory_b, db_b = resource("b")
        app_a, app_b = module.create_app(runtime=a), module.create_app(runtime=b)
        add_probe(app_a)
        add_probe(app_b)
        override = Mock(spec=Session)
        override.info = {"marker": "override"}

        def replacement():
            try:
                yield override
            finally:
                override.close()

        app_a.dependency_overrides[get_db] = replacement
        self.assertEqual(app_b.dependency_overrides, {})
        async with app_a.router.lifespan_context(app_a), app_b.router.lifespan_context(app_b):
            self.assertEqual((await self.request(app_a)).json(), {"marker": "override"})
            self.assertEqual((await self.request(app_b)).json(), {"marker": "b"})
        factory_a.assert_not_called()
        factory_b.assert_called_once_with()
        override.close.assert_called_once_with()
        override.commit.assert_not_called()
        db_b.commit.assert_not_called()
        engine_a.dispose.assert_not_called()
        engine_b.dispose.assert_not_called()

    async def test_handler_exception_is_preserved_and_cleanup_remains_owned_by_lifespan(self):
        expected, engine, factory, db = resource()
        self.create.side_effect = [expected]
        app = module.create_app(config=self.config())
        initial = ValueError("Original handler failure")

        @app.get("/failure")
        def failure(db=Depends(get_db)):
            raise initial

        @app.get("/conflict")
        def conflict(db=Depends(get_db)):
            raise HTTPException(409, "Business conflict")

        async with app.router.lifespan_context(app):
            with self.assertRaises(ValueError) as caught:
                await self.request(app, "/failure")
            self.assertIs(caught.exception, initial)
            self.assertEqual((await self.request(app, "/conflict")).status_code, 409)
            engine.dispose.assert_not_called()
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(db.close.call_count, 2)
        db.commit.assert_not_called()
        engine.dispose.assert_called_once_with()
        self.assert_detached(app)

    async def test_lifespan_exception_preserves_original_and_detaches_runtime(self):
        expected, engine, _, _ = resource()
        self.create.side_effect = [expected]
        app = module.create_app(config=self.config())
        initial = ValueError("Original lifespan failure")
        with self.assertRaises(ValueError) as caught:
            async with app.router.lifespan_context(app):
                raise initial
        self.assertIs(caught.exception, initial)
        self.assert_detached(app)
        engine.dispose.assert_called_once_with()

    async def test_startup_failure_never_publishes_runtime_or_uses_historical_fallback(self):
        self.create.side_effect = RuntimeError(SENSITIVE)
        app = module.create_app(config=self.config())
        add_probe(app)
        with self.assertRaises(database_lifespan.SqlLifespanError) as caught:
            async with app.router.lifespan_context(app):
                pass
        self.assertNotIn(SENSITIVE, repr(caught.exception))
        self.assert_detached(app)
        self.create.assert_called_once()
        self.assertEqual((await self.request(app)).status_code, 503)

    async def test_closed_borrowed_runtime_is_refused_at_startup(self):
        expected, engine, factory, _ = resource()
        app = module.create_app(runtime=expected)
        expected.dispose()
        engine.dispose.reset_mock()
        with self.assertRaises(database_lifespan.SqlLifespanError):
            async with app.router.lifespan_context(app):
                pass
        engine.dispose.assert_not_called()
        factory.assert_not_called()
        self.create.assert_not_called()
        self.assert_detached(app)


class ApplicationImportTests(unittest.TestCase):
    def test_import_and_construction_do_not_load_legacy_routes_or_sql_resources(self):
        script = r'''
            import builtins, importlib.abc, io, sys
            from contextlib import ExitStack
            from unittest.mock import Mock, patch
            import fastapi, pydantic, sqlalchemy, sqlalchemy.orm
            sys.path.insert(0,sys.argv[1])
            def forbidden(*args,**kwargs): raise AssertionError('Implicit I/O or SQL forbidden')
            class BlockLegacy(importlib.abc.MetaPathFinder):
                def find_spec(self,fullname,path=None,target=None):
                    if (fullname in ('app.main','app.core.database','app.core.config','pydantic_settings','dotenv')
                            or fullname.startswith(('app.api.routes','app.services','app.p101'))):
                        forbidden()
            sys.meta_path.insert(0,BlockLegacy())
            with ExitStack() as guards:
                for name in ('sqlalchemy.create_engine','sqlalchemy.engine_from_config',
                             'sqlalchemy.orm.sessionmaker','sqlalchemy.orm.Session',
                             'sqlalchemy.engine.Engine.connect','socket.create_connection','socket.socket.connect'):
                    guards.enter_context(patch(name,side_effect=forbidden))
                from app.application import create_app,assert_sql_runtime_binding
                from app.core.database_runtime import SqlRuntime
                from app.core.config_loader import load_application_config
                with patch('builtins.open',side_effect=forbidden),patch('io.open',side_effect=forbidden):
                    config=load_application_config({'database_url':sys.argv[2]})
                    a=create_app(config=config)
                    b=create_app(runtime=SqlRuntime(Mock(),Mock()))
                    assert a is not b and a.routes==[] and b.routes==[]
                    assert not hasattr(a.state,'sql_runtime') and not hasattr(b.state,'sql_runtime')
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
