"""Simulated authorization, services and SQL resources; in-process ASGI only."""

from contextlib import ExitStack
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException, Request
import httpx
from sqlalchemy.orm import Session


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.application import create_app
from app.api.routes import company_reads as module
from app.core.database_runtime import SqlRuntime
from app.core.dependencies import get_db
from app.schemas.company import CompanyRead


PATH = "/api/v1/companies/7"
SENSITIVE = "SYNTHETIC-AUTHORIZATION-DETAIL-NEVER-PUBLIC"


def grant(company_id=7, subject="test-subject", permission="companies:read"):
    return module.CompanyReadAuthorization(subject, company_id, permission)


def resource(marker="app"):
    engine, db = Mock(), Mock(spec=Session)
    db.info = {"marker": marker}
    factory = Mock(return_value=db)
    return SqlRuntime(engine, factory), engine, factory, db


def company(identity=7):
    return SimpleNamespace(id=identity, name="Entreprise test", code="TEST-COMPANY",
                           description=None, created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                           updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc))


class CompanyReadTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.guards = ExitStack()
        self.addCleanup(self.guards.close)
        for name in ("sqlalchemy.create_engine", "sqlalchemy.orm.sessionmaker",
                     "app.core.database_runtime.create_engine", "app.core.database_runtime.sessionmaker",
                     "sqlalchemy.engine.Engine.connect", "sqlalchemy.schema.MetaData.create_all",
                     "socket.create_connection", "socket.socket.connect"):
            self.guards.enter_context(patch(name, side_effect=AssertionError("SQL/network forbidden")))
        self.service = Mock(spec=module.CompanyService)
        self.service.get_by_id.return_value = company()
        self.service_type = self.guards.enter_context(patch.object(module, "CompanyService", return_value=self.service))

    def mount(self, provider):
        runtime, engine, factory, db = resource()
        app = create_app(runtime=runtime)
        self.assertEqual(app.routes, [])  # Factory never registers this adapter automatically.
        app.include_router(module.create_company_read_router(authorize_company_read=provider))
        return app, runtime, engine, factory, db

    async def request(self, app, path=PATH, method="GET", **kwargs):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://asgi.test") as client:
            return await client.request(method, path, **kwargs)

    def assert_no_writes(self, db):
        # No query either: the business service is deliberately simulated in this suite.
        for name in ("add", "add_all", "delete", "flush", "commit", "execute", "scalar", "scalars"):
            getattr(db, name).assert_not_called()

    async def test_missing_or_invalid_provider_is_rejected_at_router_construction(self):
        with self.assertRaises(TypeError):
            module.create_company_read_router()
        async def async_provider(request, identity):
            return grant(identity)
        for provider in (None, True, 7, {}, async_provider):
            with self.subTest(kind=type(provider).__name__), self.assertRaises(module.CompanyReadRouterError) as caught:
                module.create_company_read_router(authorize_company_read=provider)
            self.assertEqual(str(caught.exception), "COMPANY_READ_AUTHORIZER_REQUIRED")
        self.service_type.assert_not_called()

    async def test_only_detail_get_is_mounted_without_write_or_list_endpoints(self):
        app, _, engine, factory, db = self.mount(Mock(return_value=grant()))
        self.assertEqual(len(app.routes), 1)
        # Inspect the APIRouter directly: FastAPI may wrap mounted routers.
        router = module.create_company_read_router(authorize_company_read=Mock(return_value=grant()))
        self.assertEqual(len(router.routes), 1)
        route = router.routes[0]
        self.assertEqual(route.path, "/api/v1/companies/{company_id}")
        self.assertEqual(route.methods, {"GET"})
        self.assertIs(route.response_model, CompanyRead)
        paths = app.openapi()["paths"]
        self.assertEqual(set(paths), {route.path})
        self.assertEqual(set(paths[route.path]), {"get"})
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            self.assertEqual((await self.request(app, method=method)).status_code, 405)
        for path in ("/api/v1/companies", "/health", "/docs", "/openapi.json"):
            self.assertEqual((await self.request(app, path=path)).status_code, 404)
        factory.assert_not_called()
        self.service_type.assert_not_called()
        engine.dispose.assert_not_called()
        self.assert_no_writes(db)

    async def test_authorized_response_uses_existing_service_schema_and_closes_session(self):
        provider = Mock(return_value=grant())
        app, runtime, engine, factory, db = self.mount(provider)
        async with app.router.lifespan_context(app):
            self.assertIs(app.state.sql_runtime, runtime)
            response = await self.request(app)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), CompanyRead.model_validate(company()).model_dump(mode="json"))
        self.service_type.assert_called_once_with(db)
        self.service.get_by_id.assert_called_once_with(7)
        provider.assert_called_once()
        request, requested_id = provider.call_args.args
        self.assertIsInstance(request, Request)
        self.assertIs(request.app, app)
        self.assertEqual(requested_id, 7)
        factory.assert_called_once_with()
        db.close.assert_called_once_with()
        engine.dispose.assert_not_called()
        self.assert_no_writes(db)

    async def test_authorized_missing_company_keeps_historical_404(self):
        self.service.get_by_id.return_value = None
        app, _, _, _, db = self.mount(Mock(return_value=grant()))
        async with app.router.lifespan_context(app):
            response = await self.request(app)
        self.assertEqual((response.status_code, response.json()), (404, {"detail": "Company not found"}))
        db.close.assert_called_once_with()
        self.assert_no_writes(db)

    async def test_absent_boolean_client_id_and_incoherent_authorizations_fail_before_sql(self):
        invalid = (None, True, False, 7, {"company_id": 7, "subject_id": "client", "permission": "companies:read"},
                   grant(8), grant(True), grant("7"), grant(-1), grant(subject=""),
                   grant(subject=None), grant(permission="companies:write"), grant(permission=True))
        for position, authorization in enumerate(invalid):
            with self.subTest(case=position):
                app, _, engine, factory, db = self.mount(Mock(return_value=authorization))
                async with app.router.lifespan_context(app):
                    response = await self.request(app)
                self.assertEqual((response.status_code, response.json()), (403, {"detail": "COMPANY_READ_FORBIDDEN"}))
                factory.assert_not_called()
                db.close.assert_not_called()
                engine.dispose.assert_not_called()
                self.assert_no_writes(db)
        self.service_type.assert_not_called()

    async def test_foreign_company_is_refused_without_repository_or_service_read(self):
        app, _, _, factory, _ = self.mount(Mock(return_value=grant(7)))
        async with app.router.lifespan_context(app):
            response = await self.request(app, path="/api/v1/companies/8",
                                          params={"company_id": "7"}, headers={"X-Company-Id": "7"})
        self.assertEqual(response.status_code, 403)
        factory.assert_not_called()
        self.service_type.assert_not_called()
        self.service.get_by_id.assert_not_called()

    async def test_provider_exceptions_have_stable_non_sensitive_denials(self):
        for failure in (RuntimeError(SENSITIVE), HTTPException(401, SENSITIVE)):
            with self.subTest(kind=type(failure).__name__):
                app, _, _, factory, _ = self.mount(Mock(side_effect=failure))
                async with app.router.lifespan_context(app):
                    response = await self.request(app)
                self.assertEqual((response.status_code, response.json()), (403, {"detail": "COMPANY_READ_FORBIDDEN"}))
                self.assertNotIn(SENSITIVE, response.text)
                factory.assert_not_called()
        self.service_type.assert_not_called()

    async def test_client_hints_cannot_grant_access_or_select_runtime(self):
        app, _, _, factory, _ = self.mount(Mock(return_value=None))
        async with app.router.lifespan_context(app):
            response = await self.request(app, params={"authorized": "true", "permission": "companies:read",
                "subject_id": "test-subject", "company_id": "7", "database": "other"},
                headers={"X-Authorized": "true", "X-Company-Id": "7", "X-Database": "other"})
        self.assertEqual(response.status_code, 403)
        factory.assert_not_called()
        self.service_type.assert_not_called()

    async def test_valid_authorization_has_sql_503_before_and_after_real_lifespan(self):
        app, _, _, factory, db = self.mount(Mock(return_value=grant()))
        before = await self.request(app)
        self.assertEqual((before.status_code, before.json()), (503, {"detail": "SQL_RUNTIME_UNAVAILABLE"}))
        self.service_type.assert_not_called()
        async with app.router.lifespan_context(app):
            self.assertEqual((await self.request(app)).status_code, 200)
        after = await self.request(app)
        self.assertEqual((after.status_code, after.json()), (503, {"detail": "SQL_RUNTIME_UNAVAILABLE"}))
        factory.assert_called_once_with()
        db.close.assert_called_once_with()
        self.assert_no_writes(db)

    async def test_get_db_override_is_effective_but_cannot_override_authorization(self):
        provider = Mock(return_value=grant())
        app, _, engine, factory, _ = self.mount(provider)
        override = Mock(spec=Session)

        def replacement():
            try:
                yield override
            finally:
                override.close()

        app.dependency_overrides[get_db] = replacement
        async with app.router.lifespan_context(app):
            self.assertEqual((await self.request(app)).status_code, 200)
            provider.return_value = None
            self.assertEqual((await self.request(app)).status_code, 403)
        self.service_type.assert_called_once_with(override)
        override.close.assert_called_once_with()
        factory.assert_not_called()
        engine.dispose.assert_not_called()
        self.assert_no_writes(override)

    async def test_two_apps_use_only_their_own_runtime_even_with_client_destination_hints(self):
        app_a, a, engine_a, factory_a, db_a = self.mount(Mock(return_value=grant(subject="subject-a")))
        app_b, b, engine_b, factory_b, db_b = self.mount(Mock(return_value=grant(subject="subject-b")))
        async with app_a.router.lifespan_context(app_a), app_b.router.lifespan_context(app_b):
            self.assertIs(app_a.state.sql_runtime, a)
            self.assertIs(app_b.state.sql_runtime, b)
            for app in (app_a, app_b):
                response = await self.request(app, params={"database": "other"}, headers={"X-Database": "other"})
                self.assertEqual(response.status_code, 200)
        self.assertEqual([call.args[0] for call in self.service_type.call_args_list], [db_a, db_b])
        for engine, factory, db in ((engine_a, factory_a, db_a), (engine_b, factory_b, db_b)):
            factory.assert_called_once_with()
            db.close.assert_called_once_with()
            engine.dispose.assert_not_called()
            self.assert_no_writes(db)

    async def test_service_exception_is_preserved_and_session_still_closes(self):
        failure = ValueError("Synthetic service failure")
        self.service.get_by_id.side_effect = failure
        app, _, engine, _, db = self.mount(Mock(return_value=grant()))
        async with app.router.lifespan_context(app):
            with self.assertRaises(ValueError) as caught:
                await self.request(app)
            self.assertIs(caught.exception, failure)
        db.close.assert_called_once_with()
        engine.dispose.assert_not_called()
        self.assert_no_writes(db)

    async def test_foreign_service_result_is_never_exposed(self):
        self.service.get_by_id.return_value = company(8)
        app, _, _, _, db = self.mount(Mock(return_value=grant()))
        async with app.router.lifespan_context(app):
            response = await self.request(app)
        self.assertEqual((response.status_code, response.json()), (503, {"detail": "COMPANY_READ_UNAVAILABLE"}))
        self.assertNotIn("Entreprise test", response.text)
        db.close.assert_called_once_with()
        self.assert_no_writes(db)


