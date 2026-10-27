"""Simulated runtimes and in-process ASGI requests; no SQL or network server."""

from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from fastapi import Depends, FastAPI, HTTPException, Request
import httpx
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.database_runtime import SqlRuntime, SqlRuntimeError
from app.core.dependencies import get_db


DETAIL = "SQL_RUNTIME_UNAVAILABLE"
SENSITIVE = "SYNTHETIC-ACQUISITION-DETAIL-NEVER-PUBLIC"


def session(marker):
    db = Mock(spec=Session)
    db.info = {"marker": marker}
    return db


def application(runtime=None):
    app = FastAPI()
    if runtime is not None:
        app.state.sql_runtime = runtime

    @app.get("/probe")
    def probe(db=Depends(get_db)):
        return {"marker": db.info["marker"]}

    return app


class DatabaseDependencyAsgiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        # The unittest event loop already exists. Block all subsequent application
        # connections and runtime construction; ASGITransport does not use TCP.
        for name in ("sqlalchemy.create_engine", "sqlalchemy.orm.sessionmaker",
                     "app.core.database_runtime.create_engine", "app.core.database_runtime.sessionmaker",
                     "sqlalchemy.engine.Engine.connect", "socket.create_connection", "socket.socket.connect"):
            self.guards.enter_context(patch(name, side_effect=AssertionError("SQL/network forbidden")))

    async def request(self, app, path="/probe", **kwargs):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://asgi.test") as client:
            return await client.get(path, **kwargs)

    def assert_session_closed_without_commit(self, db):
        db.close.assert_called_once_with()
        db.commit.assert_not_called()

    async def test_absent_runtime_returns_constant_503(self):
        response = await self.request(application())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": DETAIL})

    async def test_incorrect_runtime_returns_constant_503_without_calling_it(self):
        for runtime in (object(), SENSITIVE, Mock(spec=SqlRuntime)):
            with self.subTest(kind=type(runtime).__name__):
                response = await self.request(application(runtime))
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"detail": DETAIL})
                self.assertNotIn(SENSITIVE, response.text)
                if isinstance(runtime, Mock):
                    runtime.session.assert_not_called()
        app = application()
        app.state.sql_runtime = None
        self.assertEqual((await self.request(app)).status_code, 503)

    async def test_closed_runtime_returns_503_without_session_or_disposal_retry(self):
        engine, factory = Mock(), Mock()
        runtime = SqlRuntime(engine, factory)
        runtime.dispose()
        engine.dispose.reset_mock()
        response = await self.request(application(runtime))
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": DETAIL})
        factory.assert_not_called()
        engine.dispose.assert_not_called()

    async def test_acquisition_failures_are_sanitized_including_http_errors(self):
        for failure in (RuntimeError(SENSITIVE), SQLAlchemyError(SENSITIVE),
                        HTTPException(status_code=401, detail=SENSITIVE)):
            with self.subTest(kind=type(failure).__name__):
                engine, factory = Mock(), Mock(side_effect=failure)
                response = await self.request(application(SqlRuntime(engine, factory)))
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"detail": DETAIL})
                self.assertNotIn(SENSITIVE, response.text)
                factory.assert_called_once_with()
                engine.dispose.assert_not_called()

    async def test_provided_session_closes_after_success_without_commit_or_dispose(self):
        engine, db = Mock(), session("app-session")
        factory = Mock(return_value=db)
        response = await self.request(application(SqlRuntime(engine, factory)))
        self.assertEqual(response.json(), {"marker": "app-session"})
        self.assertEqual(response.status_code, 200)
        factory.assert_called_once_with()
        self.assert_session_closed_without_commit(db)
        engine.dispose.assert_not_called()

    async def test_two_requests_have_distinct_sessions_and_request_local_dependency_cache(self):
        first, second = session("first"), session("second")
        factory = Mock(side_effect=[first, second])
        engine = Mock()
        app = application(SqlRuntime(engine, factory))

        @app.get("/twice")
        def twice(left=Depends(get_db), right=Depends(get_db)):
            return {"same_request_session": left is right, "marker": left.info["marker"]}

        one, two = await self.request(app, "/twice"), await self.request(app, "/twice")
        self.assertEqual(one.json(), {"same_request_session": True, "marker": "first"})
        self.assertEqual(two.json(), {"same_request_session": True, "marker": "second"})
        self.assertEqual(factory.call_count, 2)
        self.assert_session_closed_without_commit(first)
        self.assert_session_closed_without_commit(second)
        engine.dispose.assert_not_called()

    async def test_business_sql_and_runtime_handler_exceptions_are_not_changed_to_503(self):
        for failure in (ValueError("Business failure"), SQLAlchemyError("Handler SQL failure"),
                        SqlRuntimeError("Handler runtime failure")):
            with self.subTest(kind=type(failure).__name__):
                db, engine = session("handler"), Mock()
                app = application(SqlRuntime(engine, Mock(return_value=db)))

                @app.get("/failure")
                def failed(db=Depends(get_db)):
                    raise failure

                with self.assertRaises(type(failure)) as caught:
                    await self.request(app, "/failure")
                self.assertIs(caught.exception, failure)
                self.assert_session_closed_without_commit(db)
                engine.dispose.assert_not_called()

    async def test_http_handler_exception_keeps_its_status_detail_and_headers(self):
        engine, db = Mock(), session("http-error")
        app = application(SqlRuntime(engine, Mock(return_value=db)))

        @app.get("/conflict")
        def conflict(db=Depends(get_db)):
            raise HTTPException(409, "Business conflict", headers={"X-Test-Conflict": "yes"})

        response = await self.request(app, "/conflict")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {"detail": "Business conflict"})
        self.assertEqual(response.headers["X-Test-Conflict"], "yes")
        self.assert_session_closed_without_commit(db)
        engine.dispose.assert_not_called()

    async def test_cleanup_error_is_not_reclassified_as_acquisition_503(self):
        failure = RuntimeError("Session close failure")
        engine, db = Mock(), session("cleanup")
        db.close.side_effect = failure
        with self.assertRaises(RuntimeError) as caught:
            await self.request(application(SqlRuntime(engine, Mock(return_value=db))))
        self.assertIs(caught.exception, failure)
        self.assert_session_closed_without_commit(db)
        engine.dispose.assert_not_called()

    async def test_override_of_exact_new_dependency_bypasses_acquisition(self):
        engine, factory = Mock(), Mock(side_effect=AssertionError("Original dependency called"))
        app = application(SqlRuntime(engine, factory))
        db = session("override")

        def replacement():
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = replacement
        response = await self.request(app)
        self.assertEqual(response.json(), {"marker": "override"})
        factory.assert_not_called()
        engine.dispose.assert_not_called()
        self.assert_session_closed_without_commit(db)

    async def test_two_applications_ignore_client_destination_hints_and_stay_isolated(self):
        db_a, db_b = session("application-a"), session("application-b")
        engine_a, engine_b = Mock(), Mock()
        factory_a, factory_b = Mock(return_value=db_a), Mock(return_value=db_b)
        app_a = application(SqlRuntime(engine_a, factory_a))
        app_b = application(SqlRuntime(engine_b, factory_b))
        hints = {"params": {"company_id": "999", "database": "other-destination"},
                 "headers": {"X-Database": "other-destination", "X-Company-Id": "999"}}
        one = await self.request(app_a, **hints)
        two = await self.request(app_b, **hints)
        self.assertEqual(one.json(), {"marker": "application-a"})
        self.assertEqual(two.json(), {"marker": "application-b"})
        factory_a.assert_called_once_with()
        factory_b.assert_called_once_with()
        self.assert_session_closed_without_commit(db_a)
        self.assert_session_closed_without_commit(db_b)
        engine_a.dispose.assert_not_called()
        engine_b.dispose.assert_not_called()


