"""In-process HTTP and synthetic SQL/provider doubles only; no real qualification."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
import sys
import asyncio

import pytest
from fastapi import FastAPI
import httpx

from app.api.routes.p101_analysis import create_p101_analysis_router
from app.core.caller_session import CallerUnauthenticated, CurrentCaller
from app.p101_dev.contracts import DeclaredProvenance, EvidenceReference
from app.schemas.p101_analysis import AnalysisRequest
from app.services import p101_analysis as module
from app.services.p101_dev_orchestration import P101DevOrchestrator
from p101_dev_sql.test_loader import db
from p101_dev_sql import test_loader as loader_tests
from p101_dev_orchestration.test_orchestration import PortDouble


class InProcessClient:
    def __init__(self, app, loop):
        self.app, self.loop = app, loop

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def request(self, method, path, **kwargs):
        async def send():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),
                                         base_url='http://offline.test') as client:
                return await client.request(method, path, **kwargs)
        return self.loop.run_until_complete(send())

    def post(self, path, **kwargs):
        return self.request('POST', path, **kwargs)


@pytest.fixture(autouse=True)
def no_live_database(monkeypatch):
    # Allocate Windows' private loop wakeup pair before installing network bans.
    # All HTTP below is in-process ASGI; no server or application socket is used.
    loop = asyncio.new_event_loop()
    loader_tests.no_live_database.__wrapped__(monkeypatch)
    monkeypatch.setattr(sys.modules[__name__], 'TestClient', lambda app: InProcessClient(app, loop), raising=False)
    try:
        yield
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()


@pytest.fixture
def case(db):
    db.proofs = [dict(isolation='repeatable read', read_only='on')] * 3
    port = PortDouble(db)
    now = db.arguments['observed_at']
    provider = SimpleNamespace(current_caller=lambda reference, now: CurrentCaller(reference, port.identity, (port.member,), now))
    verifier = Mock(return_value=DeclaredProvenance('offline-double', 'test-only', False,
        (EvidenceReference('source_manifest', 'offline-test', 'a' * 64),)))
    connection_context = Mock(side_effect=AssertionError('No real runtime'))
    service = module.P101AnalysisService(caller_provider=provider, connection_context=connection_context,
        provenance_verifier=verifier, clock=lambda: now)
    service._read = port.read  # Explicit test-only transaction double.
    request = AnalysisRequest(company_id=101, site_id=202, sensor_id=404,
        target_measurement_id=11, cutoff_utc=db.arguments['event_cutoff'])
    app = FastAPI()
    app.include_router(create_p101_analysis_router(service=service, session_resolver=lambda request: port.reference), prefix='/api/v1')
    return SimpleNamespace(db=db, port=port, provider=provider, verifier=verifier,
                           service=service, request=request, app=app)


def post(case):
    with TestClient(case.app) as client:
        return client.post('/api/v1/equipments/303/p101-analysis', json=case.request.model_dump(mode='json'))


def no_writes(case):
    for name in ('add', 'add_all', 'delete', 'flush', 'commit'):
        getattr(case.db.session, name).assert_not_called()
    case.db.connection.commit.assert_not_called()
    assert not case.port.rows and 'write_enter' not in case.port.events


def test_computed_real_evaluator_mapping_without_persistence_plan(case):
    response = post(case)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['status'] == 'COMPUTED' and result['score'] == 1
    assert result['statistics']['mean'] == 65 and result['statistics']['sample_std'] == 1
    assert result['persisted'] is False and result['synthetic'] is False
    assert result['reference_ids'] == list(range(1, 11))
    assert 'prediction_id' not in result and 'failure_probability' not in result
    assert case.db.connection.get_transaction().is_active is False
    no_writes(case)


def test_orchestrator_analysis_retains_no_persistence_capability(case):
    orchestrator = P101DevOrchestrator(port=case.port, clock=lambda: case.db.arguments['observed_at'])
    result = orchestrator.analyze(reference=case.port.reference,
        **{key: value for key, value in case.db.arguments.items() if key not in ('authorization', 'observed_at')},
        company_id=101)
    assert result.prepared is None and orchestrator._pending == {}
    no_writes(case)


@pytest.mark.parametrize('fault', ['missing', 'expired', 'permission', 'revoked', 'other_company'])
def test_authentication_authorization_before_business_reads(case, fault):
    if fault in ('missing', 'expired'):
        case.provider.current_caller = Mock(side_effect=CallerUnauthenticated())
        expected = 401
    else:
        if fault in ('permission', 'revoked'):
            case.port.member = replace(case.port.member, permissions=frozenset())
        else:
            case.port.member = replace(case.port.member, company_id=999)
        expected = 403
    response = post(case)
    assert response.status_code == expected
    assert case.db.queries == [] and case.port.events == []
    case.verifier.assert_not_called()
    no_writes(case)


@pytest.mark.parametrize('key', ['site_id', 'equipment_id', 'company_id', 'sensor_equipment_id'])
def test_scope_refused_before_measurement_read(case, key):
    case.db.chain[0][key] = 999
    assert post(case).status_code == 403
    assert all('JOIN public.equipments' in sql for sql, _ in case.db.queries)
    case.verifier.assert_not_called()
    no_writes(case)


@pytest.mark.parametrize('provenance', [None, DeclaredProvenance('demo', 'fixture', True),
                                     DeclaredProvenance('claim', 'unverified', False)])
def test_synthetic_absent_or_unverified_provenance_cannot_calculate(case, provenance):
    case.verifier.return_value = provenance
    assert post(case).status_code == 503
    assert all('JOIN public.equipments' in sql for sql, _ in case.db.queries)
    no_writes(case)


@pytest.mark.parametrize('fault,status', [('history', 'ABSTAINED'), ('invalid', 'REJECTED')])
def test_business_outcomes_are_not_http_authorization_failures(case, fault, status):
    if fault == 'history':
        case.db.refs.pop()
    else:
        case.db.target[0]['value'] = True
    response = post(case)
    assert response.status_code == 200, response.text
    assert response.json()['status'] == status
    assert response.json()['reason']
    no_writes(case)


def test_default_endpoint_closed_and_no_client_identity_or_provenance(case):
    app = FastAPI()
    app.include_router(create_p101_analysis_router())
    with TestClient(app) as client:
        response = client.post('/equipments/303/p101-analysis', json=case.request.model_dump(mode='json'))
        assert response.status_code == 401
        response = client.post('/equipments/303/p101-analysis', json=case.request.model_dump(mode='json') | {'synthetic': False})
        assert response.status_code == 422
    assert case.db.queries == []


def test_missing_resolved_session_is_401_before_service(case):
    app = FastAPI()
    service = Mock()
    app.include_router(create_p101_analysis_router(service=service, session_resolver=lambda request: None))
    with TestClient(app) as client:
        assert client.post('/equipments/303/p101-analysis', json=case.request.model_dump(mode='json')).status_code == 401
    service.analyze.assert_not_called()


def test_revocation_rechecked_inside_snapshot_before_business_reads(case):
    valid = case.provider.current_caller
    calls = []
    def refresh(reference, now):
        calls.append(1)
        if len(calls) > 1:
            raise CallerUnauthenticated()
        return valid(reference, now)
    case.provider.current_caller = refresh
    assert post(case).status_code == 401
    assert case.db.queries == []
    no_writes(case)


def test_no_provider_or_runtime_installed_in_actual_http_assembly(monkeypatch):
    # No engine creation/config loading during import of the historical app.
    db_provider = Mock(side_effect=AssertionError('SQL acquisition before auth'))
    fake_database = SimpleNamespace(get_db=db_provider)
    monkeypatch.setitem(sys.modules, 'app.core.database', fake_database)
    monkeypatch.setitem(sys.modules, 'app.core.config', SimpleNamespace(settings=SimpleNamespace(
        app_name='offline-test', app_version='test', app_env='test')))
    from app.main import app
    with TestClient(app) as client:
        response = client.post('/api/v1/equipments/303/p101-analysis', json=dict(
            company_id=101, site_id=202, sensor_id=404, target_measurement_id=11,
            cutoff_utc='2026-04-11T00:00:00Z'))
        assert response.status_code == 401
        for method, suffix in [('GET','predictions'), ('GET','recommendations'), ('POST','recommendations'),
                               ('POST','health-score'), ('POST','rul')]:
            response = client.request(method, '/api/v1/equipments/303/' + suffix, json={})
            assert response.status_code == (503 if suffix in ('health-score', 'rul') else 401), response.text
    db_provider.assert_not_called()


def test_read_context_verifies_state_and_rolls_back_its_transaction(case, monkeypatch):
    from contextlib import contextmanager
    connection = case.db.connection
    connection.in_transaction.return_value = False
    tx = Mock(is_active=True)
    connection.begin.return_value = tx
    connection.execution_options.return_value = connection
    connection.execute.side_effect = None
    connection.execute.return_value.mappings.return_value.one.return_value = dict(
        isolation='repeatable read', read_only='on', statement_timeout_ms=15000, lock_timeout_ms=5000)
    native = object()
    monkeypatch.setattr(module, '_native_idle', lambda connection: native)
    monkeypatch.setattr(module, '_native_connection', lambda connection: native)
    @contextmanager
    def supplied():
        yield connection
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    session.begin.return_value.__enter__ = Mock()
    session.begin.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(module, 'Session', Mock(return_value=session))
    case.service.connection_context = supplied
    with module.P101AnalysisService._read(case.service):
        connection.exec_driver_sql.assert_called_once_with('SET TRANSACTION READ ONLY')
    tx.rollback.assert_called_once()
    connection.commit.assert_not_called()
    connection.close.assert_not_called()


def test_existing_transaction_is_never_rolled_back_by_adapter(case):
    from contextlib import contextmanager
    @contextmanager
    def supplied():
        yield case.db.connection
    case.service.connection_context = supplied
    with pytest.raises(module.AnalysisUnavailable):
        with module.P101AnalysisService._read(case.service):
            pytest.fail('must not enter')
    case.db.connection.rollback.assert_not_called()
    case.db.connection.begin.assert_not_called()
