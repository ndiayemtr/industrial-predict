"""Execute real ASGI lifespan contexts with simulated SQL resources, never a server."""

import asyncio
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

from app.core import database_lifespan as module
from app.core.config_loader import ConfigurationError, load_application_config
from app.core.database_runtime import SqlRuntime
from app.core.dependencies import get_db


SENSITIVE = "SYNTHETIC-LIFESPAN-DETAIL-NEVER-PUBLIC"
URL = "postgresql+psycopg://fake_role:FAKE_ONLY@sql.example.invalid:6543/fake_database"


def resource(marker="demo"):
    engine, db = Mock(), Mock(spec=Session)
    db.info = {"marker": marker}
    factory = Mock(return_value=db)
    return SqlRuntime(engine, factory), engine, factory, db


def application(lifespan):
    app = FastAPI(lifespan=lifespan)

    @app.get("/probe")
    def probe(db=Depends(get_db)):
        return {"marker": db.info["marker"]}

    return app


class FailingInstallation(State):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "sql_runtime":
            raise RuntimeError(SENSITIVE)  # Simulate mutation followed by startup failure.


class FailingActivation(State):
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == module._MARKER:
            raise RuntimeError(SENSITIVE)


class SqlLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        # The isolated unittest loop is already started. ASGI requests stay in-process.
        for name in ("sqlalchemy.create_engine", "sqlalchemy.orm.sessionmaker",
                     "app.core.database_runtime.create_engine", "app.core.database_runtime.sessionmaker",
                     "sqlalchemy.engine.Engine.connect", "sqlalchemy.schema.MetaData.create_all",
                     "socket.create_connection", "socket.socket.connect"):
            self.guards.enter_context(patch(name, side_effect=AssertionError("SQL/network forbidden")))
        self.create = self.guards.enter_context(patch.object(
            module, "create_sql_runtime", side_effect=AssertionError("Factory must be simulated")))

    def config(self):
        return load_application_config({"database_url": URL})

    def assert_detached(self, app):
        self.assertFalse(hasattr(app.state, "sql_runtime"))
        self.assertFalse(hasattr(app.state, module._MARKER))

    def assert_no_session_or_transaction(self, factory, db):
        factory.assert_not_called()
        db.commit.assert_not_called()
        db.close.assert_not_called()

    async def request(self, app, path="/probe"):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://asgi.test") as client:
            return await client.get(path)

    async def test_preparation_creates_nothing_and_rejects_bad_parameters(self):
        loan, engine, factory, db = resource()
        for kwargs in ({}, {"config": self.config(), "runtime": loan}, {"config": {}},
                       {"config": URL}, {"runtime": object()}, {"runtime": Mock(spec=SqlRuntime)}):
            with self.subTest(keys=list(kwargs)):
                with self.assertRaises(module.SqlLifespanError):
                    module.create_sql_lifespan(**kwargs)
        invalid = self.config().model_copy(update={"database_url": "invalid"})
        with self.assertRaises(ConfigurationError):
            module.create_sql_lifespan(config=invalid)
        self.assertTrue(callable(module.create_sql_lifespan(config=self.config())))
        self.assertTrue(callable(module.create_sql_lifespan(runtime=loan)))
        self.create.assert_not_called()
        engine.dispose.assert_not_called()
        self.assert_no_session_or_transaction(factory, db)

    async def test_owned_startup_installs_without_probe_and_detaches_before_single_disposal(self):
        runtime, engine, factory, db = resource()
        config = self.config()
        lifespan = module.create_sql_lifespan(config=config)
        app = application(lifespan)
        self.create.assert_not_called()
        self.create.side_effect = [runtime]
        events = []

        def disposal():
            self.assertFalse(hasattr(app.state, "sql_runtime"))
            events.append("detached-before-disposal")

        engine.dispose.side_effect = disposal
        async with app.router.lifespan_context(app):
            self.assertIs(app.state.sql_runtime, runtime)
            self.assertTrue(hasattr(app.state, module._MARKER))
            self.assert_no_session_or_transaction(factory, db)
            engine.dispose.assert_not_called()
        self.assertEqual(self.create.call_count, 1)
        self.assertEqual(self.create.call_args.args[0], config)
        engine.dispose.assert_called_once_with()
        self.assertEqual(events, ["detached-before-disposal"])
        self.assert_detached(app)
        self.assert_no_session_or_transaction(factory, db)
        self.assertFalse(module._runtime_is_open(runtime))

    async def test_borrowed_runtime_is_the_same_object_and_is_never_disposed(self):
        runtime, engine, factory, db = resource()
        app = application(module.create_sql_lifespan(runtime=runtime))
        async with app.router.lifespan_context(app):
            self.assertIs(app.state.sql_runtime, runtime)
        self.assert_detached(app)
        self.create.assert_not_called()
        engine.dispose.assert_not_called()
        self.assertIs(runtime.engine, engine)
        self.assertTrue(module._runtime_is_open(runtime))
        self.assert_no_session_or_transaction(factory, db)

    async def test_dependency_returns_503_before_after_and_works_during_actual_lifespan(self):
        runtime, engine, factory, db = resource("during-lifespan")
        app = application(module.create_sql_lifespan(runtime=runtime))
        before = await self.request(app)
        self.assertEqual((before.status_code, before.json()), (503, {"detail": "SQL_RUNTIME_UNAVAILABLE"}))
        factory.assert_not_called()
        # ASGITransport alone does not execute startup/shutdown. Enter the real context.
        async with app.router.lifespan_context(app):
            during = await self.request(app)
            self.assertEqual(during.status_code, 200)
            self.assertEqual(during.json(), {"marker": "during-lifespan"})
        after = await self.request(app)
        self.assertEqual((after.status_code, after.json()), (503, {"detail": "SQL_RUNTIME_UNAVAILABLE"}))
        factory.assert_called_once_with()
        db.close.assert_called_once_with()
        db.commit.assert_not_called()
        engine.dispose.assert_not_called()

    async def test_preinstalled_slot_including_none_is_preserved(self):
        loan, engine, _, _ = resource()
        for existing in (None, object(), loan):
            with self.subTest(kind=type(existing).__name__):
                app = application(module.create_sql_lifespan(runtime=loan))
                app.state.sql_runtime = existing
                with self.assertRaises(module.SqlLifespanError):
                    async with app.router.lifespan_context(app):
                        self.fail("Preinstalled runtime accepted")
                self.assertIs(app.state.sql_runtime, existing)
                self.assertFalse(hasattr(app.state, module._MARKER))
        engine.dispose.assert_not_called()
        self.create.assert_not_called()

    async def test_existing_activation_marker_is_preserved(self):
        runtime, engine, _, _ = resource()
        app = application(module.create_sql_lifespan(runtime=runtime))
        foreign = object()
        setattr(app.state, module._MARKER, foreign)
        with self.assertRaises(module.SqlLifespanError):
            async with app.router.lifespan_context(app):
                pass
        self.assertIs(getattr(app.state, module._MARKER), foreign)
        engine.dispose.assert_not_called()

    async def test_same_lifespan_refuses_nested_activation_even_on_another_app(self):
        runtime, engine, _, _ = resource()
        lifespan = module.create_sql_lifespan(runtime=runtime)
        app, other = application(lifespan), application(lifespan)
        async with app.router.lifespan_context(app):
            for target in (app, other):
                with self.assertRaises(module.SqlLifespanError):
                    async with lifespan(target):
                        self.fail("Double activation accepted")
            self.assertIs(app.state.sql_runtime, runtime)
            self.assert_detached(other)
        self.assert_detached(app)
        engine.dispose.assert_not_called()

    async def test_two_lifespans_cannot_claim_the_same_app(self):
        first, _, _, _ = resource()
        second, engine, _, _ = resource()
        app = application(module.create_sql_lifespan(runtime=first))
        other = module.create_sql_lifespan(runtime=second)
        async with app.router.lifespan_context(app):
            with self.assertRaises(module.SqlLifespanError):
                async with other(app):
                    pass
            self.assertIs(app.state.sql_runtime, first)
        engine.dispose.assert_not_called()

    async def test_closed_borrowed_runtime_is_rejected_at_startup_without_disposal(self):
        runtime, engine, factory, db = resource()
        lifespan = module.create_sql_lifespan(runtime=runtime)
        runtime.dispose()  # Owner closes it after preparation, before startup.
        engine.dispose.reset_mock()
        app = application(lifespan)
        with self.assertRaises(module.SqlLifespanError):
            async with app.router.lifespan_context(app):
                pass
        self.assert_detached(app)
        engine.dispose.assert_not_called()
        self.assert_no_session_or_transaction(factory, db)

    async def test_factory_failure_is_sanitized_and_activation_is_released(self):
        self.create.side_effect = RuntimeError(SENSITIVE)
        app = application(module.create_sql_lifespan(config=self.config()))
        with self.assertRaises(module.SqlLifespanError) as caught:
            async with app.router.lifespan_context(app):
                pass
        self.assertEqual(str(caught.exception), "SQL_LIFESPAN_RUNTIME_CREATION_FAILED")
        self.assertIsNone(caught.exception.__context__)
        self.assertNotIn(SENSITIVE, repr(caught.exception))
        self.create.assert_called_once()
        self.assert_detached(app)

    async def test_invalid_factory_runtime_is_not_published_or_disposed(self):
        wrong = Mock(spec=SqlRuntime)
        self.create.side_effect = [wrong]
        app = application(module.create_sql_lifespan(config=self.config()))
        with self.assertRaises(module.SqlLifespanError):
            async with app.router.lifespan_context(app):
                pass
        wrong.dispose.assert_not_called()
        self.assert_detached(app)

    async def test_partial_installation_failure_cleans_owned_but_never_borrowed_runtime(self):
        for owned in (False, True):
            with self.subTest(owned=owned):
                runtime, engine, factory, db = resource()
                self.create.side_effect = [runtime]
                lifespan = (module.create_sql_lifespan(config=self.config()) if owned
                            else module.create_sql_lifespan(runtime=runtime))
                app = application(lifespan)
                app.state = FailingInstallation()
                engine.dispose.side_effect = lambda: self.assertFalse(hasattr(app.state, "sql_runtime"))
                with self.assertRaises(module.SqlLifespanError) as caught:
                    async with app.router.lifespan_context(app):
                        self.fail("Startup failure ignored")
                self.assertEqual(str(caught.exception), "SQL_LIFESPAN_INSTALLATION_FAILED")
                self.assertNotIn(SENSITIVE, repr(caught.exception))
                self.assertIsNone(caught.exception.__context__)
                self.assert_detached(app)
                self.assertEqual(engine.dispose.call_count, 1 if owned else 0)
                self.assert_no_session_or_transaction(factory, db)

    async def test_partial_activation_failure_does_not_create_a_runtime(self):
        app = application(module.create_sql_lifespan(config=self.config()))
        app.state = FailingActivation()
        with self.assertRaises(module.SqlLifespanError) as caught:
            async with app.router.lifespan_context(app):
                pass
        self.assertEqual(str(caught.exception), "SQL_LIFESPAN_ACTIVATION_FAILED")
        self.assertNotIn(SENSITIVE, repr(caught.exception))
        self.create.assert_not_called()
        self.assert_detached(app)

    async def test_lifespan_exception_is_preserved_and_owned_runtime_disposed_once(self):
        runtime, engine, _, _ = resource()
        self.create.side_effect = [runtime]
        app = application(module.create_sql_lifespan(config=self.config()))
        initial = ValueError("Original lifespan failure")
        with self.assertRaises(ValueError) as caught:
            async with app.router.lifespan_context(app):
                raise initial
        self.assertIs(caught.exception, initial)
        self.assert_detached(app)
        engine.dispose.assert_called_once_with()

    async def test_cancellation_still_detaches_and_cleans_owned_runtime(self):
        runtime, engine, _, _ = resource()
        self.create.side_effect = [runtime]
        app = application(module.create_sql_lifespan(config=self.config()))
        initial = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError) as caught:
            async with app.router.lifespan_context(app):
                raise initial
        self.assertIs(caught.exception, initial)
        self.assert_detached(app)
        engine.dispose.assert_called_once_with()

    async def test_borrowed_runtime_never_disposed_after_lifespan_exception(self):
        runtime, engine, _, _ = resource()
        app = application(module.create_sql_lifespan(runtime=runtime))
        initial = ValueError("Borrowed lifespan failure")
        with self.assertRaises(ValueError) as caught:
            async with app.router.lifespan_context(app):
                raise initial
        self.assertIs(caught.exception, initial)
        self.assert_detached(app)
        engine.dispose.assert_not_called()
        self.assertTrue(module._runtime_is_open(runtime))

    async def test_handler_exception_is_not_503_and_session_closes_without_engine_disposal(self):
        runtime, engine, factory, db = resource()
        app = application(module.create_sql_lifespan(runtime=runtime))
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
            self.assertIs(app.state.sql_runtime, runtime)
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(db.close.call_count, 2)
        db.commit.assert_not_called()
        engine.dispose.assert_not_called()

    async def test_dispose_failure_is_publicly_reported_after_detachment_without_retry(self):
        runtime, engine, _, _ = resource()
        self.create.side_effect = [runtime]
        engine.dispose.side_effect = RuntimeError(SENSITIVE)
        app = application(module.create_sql_lifespan(config=self.config()))
        with self.assertRaises(module.SqlLifespanError) as caught:
            async with app.router.lifespan_context(app):
                pass
        self.assertIn("SQL_RUNTIME_DISPOSE_FAILED", str(caught.exception))
        self.assertNotIn(SENSITIVE, repr(caught.exception))
        self.assertIsNone(caught.exception.__context__)
        engine.dispose.assert_called_once_with()
        self.assert_detached(app)
        self.assertEqual((await self.request(app)).status_code, 503)

    async def test_initial_exception_wins_and_cleanup_error_is_reported_as_safe_note(self):
        runtime, engine, _, _ = resource()
        self.create.side_effect = [runtime]
        engine.dispose.side_effect = RuntimeError(SENSITIVE)
        app = application(module.create_sql_lifespan(config=self.config()))
        initial = ValueError("Primary lifespan failure")
        with self.assertRaises(ValueError) as caught:
            async with app.router.lifespan_context(app):
                raise initial
        self.assertIs(caught.exception, initial)
        self.assertIn("SQL_RUNTIME_DISPOSE_FAILED", " ".join(initial.__notes__))
        self.assertNotIn(SENSITIVE, " ".join(initial.__notes__))
        engine.dispose.assert_called_once_with()
        self.assert_detached(app)

    async def test_startup_error_is_preserved_when_its_cleanup_also_fails(self):
        runtime, engine, _, _ = resource()
        self.create.side_effect = [runtime]
        engine.dispose.side_effect = RuntimeError(SENSITIVE)
        app = application(module.create_sql_lifespan(config=self.config()))
        app.state = FailingInstallation()
        with self.assertRaises(module.SqlLifespanError) as caught:
            async with app.router.lifespan_context(app):
                pass
        self.assertEqual(str(caught.exception), "SQL_LIFESPAN_INSTALLATION_FAILED")
        self.assertIn("SQL_RUNTIME_DISPOSE_FAILED", " ".join(caught.exception.__notes__))
        self.assertNotIn(SENSITIVE, " ".join(caught.exception.__notes__))
        self.assert_detached(app)
        engine.dispose.assert_called_once_with()

    async def test_foreign_replacement_is_reported_without_removal_or_disposal(self):
        for owned in (False, True):
            with self.subTest(owned=owned):
                initial, engine, _, _ = resource()
                foreign, foreign_engine, _, _ = resource()
                self.create.side_effect = [initial]
                lifespan = (module.create_sql_lifespan(config=self.config()) if owned
                            else module.create_sql_lifespan(runtime=initial))
                app = application(lifespan)
                with self.assertRaises(module.SqlLifespanError) as caught:
                    async with app.router.lifespan_context(app):
                        app.state.sql_runtime = foreign
                self.assertIn("SQL_LIFESPAN_STATE_CONFLICT", str(caught.exception))
                self.assertIs(app.state.sql_runtime, foreign)
                self.assertFalse(hasattr(app.state, module._MARKER))
                foreign_engine.dispose.assert_not_called()
                self.assertEqual(engine.dispose.call_count, 1 if owned else 0)

    async def test_independent_apps_have_independent_owned_runtimes(self):
        a, engine_a, _, db_a = resource("a")
        b, engine_b, _, db_b = resource("b")
        self.create.side_effect = [a, b]
        app_a = application(module.create_sql_lifespan(config=self.config()))
        app_b = application(module.create_sql_lifespan(config=self.config()))
        async with app_a.router.lifespan_context(app_a), app_b.router.lifespan_context(app_b):
            self.assertIs(app_a.state.sql_runtime, a)
            self.assertIs(app_b.state.sql_runtime, b)
            self.assertEqual((await self.request(app_a)).json(), {"marker": "a"})
            self.assertEqual((await self.request(app_b)).json(), {"marker": "b"})
        engine_a.dispose.assert_called_once_with()
        engine_b.dispose.assert_called_once_with()
        db_a.commit.assert_not_called()
        db_b.commit.assert_not_called()
        self.assert_detached(app_a)
        self.assert_detached(app_b)

    async def test_new_owned_cycle_creates_a_new_runtime(self):
        a, engine_a, _, _ = resource("first")
        b, engine_b, _, _ = resource("second")
        self.create.side_effect = [a, b]
        app = application(module.create_sql_lifespan(config=self.config()))
        async with app.router.lifespan_context(app):
            self.assertIs(app.state.sql_runtime, a)
        self.assert_detached(app)
        async with app.router.lifespan_context(app):
            self.assertIs(app.state.sql_runtime, b)
        self.assertEqual(self.create.call_count, 2)
        engine_a.dispose.assert_called_once_with()
        engine_b.dispose.assert_called_once_with()
        self.assert_detached(app)


