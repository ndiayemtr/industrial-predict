"""Offline ASGI, SQL rows and provider doubles; never real OIDC or PostgreSQL."""

import asyncio
import base64
import importlib
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace as NS
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.application_session_store import PostgresApplicationSessionStore, SessionStoreRejected, SessionStoreUnavailable, session_reference
from app.b2b_runtime import B2BRouteRuntime, GoogleSessionLogin, SqlIdentityLookup, install_b2b_runtime, create_route_runtime
from app.core.authorization import AccountState
from app.core.caller_session import SessionRecord, CallerForbidden, CallerUnauthenticated, CallerProviderUnavailable, Reason, Outcome
from app.core.database_runtime import SqlRuntime
from app.core.identity import LocalIdentityLink, VerifiedExternalIdentity
from app.core.oidc_client import GoogleOidcClient, ProfessionalIdentityResult, EmailAssurance, OidcClientUnavailable, OidcClientRejected
from app.core.authorization import VerifiedIdentity
from app.api.routes.p101_analysis import create_p101_analysis_router
from app.api.routes.b2b_login import create_google_login_router, CALLBACK_PATH, BINDING_COOKIE
from app.core.oidc_config import OidcConfig
from app.b2b_runtime import install_google_b2b
import httpx
from p101_dev_sql import test_loader as loader_tests
from p101_integration.test_analysis import InProcessClient


NOW = datetime(2026, 11, 12, 12, tzinfo=timezone.utc)
SECRET = base64.urlsafe_b64encode(b'x' * 32).rstrip(b'=').decode()
HEADERS = {'Authorization': 'Bearer ' + SECRET}


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    loop = asyncio.new_event_loop()
    loader_tests.no_live_database.__wrapped__(monkeypatch)
    yield loop
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.run_until_complete(loop.shutdown_default_executor())
    loop.close()


@pytest.fixture
def case(monkeypatch, offline):
    db = Session(autoflush=False)
    db.connection = Mock()
    engine = NS(echo=False, hide_parameters=True, logger=Mock())
    engine.logger.isEnabledFor.return_value = False
    sql = SqlRuntime(engine, lambda: db)
    store = PostgresApplicationSessionStore(sql, admission_provider=NS(admit=Mock()), clock=lambda: NOW)
    identity = VerifiedIdentity(17, 'https://accounts.google.com', 'offline-subject', AccountState.ACTIVE)
    record = SessionRecord(session_reference(SECRET), identity, NOW-timedelta(minutes=2),
        NOW-timedelta(minutes=2), NOW-timedelta(minutes=1), NOW-timedelta(minutes=2)+timedelta(hours=8))
    state = NS(permissions=['predictions:read', 'maintenance:write', 'predictions:analyze'],
        company=101, scope_company=101, scope_id=303, auth_error=None, calls=[], committed=0, membership_state='active')
    def load(db, reference):
        state.calls.append('session')
        if state.auth_error:
            raise state.auth_error
        if reference != record.reference:
            raise SessionStoreRejected(Reason.SESSION_MISMATCH)
        return {}, record, NOW
    store._load = Mock(side_effect=load)
    member = NS(id=1, company_id=101, state='active', role='company_admin')
    def execute(statement, *args, **kwargs):
        query = str(statement.compile(dialect=postgresql.dialect()))
        result = Mock()
        if 'membership_permissions' in query:
            state.calls.append('permissions')
            result.all.return_value = [NS(permission=p, role='company_admin') for p in state.permissions]
        elif 'company_memberships' in query:
            state.calls.append('memberships')
            member.company_id = state.company
            member.state = state.membership_state
            result.scalars.return_value.all.return_value = [member]
        elif 'equipments' in query:
            state.calls.append('scope')
            params = statement.compile(dialect=postgresql.dialect()).params
            assert [101] in params.values() or [999] in params.values()
            result.one_or_none.return_value = NS(id=state.scope_id, site_id=202, company_id=state.scope_company)
        elif 'sensors' in query:
            state.calls.append('sensor')
            result.scalar_one_or_none.return_value = 404
        else:
            assert query.startswith('SET LOCAL'), query
        return result
    db.execute = Mock(side_effect=execute)
    event.listen(db, 'after_commit', lambda session: setattr(state, 'committed', state.committed + 1))
    runtime = B2BRouteRuntime(sql=sql, sessions=store, clock=lambda: NOW)
    # Import the legacy assembly without configuration or engine creation.
    monkeypatch.setitem(sys.modules, 'app.core.database', NS(get_db=Mock(side_effect=AssertionError('legacy DB forbidden'))))
    monkeypatch.setitem(sys.modules, 'app.core.config', NS(settings=NS(
        app_name='offline-runtime-test', app_version='test', app_env='test')))
    equipment = importlib.import_module('app.api.routes.equipment')
    app = FastAPI()
    app.include_router(equipment.router, prefix='/api/v1')
    app.include_router(create_p101_analysis_router(), prefix='/api/v1')
    app.state.sql_runtime = sql
    install_b2b_runtime(app, runtime=runtime)
    prediction_service = Mock()
    prediction_service.get_paginated.return_value = dict(items=[], total=0, pages=0, page=1, page_size=20)
    recommendation_reads = Mock()
    recommendation_reads.get_paginated.return_value = dict(items=[], total=0, pages=0, page=1, page_size=20)
    recommendation_writes = Mock()
    def recommend(**kwargs):
        state.calls.append('business_write')
        db.commit()
        return dict(equipment_id=303, priority='medium', recommendation_type='monitoring', title='Offline',
                    reason='Offline signal', recommended_action='Review measurements', signals={'anomaly_score': 1})
    recommendation_writes.recommend_from_latest_predictions.side_effect = recommend
    monkeypatch.setattr(equipment, 'PredictionService', Mock(return_value=prediction_service))
    monkeypatch.setattr(equipment, 'MaintenanceRecommendationService', Mock(return_value=recommendation_reads))
    monkeypatch.setattr(equipment, 'RecommendationService', Mock(return_value=recommendation_writes))
    yield NS(app=app, client=InProcessClient(app, offline), runtime=runtime, store=store, sql=sql,
        db=db, state=state, record=record, reads=prediction_service, writes=recommendation_writes,
        recommendation_reads=recommendation_reads)
    db.close()