class DatabaseDependencyImportTests(unittest.TestCase):
    def test_acquisition_error_has_no_sensitive_exception_chain(self):
        failure = RuntimeError(SENSITIVE)
        app = application(SqlRuntime(Mock(), Mock(side_effect=failure)))
        request = Request({"type": "http", "app": app, "headers": []})
        dependency = get_db(request)
        with self.assertRaises(HTTPException) as caught:
            next(dependency)
        error = caught.exception
        self.assertEqual(error.status_code, 503)
        self.assertEqual(error.detail, DETAIL)
        self.assertNotIn(SENSITIVE, repr(error))
        self.assertIsNone(error.__context__)
        self.assertIsNone(error.__cause__)

    def test_fresh_import_does_not_load_legacy_or_create_sql_resources(self):
        script = r'''
            import builtins, importlib.abc, io, sys
            from contextlib import ExitStack
            from unittest.mock import patch
            import fastapi, pydantic, sqlalchemy, sqlalchemy.orm
            sys.path.insert(0, sys.argv[1])
            def forbidden(*args, **kwargs):
                raise AssertionError('Legacy configuration, SQL or network forbidden')
            class BlockLegacy(importlib.abc.MetaPathFinder):
                def find_spec(self, fullname, path=None, target=None):
                    if fullname in ('app.core.config','app.core.database','app.main','pydantic_settings','dotenv'):
                        forbidden()
            sys.meta_path.insert(0, BlockLegacy())
            def guard_open(original):
                def checked(file, *args, **kwargs):
                    if isinstance(file,str) and (file.endswith('.env') or '.env.' in file): forbidden()
                    return original(file,*args,**kwargs)
                return checked
            with ExitStack() as guards:
                guards.enter_context(patch('builtins.open',guard_open(builtins.open)))
                guards.enter_context(patch('io.open',guard_open(io.open)))
                for name in ('sqlalchemy.create_engine','sqlalchemy.engine_from_config',
                             'sqlalchemy.orm.sessionmaker','sqlalchemy.orm.Session',
                             'sqlalchemy.engine.Engine.connect','socket.create_connection','socket.socket.connect'):
                    guards.enter_context(patch(name,side_effect=forbidden))
                from app.core.dependencies import get_db
                assert callable(get_db)
                assert 'app.core.config' not in sys.modules
                assert 'app.core.database' not in sys.modules
                assert 'app.main' not in sys.modules
        '''
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP")
               if key in os.environ}
        env.update(DATABASE_URL="invalid://ambient", PGHOST="ambient.invalid")
        result = subprocess.run(
            [sys.executable, "-B", "-I", "-c", textwrap.dedent(script), str(ROOT / "backend")],
            cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