class SqlLifespanImportTests(unittest.TestCase):
    def test_import_and_preparation_are_inert_without_legacy_config(self):
        script = r'''
            import builtins, importlib.abc, io, sys
            from contextlib import ExitStack
            from unittest.mock import Mock, patch
            import fastapi, pydantic, sqlalchemy, sqlalchemy.orm
            sys.path.insert(0,sys.argv[1])
            def forbidden(*args,**kwargs): raise AssertionError('Implicit I/O or SQL forbidden')
            class BlockLegacy(importlib.abc.MetaPathFinder):
                def find_spec(self,fullname,path=None,target=None):
                    if fullname in ('app.main','app.core.database','app.core.config','pydantic_settings','dotenv'):
                        forbidden()
            sys.meta_path.insert(0,BlockLegacy())
            with ExitStack() as guards:
                for name in ('sqlalchemy.create_engine','sqlalchemy.engine_from_config',
                             'sqlalchemy.orm.sessionmaker','sqlalchemy.orm.Session',
                             'sqlalchemy.engine.Engine.connect','socket.create_connection','socket.socket.connect'):
                    guards.enter_context(patch(name,side_effect=forbidden))
                from app.core.database_lifespan import create_sql_lifespan
                from app.core.database_runtime import SqlRuntime
                from app.core.config_loader import load_application_config
                with patch('builtins.open',side_effect=forbidden),patch('io.open',side_effect=forbidden):
                    config=load_application_config({'database_url':sys.argv[2]})
                    assert callable(create_sql_lifespan(config=config))
                    assert callable(create_sql_lifespan(runtime=SqlRuntime(Mock(),Mock())))
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