@pytest.mark.parametrize('method,suffix', [('GET','predictions'), ('GET','recommendations'), ('POST','recommendations'), ('POST','p101-analysis')])
@pytest.mark.parametrize('header', [None, 'Bearer invalid', 'Bearer a.b.c'])
def test_missing_or_invalid_credentials_never_read_sql(case, method, suffix, header):
    headers = {} if header is None else {'Authorization': header}
    body = dict(company_id=101, site_id=202, sensor_id=404, target_measurement_id=11, cutoff_utc=NOW.isoformat())
    response = case.client.request(method, '/api/v1/equipments/303/'+suffix, headers=headers,
                                   **({'json': body} if suffix=='p101-analysis' else {}))
    assert response.status_code == 401
    assert case.state.calls == []
    case.db.connection.assert_not_called()


@pytest.mark.parametrize('reason', [Reason.SESSION_MISMATCH, Reason.IDLE_EXPIRED, Reason.ABSOLUTE_EXPIRED, Reason.REVOKED])
def test_session_invalid_or_expired_refuses_before_scope(case, reason):
    case.state.auth_error = SessionStoreRejected(reason)
    assert case.client.request('GET', '/api/v1/equipments/303/predictions', headers=HEADERS).status_code == 401
    assert case.state.calls == ['session']
    case.reads.get_paginated.assert_not_called()


@pytest.mark.parametrize('method,suffix', [('GET','predictions'), ('GET','recommendations'), ('POST','recommendations')])
def test_explicit_grants_allow_existing_routes(case, method, suffix):
    response = case.client.request(method, '/api/v1/equipments/303/'+suffix, headers=HEADERS)
    assert response.status_code == (201 if method=='POST' else 200), response.text
    assert case.state.calls.index('permissions') < case.state.calls.index('scope')
    assert case.state.committed == (1 if method=='POST' else 0)


@pytest.mark.parametrize('fault', ['permission', 'inactive_membership', 'foreign_company', 'wrong_equipment'])
def test_no_unauthorized_business_read_or_write(case, fault):
    if fault == 'permission':
        case.state.permissions = []
    elif fault == 'inactive_membership':
        case.state.membership_state = 'inactive'
        case.state.permissions = []
    elif fault == 'foreign_company':
        case.state.company = 999
    else:
        case.state.scope_id = 999
    response = case.client.request('POST', '/api/v1/equipments/303/recommendations', headers=HEADERS)
    assert response.status_code == 403, response.text
    case.writes.recommend_from_latest_predictions.assert_not_called()
    assert case.state.committed == 0


def test_post_requires_write_permission_not_only_read(case):
    case.state.permissions = ['predictions:read']
    assert case.client.request('POST', '/api/v1/equipments/303/recommendations', headers=HEADERS).status_code == 403
    assert 'scope' not in case.state.calls


def test_permission_rechecked_at_commit_without_implicit_grant(case):
    def revoked_before_commit(**kwargs):
        case.state.permissions = []
        case.db.commit()
        pytest.fail('commit must be denied')
    case.writes.recommend_from_latest_predictions.side_effect = revoked_before_commit
    response = case.client.request('POST', '/api/v1/equipments/303/recommendations', headers=HEADERS)
    assert response.status_code == 403, response.text
    assert case.state.committed == 0
    assert case.state.calls.count('permissions') == 2