class CompanyReadImportTests(unittest.TestCase):
    def test_fresh_import_and_router_construction_do_not_load_legacy_or_create_sql(self):
        script = r'''
            import importlib.abc,sys
            from contextlib import ExitStack
            from unittest.mock import patch
            import fastapi,pydantic,sqlalchemy,sqlalchemy.orm
            sys.path.insert(0,sys.argv[1])
            def forbidden(*args,**kwargs): raise AssertionError('Legacy, SQL or network forbidden')
            class BlockLegacy(importlib.abc.MetaPathFinder):
                def find_spec(self,fullname,path=None,target=None):
                    if fullname in ('app.main','app.core.database','app.core.config',
                                    'app.api.routes.companies','pydantic_settings','dotenv'):
                        forbidden()
            sys.meta_path.insert(0,BlockLegacy())
            with ExitStack() as guards:
                for name in ('sqlalchemy.create_engine','sqlalchemy.engine_from_config',
                             'sqlalchemy.orm.sessionmaker','sqlalchemy.orm.Session',
                             'sqlalchemy.engine.Engine.connect','socket.create_connection','socket.socket.connect'):
                    guards.enter_context(patch(name,side_effect=forbidden))
                from app.api.routes.company_reads import CompanyReadAuthorization,create_company_read_router
                def trusted_test_provider(request,company_id):
                    return CompanyReadAuthorization('test-subject',7,'companies:read')
                router=create_company_read_router(authorize_company_read=trusted_test_provider)
                assert len(router.routes)==1 and router.routes[0].methods=={'GET'}
                for name in ('app.main','app.core.database','app.core.config','app.api.routes.companies'):
                    assert name not in sys.modules
        '''
        env = {key: os.environ[key] for key in ("SystemRoot", "WINDIR", "PATH", "TEMP", "TMP")
               if key in os.environ}
        env.update(DATABASE_URL="invalid://ambient", PGHOST="ambient.invalid")
        result = subprocess.run([sys.executable, "-B", "-I", "-c", textwrap.dedent(script), str(ROOT / "backend")],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