def test_missing_runtime_is_503_for_canonical_session_but_401_without(case):
    del case.app.state.b2b_runtime
    assert case.client.request('GET', '/api/v1/equipments/303/predictions', headers=HEADERS).status_code == 503
    assert case.client.request('GET', '/api/v1/equipments/303/predictions').status_code == 401
    case.store._load.assert_not_called()


def test_unavailable_authority_never_falls_back(case):
    case.state.auth_error = SessionStoreUnavailable()
    assert case.client.request('GET', '/api/v1/equipments/303/recommendations', headers=HEADERS).status_code == 503
    assert 'scope' not in case.state.calls


def test_p101_authentication_does_not_supply_provenance(case):
    body = dict(company_id=101, site_id=202, sensor_id=404, target_measurement_id=11, cutoff_utc=NOW.isoformat())
    response = case.client.post('/api/v1/equipments/303/p101-analysis', json=body, headers=HEADERS)
    assert response.status_code == 503
    assert case.state.calls[-1] == 'sensor'
    assert case.state.committed == 0
    response = case.client.post('/api/v1/equipments/303/p101-analysis', json=body | {'company_id': 999}, headers=HEADERS)
    assert response.status_code == 403


@pytest.mark.parametrize('suffix', ['health-score', 'rul'])
def test_other_generators_remain_closed(case, suffix):
    assert case.client.post('/api/v1/equipments/303/'+suffix, headers=HEADERS, json={}).status_code == 503
    assert case.state.calls == []


def test_grant_queries_take_share_locks_and_reload_each_request(case):
    case.client.request('GET', '/api/v1/equipments/303/predictions', headers=HEADERS)
    sql = [str(call.args[0].compile(dialect=postgresql.dialect())) for call in case.db.execute.call_args_list]
    assert any('company_memberships' in query and 'FOR SHARE' in query for query in sql)
    assert any('membership_permissions' in query and 'FOR SHARE' in query for query in sql)
    case.state.permissions = []
    assert case.client.request('GET', '/api/v1/equipments/303/predictions', headers=HEADERS).status_code == 403
    assert case.reads.get_paginated.call_count == 1


@pytest.mark.parametrize('error,expected', [(OidcClientRejected(), CallerUnauthenticated), (OidcClientUnavailable(), CallerProviderUnavailable)])
def test_oidc_failure_never_issues_session(case, monkeypatch, error, expected):
    client = object.__new__(GoogleOidcClient)
    client.complete_callback = Mock(side_effect=error)
    create = Mock()
    monkeypatch.setattr(PostgresApplicationSessionStore, 'create', create)
    login = GoogleSessionLogin(client=client, runtime=case.sql)
    with pytest.raises(expected):
        login.complete_callback(state='offline', browser_binding='offline', code='offline', client_secret='offline')
    create.assert_not_called()


@pytest.mark.parametrize('professional', [True, False])
def test_verified_oidc_to_existing_local_link_without_company_grants(case, monkeypatch, professional):
    client = object.__new__(GoogleOidcClient)
    external = VerifiedExternalIdentity('https://accounts.google.com', 'offline-subject')
    result = ProfessionalIdentityResult(external, 'test@factory.example',
        EmailAssurance.GOOGLE_WORKSPACE if professional else EmailAssurance.INDEPENDENT_VERIFICATION_REQUIRED)
    client.complete_callback = Mock(return_value=result)  # Provider double, not a real authentication.
    monkeypatch.setattr(SqlIdentityLookup, 'find_by_external_identity', lambda self, **kwargs:
        (LocalIdentityLink(external.issuer, external.subject, 17, AccountState.ACTIVE),))
    admissions = []
    def create(store):
        admissions.append(store._admission.admit())
        return 'offline-confirmed-issuance-double'
    monkeypatch.setattr(PostgresApplicationSessionStore, 'create', create)
    login = GoogleSessionLogin(client=client, runtime=case.sql)
    if professional:
        assert login.complete_callback(state='offline', browser_binding='offline', code='offline', client_secret='offline')
        assert admissions[0].outcome is Outcome.READY
        assert admissions[0].identity.user_id == 17
    else:
        with pytest.raises(CallerForbidden):
            login.complete_callback(state='offline', browser_binding='offline', code='offline', client_secret='offline')
        assert admissions == []


def test_inactive_membership_disables_retained_grants(case):
    case.state.membership_state = 'inactive'
    assert case.client.request('GET', '/api/v1/equipments/303/predictions', headers=HEADERS).status_code == 403
    assert 'scope' not in case.state.calls


def test_validation_runtime_cannot_create_a_session(case):
    runtime = create_route_runtime(sql=case.sql, clock=lambda: NOW)
    with pytest.raises(SessionStoreUnavailable):
        runtime.sessions._admission.admit()


def test_login_router_secure_binding_and_transient_bearer_delivery(case):
    client = object.__new__(GoogleOidcClient)
    client._config = NS(callback_url='https://login.test'+CALLBACK_PATH, transaction_ttl_seconds=300)
    login = GoogleSessionLogin(client=client, runtime=case.sql)
    login.begin = Mock(return_value=(NS(browser_binding='offline-binding'), 'https://accounts.google.com/offline-only'))
    login.complete_callback = Mock(return_value=NS(secret=SECRET, record=case.record))
    app = FastAPI()
    app.include_router(create_google_login_router(login=login, client_secret_loader=lambda: 'offline-secret-double'))
    http = InProcessClient(app, case.client.loop)
    response = http.request('GET', 'https://login.test/auth/oidc/google/start')
    assert response.status_code == 302
    assert all(value in response.headers['set-cookie'] for value in ('Secure', 'HttpOnly', 'SameSite=lax'))
    response = http.request('GET', 'https://login.test'+CALLBACK_PATH+'?state=offline&code=offline')
    assert response.status_code == 401
    login.complete_callback.assert_not_called()
    response = http.request('GET', 'https://login.test'+CALLBACK_PATH+'?state=offline&code=offline',
                            headers={'Cookie': BINDING_COOKIE+'=offline-binding'})
    assert response.status_code == 200
    assert response.json()['session_token'] == SECRET and response.headers['cache-control'] == 'no-store'
    assert 'Max-Age=0' in response.headers['set-cookie']
    login.complete_callback.assert_called_once()
    # Wrong host/scheme and duplicate state cannot consume an OIDC transaction.
    response = http.request('GET', 'http://login.test'+CALLBACK_PATH+'?state=offline&code=offline')
    assert response.status_code == 503
    response = http.request('GET', 'https://login.test'+CALLBACK_PATH+'?state=a&state=b&code=offline',
                            headers={'Cookie': BINDING_COOKIE+'=offline-binding'})
    assert response.status_code == 401 and login.complete_callback.call_count == 1


def test_oidc_http_closed_without_configuration(case):
    app = FastAPI()
    app.include_router(create_google_login_router())
    http = InProcessClient(app, case.client.loop)
    assert http.request('GET', '/auth/oidc/google/start').status_code == 503
    assert http.request('GET', CALLBACK_PATH+'?state=offline&code=offline').status_code == 503
    assert case.state.calls == []


def test_google_installation_reuses_sql_and_pins_transport_without_io(case, monkeypatch):
    app = FastAPI()
    app.state.sql_runtime = case.sql
    transport = Mock(spec=httpx.BaseTransport)
    factory = Mock(return_value=transport)
    monkeypatch.setattr(httpx, 'HTTPTransport', factory)
    config = OidcConfig(issuer='https://accounts.google.com', client_id='offline-client',
        callback_url='https://login.test'+CALLBACK_PATH, signature_algorithms=('RS256',),
        deployment_mode='production', transaction_ttl_seconds=300, clock_skew_seconds=0,
        max_id_token_age_seconds=300)
    runtime = install_google_b2b(app, sql=case.sql, config=config,
        approved_domains=('factory.example',), client_secret_loader=lambda: 'offline-secret', clock=lambda: NOW)
    assert app.state.b2b_runtime is runtime and runtime.sql is case.sql
    assert runtime.analysis is None
    assert InProcessClient(app, case.client.loop).request('GET', '/auth/oidc/google/start').status_code == 503
    factory.assert_called_once_with(verify=True, retries=0, trust_env=False)
    case.db.connection.assert_not_called()
    assert case.state.calls == []
    async def lifecycle():
        async with app.router.lifespan_context(app):
            transport.close.assert_not_called()
    case.client.loop.run_until_complete(lifecycle())
    transport.close.assert_called_once()


def test_verified_professional_domain_does_not_create_local_identity(case, monkeypatch):
    client = object.__new__(GoogleOidcClient)
    client.complete_callback = Mock(return_value=ProfessionalIdentityResult(
        VerifiedExternalIdentity('https://accounts.google.com', 'unlinked'),
        'member@factory.example', EmailAssurance.GOOGLE_WORKSPACE))
    monkeypatch.setattr(SqlIdentityLookup, 'find_by_external_identity', lambda self, **kwargs: ())
    def create(store):
        admission = store._admission.admit()
        assert admission.outcome is Outcome.FORBIDDEN
        raise SessionStoreRejected(admission.reason)
    monkeypatch.setattr(PostgresApplicationSessionStore, 'create', create)
    login = GoogleSessionLogin(client=client, runtime=case.sql)
    with pytest.raises(CallerForbidden):
        login.complete_callback(state='offline', browser_binding='offline', code='offline', client_secret='offline')
