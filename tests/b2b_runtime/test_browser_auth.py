"""API/browser bridge on ASGI + existing transactional store double only.

No real Google success, PostgreSQL, Docker, provisioning or runtime activation.
"""
import asyncio
from datetime import timedelta
import json
from pathlib import Path
import re
import shutil
import subprocess
from types import SimpleNamespace as NS
from unittest.mock import Mock

from fastapi import FastAPI
import httpx
import pytest

from app import b2b_runtime as binding
from app.api.routes.b2b_login import BINDING_COOKIE, CALLBACK_PATH, popup_response
from app.application_session_store import SessionStoreRejected
from app.core.authorization import AccountState, VerifiedIdentity
from app.core.b2b_browser import BrowserAuthProfile, BROWSER_BRIDGE
from app.core.caller_session import AdmissionDecision, Outcome, Reason, CallerProviderUnavailable
from app.core.identity import LocalIdentityLink, VerifiedExternalIdentity
from app.core.oidc_client import GoogleOidcClient, ProfessionalIdentityResult, EmailAssurance
from app.core.oidc_config import OidcConfig
from core.test_application_session_store import Harness, SimulatedSession
from p101_dev_sql import test_loader as loader_tests
from p101_integration.test_analysis import InProcessClient

ORIGIN = 'https://login.test'
PRIVATE = 'synthetic-private-auth-diagnostic'
REAL_RUN = subprocess.run


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    loop = asyncio.new_event_loop()  # Windows private wakeup pair before bans.
    loader_tests.no_live_database.__wrapped__(monkeypatch)
    monkeypatch.setattr(subprocess, 'run', Mock(side_effect=AssertionError('Process forbidden')))
    try:
        yield loop
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.run_until_complete(loop.shutdown_default_executor())
        loop.close()


@pytest.fixture
def case(monkeypatch, offline):
    h = Harness()
    identity = VerifiedIdentity(17, 'https://accounts.google.com', 'synthetic-subject', AccountState.ACTIVE)
    h.external[0]['issuer'] = identity.issuer
    h.admission.admit.return_value = AdmissionDecision(Outcome.READY, Reason.VALID, identity)
    h.memberships = [dict(id=51, user_id=17, company_id=101, state='active', role='company_admin')]
    h.permissions = [dict(membership_id=51, role='company_admin', permission=p)
                     for p in ('predictions:read', 'predictions:analyze', 'maintenance:write')]
    def factory():
        db = SimulatedSession(h)
        db.autoflush = False
        db.new = db.dirty = db.deleted = ()
        db.in_transaction = lambda: False
        return db
    h.runtime._factory = factory
    issued = h.store().create()
    h.events.clear()
    state = NS(provider=None, guard=Mock(return_value=None), h=h)
    external = VerifiedExternalIdentity(identity.issuer, identity.subject)
    def initialize(client, *, config, **kwargs):
        client._config = config
        client._transactions = NS(create=Mock(return_value=NS(browser_binding='synthetic-binding')))
        client.authorization_url = Mock(return_value='https://accounts.google.com/synthetic-only')
        # Deliberate test provider double. Real claims/PKCE/state use selected
        # existing tests; no production fake provider is installed.
        client.complete_callback = Mock(return_value=ProfessionalIdentityResult(
            external, 'unit@factory.example', EmailAssurance.GOOGLE_WORKSPACE))
        state.provider = client
    monkeypatch.setattr(GoogleOidcClient, '__init__', initialize)
    lookup = Mock(return_value=(LocalIdentityLink(identity.issuer, identity.subject, 17, AccountState.ACTIVE),))
    monkeypatch.setattr(binding.SqlIdentityLookup, 'find_by_external_identity', lookup)
    transport = Mock(spec=httpx.BaseTransport)
    monkeypatch.setattr(httpx, 'HTTPTransport', Mock(return_value=transport))
    app = FastAPI()
    app.state.sql_runtime = h.runtime
    cfg = OidcConfig(issuer='https://accounts.google.com', client_id='synthetic-client',
        callback_url=ORIGIN + CALLBACK_PATH, signature_algorithms=('RS256',),
        deployment_mode='production', transaction_ttl_seconds=300, clock_skew_seconds=0, max_id_token_age_seconds=300)
    profile = BrowserAuthProfile(ORIGIN, state.guard)
    runtime = binding.install_google_b2b(app, sql=h.runtime, config=cfg, approved_domains=('factory.example',),
        client_secret_loader=lambda: 'synthetic-client-secret', clock=lambda: h.now, browser_profile=profile)
    http = InProcessClient(app, offline)
    headers = {'Authorization': 'Bearer ' + issued.secret, 'Origin': ORIGIN, 'Sec-Fetch-Site': 'same-origin'}
    return NS(h=h, app=app, state=state, runtime=runtime, profile=profile, cfg=cfg, client=http,
              issued=issued, headers=headers, lookup=lookup, transport=transport)


def request(case, method='GET', path='/api/v1/auth/me', headers=None, **kwargs):
    return case.client.request(method, ORIGIN + path, headers=case.headers if headers is None else headers, **kwargs)


def callback(case, query='state=synthetic-state&code=synthetic-code', cookie='synthetic-binding'):
    return request(case, path=CALLBACK_PATH + '?' + query,
                   headers={'Cookie': BINDING_COOKIE + '=' + cookie})


def payload(response):
    return json.loads(re.search(r'let payload = (.*);', response.text).group(1))


def test_profile_matches_angular_and_contains_only_explicit_authorized_companies(case):
    response = request(case)
    assert response.status_code == 200, response.text
    assert response.json() == {'userId': 17, 'displayName': None, 'companies': [
        {'companyId': 101, 'displayName': None, 'permissions': ['maintenance:write', 'predictions:analyze', 'predictions:read']}]}
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['pragma'] == 'no-cache'
    assert 'set-cookie' not in response.headers
    assert case.issued.secret not in response.text and case.issued.record.reference.digest not in response.text
    assert 'issuer' not in response.text and 'subject' not in response.text
    assert 'commit' not in case.h.events and 'update' not in case.h.events
    # Read again after permission removal; no cached tenant/role inference.
    case.h.permissions.clear()
    assert request(case).status_code == 403


@pytest.mark.parametrize('header', [None, 'Bearer invalid', 'Bearer header.payload.signature'])
def test_missing_cookie_only_or_invalid_bearer_refused_without_store_access(case, header):
    headers = {'Cookie': 'session=' + case.issued.secret}
    if header:
        headers['Authorization'] = header
    case.state.guard.reset_mock()
    response = request(case, headers=headers)
    assert response.status_code == 401 and response.headers['www-authenticate'] == 'Bearer'
    assert case.h.events == []
    case.state.guard.assert_not_called()


def test_ambiguous_authorization_rejected(case):
    response = request(case, headers=[('Authorization', case.headers['Authorization'])] * 2)
    assert response.status_code == 401
    assert case.h.events == []


@pytest.mark.parametrize('fault', ['idle', 'absolute', 'revoked'])
def test_expired_or_revoked_session_refused(case, fault):
    row = case.h.rows[case.issued.record.reference.digest]
    if fault == 'revoked':
        row['revoked_at'] = case.h.now
    elif fault == 'idle':
        case.h.now = case.h.server_now = case.h.now + timedelta(minutes=31)
    else:
        case.h.now = case.h.server_now = case.h.now + timedelta(hours=9)
    response = request(case)
    assert response.status_code == 401
    assert case.issued.secret not in response.text


@pytest.mark.parametrize('fault', ['inactive', 'absent', 'no_grants'])
def test_no_active_authorized_membership_returns_403(case, fault):
    if fault == 'inactive':
        case.h.memberships[0]['state'] = 'inactive'
    elif fault == 'absent':
        case.h.memberships.clear()
    else:
        case.h.permissions.clear()
    assert request(case).status_code == 403


def test_inactive_company_never_leaks_into_other_company_scope(case):
    case.h.memberships.append(dict(id=52, user_id=17, company_id=202, state='inactive', role='company_admin'))
    case.h.permissions.append(dict(membership_id=52, role='company_admin', permission='predictions:read'))
    assert [c['companyId'] for c in request(case).json()['companies']] == [101]


def test_suspended_account_is_forbidden(case):
    case.h.users[0]['state'] = 'suspended'
    assert request(case).status_code == 403


def test_logout_commits_revocation_of_this_bearer_only(case):
    second = case.h.store().create()
    case.h.events.clear()
    # A body cannot select another user's/session's target.
    response = request(case, 'POST', '/api/v1/auth/logout', json={'user_id': 18, 'session_token': second.secret})
    assert response.status_code == 204 and response.content == b''
    assert response.headers['cache-control'] == 'no-store'
    assert case.h.rows[case.issued.record.reference.digest]['revoked_at'] == case.h.now
    assert case.h.rows[second.record.reference.digest]['revoked_at'] is None
    assert case.h.events.count('commit') == 1 and case.h.events.count('update') == 1
    assert request(case).status_code == 401
    assert request(case, 'POST', '/api/v1/auth/logout').status_code == 401


def test_removed_company_access_does_not_prevent_own_logout(case):
    case.h.memberships[0]['state'] = 'inactive'
    assert request(case).status_code == 403
    assert request(case, 'POST', '/api/v1/auth/logout').status_code == 204


@pytest.mark.parametrize('mode', ['commit_before', 'commit_after'])
def test_logout_uncertain_commit_never_claims_success_or_retries(case, mode):
    case.h.failure = mode
    response = request(case, 'POST', '/api/v1/auth/logout')
    assert response.status_code == 503
    assert case.h.events.count('commit') == 1
    assert case.issued.secret not in response.text and PRIVATE not in response.text


@pytest.mark.parametrize('headers', [
    {'Origin': 'https://foreign.test'}, {'Sec-Fetch-Site': 'cross-site'},
    {'Sec-Fetch-Site': 'same-site'},
])
def test_cross_origin_auth_requests_rejected_before_session_queries(case, headers):
    response = request(case, headers={**case.headers, **headers})
    assert response.status_code == 403 and case.h.events == []


def test_logout_requires_exact_origin_and_rejects_query_credentials(case):
    assert request(case, 'POST', '/api/v1/auth/logout', headers={'Authorization': case.headers['Authorization']}).status_code == 403
    assert request(case, path='/api/v1/auth/me?session_token=not-a-credential').status_code == 403
    assert case.h.events == []


def test_wrong_https_host_and_unqualified_runtime_fail_closed(case):
    for origin in ('http://login.test', 'https://other.test'):
        response = case.client.request('GET', origin + '/api/v1/auth/me', headers=case.headers)
        assert response.status_code == 503
    case.state.guard.side_effect = RuntimeError(PRIVATE)
    response = request(case)
    assert response.status_code == 503 and PRIVATE not in response.text
    assert case.h.events == []


def test_runtime_unbound_or_sql_unavailable_is_503(case):
    del case.app.state.b2b_auth_runtime
    assert request(case).status_code == 503
    case.app.state.b2b_auth_runtime = case.runtime
    case.h.failure = 'execute'
    assert request(case).status_code == 503


def test_popup_success_is_nonce_protected_exact_origin_delivery_after_commit(case):
    before = len(case.h.rows)
    response = callback(case)
    assert response.status_code == 200, response.text
    data = payload(response)
    assert set(data) == {'kind', 'token_type', 'session_token', 'absolute_expires_at'}
    assert data['kind'] == BROWSER_BRIDGE and data['token_type'] == 'Bearer'
    assert len(case.h.rows) == before + 1 and case.h.events.count('commit') == 1
    assert 'session_token' not in str(response.url) and 'location' not in response.headers
    assert 'synthetic-code' not in response.text and 'synthetic-state' not in response.text
    assert 'synthetic-client-secret' not in response.text and 'synthetic-binding' not in response.text
    nonce = re.search(r'<script nonce="([A-Za-z0-9_-]+)"', response.text).group(1)
    assert "script-src 'nonce-" + nonce + "'" in response.headers['content-security-policy']
    assert 'unsafe-inline' not in response.headers['content-security-policy']
    assert "frame-ancestors 'none'" in response.headers['content-security-policy']
    assert 'target.location.origin !== targetOrigin' in response.text
    assert 'target.postMessage(payload, targetOrigin)' in response.text
    assert response.headers['referrer-policy'] == 'no-referrer'
    assert response.headers['cache-control'] == 'no-store'
    assert 'Max-Age=0' in response.headers['set-cookie']
    case.lookup.assert_called_once_with(issuer='https://accounts.google.com', subject='synthetic-subject')


@pytest.mark.parametrize('query', ['state=a&state=b&code=c', 'state=a&code=b&code=c', 'state=a',
                                  'code=a', 'state=a&code=c&error=access_denied'])
def test_refused_callback_never_exchanges_or_emits_session(case, query):
    response = callback(case, query)
    assert response.status_code == 401
    assert payload(response) == {'kind': BROWSER_BRIDGE, 'error': 'denied'}
    assert 'session_token' not in response.text and case.h.events == []
    case.state.provider.complete_callback.assert_not_called()


def test_duplicate_or_absent_binding_cookie_rejected(case):
    response = request(case, path=CALLBACK_PATH + '?state=a&code=b', headers={})
    assert response.status_code == 401
    headers = {'Cookie': BINDING_COOKIE + '=one; ' + BINDING_COOKIE + '=two'}
    assert request(case, path=CALLBACK_PATH + '?state=a&code=b', headers=headers).status_code == 401
    case.state.provider.complete_callback.assert_not_called()


@pytest.mark.parametrize('fault', ['unprovisioned', 'inactive', 'no_grants'])
def test_callback_requires_provisioned_identity_and_explicit_active_company_before_commit(case, fault):
    before = dict(case.h.rows)
    if fault == 'unprovisioned':
        case.lookup.return_value = ()
    elif fault == 'inactive':
        case.h.memberships[0]['state'] = 'inactive'
    else:
        case.h.permissions.clear()
    response = callback(case)
    assert response.status_code == 403
    assert payload(response)['error'] == 'denied' and 'session_token' not in response.text
    assert case.h.rows == before
    assert 'commit' not in case.h.events and 'rollback' in case.h.events


@pytest.mark.parametrize('fault', ['commit_before', 'commit_after'])
def test_callback_commit_uncertainty_does_not_deliver_secret(case, fault):
    case.h.failure = fault
    response = callback(case)
    assert response.status_code == 503
    assert payload(response) == {'kind': BROWSER_BRIDGE, 'error': 'unavailable'}
    assert case.h.events.count('commit') == 1
    case.state.provider.complete_callback.assert_called_once()


def test_start_keeps_existing_google_route_and_host_cookie_contract(case):
    response = request(case, path='/auth/oidc/google/start', headers={})
    assert response.status_code == 302
    assert response.headers['location'] == 'https://accounts.google.com/synthetic-only'
    assert all(part in response.headers['set-cookie'] for part in ('__Host-', 'Secure', 'HttpOnly', 'SameSite=lax', 'Path=/'))
    assert case.h.events == []


@pytest.mark.parametrize('origin', ['http://login.test', 'https://foreign.test', 'https://login.test/',
                                  'https://login.test:443', 'https://user:secret@login.test', 'https://*.test'])
def test_browser_profile_rejects_noncanonical_or_mismatched_origins(case, origin):
    if origin == 'https://foreign.test':
        profile = BrowserAuthProfile(origin, case.state.guard)
        with pytest.raises(CallerProviderUnavailable):
            app = FastAPI(); app.state.sql_runtime = case.h.runtime
            binding.install_google_b2b(app, sql=case.h.runtime, config=case.cfg, approved_domains=('factory.example',),
                client_secret_loader=lambda: 'synthetic', browser_profile=profile)
    else:
        with pytest.raises(ValueError):
            BrowserAuthProfile(origin, case.state.guard)


def test_profile_guard_and_auth_only_surface_cannot_be_implicitly_enabled(case):
    app = FastAPI()
    http = InProcessClient(app, case.client.loop)
    assert http.request('GET', ORIGIN + '/api/v1/auth/me').status_code == 404
    assert http.request('POST', ORIGIN + '/api/v1/auth/logout').status_code == 404
    assert getattr(case.app.state, 'b2b_runtime', None) is None
    for path in ('/api/v1/companies', '/api/v1/equipments/303/predictions', '/api/v1/equipments/303/recommendations'):
        assert request(case, path=path).status_code == 404
    invoked = Mock(return_value={'unsafe': True})
    case.app.add_api_route('/api/v1/unsafe-late-crud', invoked, methods=['GET'])
    assert request(case, path='/api/v1/unsafe-late-crud').status_code == 404
    invoked.assert_not_called()


def test_browser_assembly_refuses_a_legacy_business_application(case):
    app = FastAPI(); app.state.sql_runtime = case.h.runtime
    app.add_api_route('/api/v1/companies', lambda: [])
    case.state.guard.reset_mock()
    with pytest.raises(CallerProviderUnavailable):
        binding.install_google_b2b(app, sql=case.h.runtime, config=case.cfg, approved_domains=('factory.example',),
            client_secret_loader=lambda: 'synthetic', browser_profile=case.profile)
    case.state.guard.assert_not_called()


def test_popup_javascript_executes_only_for_exact_same_origin_opener(case):
    response = callback(case)
    script = re.search(r'<script nonce="[^"]+">(.*?)</script>', response.text, re.S).group(1)
    node = shutil.which('node')
    assert node, 'Installed Node required for isolated browser-script evaluation'
    javascript = r"""
const vm=require('node:vm'),fs=require('node:fs');
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const results=[];
for(const mode of ['same','foreign','absent','closed','cross-origin-getter']) {
  const messages=[],urls=[];
  let opener=mode==='absent'?null:{closed:mode==='closed',location:{origin:mode==='foreign'?'https://other.test':input.origin},postMessage:(data,origin)=>messages.push({data,origin})};
  if(mode==='cross-origin-getter') Object.defineProperty(opener,'location',{get(){throw new Error('SOP');}});
  const window={location:{origin:input.origin},opener,history:{replaceState:(_,__,url)=>urls.push(url)},close(){}};
  vm.runInNewContext(input.script,{window},{timeout:1000});
  results.push({mode,count:messages.length,origin:messages[0]?.origin,kind:messages[0]?.data.kind,urls});
}
process.stdout.write(JSON.stringify(results));
"""
    result = REAL_RUN([node, '-e', javascript], input=json.dumps({'script': script, 'origin': ORIGIN}).encode(),
                      capture_output=True, timeout=10, check=True)
    values = json.loads(result.stdout)
    assert values[0]['count'] == 1 and values[0]['origin'] == ORIGIN and values[0]['kind'] == BROWSER_BRIDGE
    assert all(v['count'] == 0 for v in values[1:])
    assert all(v['urls'] == [CALLBACK_PATH] for v in values)


def test_popup_json_cannot_break_out_of_its_script():
    response = popup_response({'kind': BROWSER_BRIDGE, 'error': '</script><script>bad()</script>'}, origin=ORIGIN)
    body = response.body.decode()
    assert body.count('</script>') == 1 and '\\u003c/script' in body


def test_safe_popup_render_failure_never_falls_back_to_json_secret(case, monkeypatch):
    import app.api.routes.b2b_login as route
    monkeypatch.setattr(route.secrets, 'token_urlsafe', Mock(side_effect=RuntimeError(PRIVATE)))
    response = callback(case)
    assert response.status_code == 503 and response.json() == {'detail': 'OIDC_RUNTIME_UNAVAILABLE'}
    assert 'session_token' not in response.text and PRIVATE not in response.text
    assert response.headers['cache-control'] == 'no-store'


@pytest.mark.parametrize('result', [True, False])
def test_qualification_guard_boolean_is_not_authorization(case, result):
    case.state.guard.return_value = result
    assert request(case).status_code == 503
    assert case.h.events == []


def test_browser_transport_lifespan_closes_and_reuses_qualified_sql(case):
    assert case.runtime.sql is case.h.runtime
    async def lifecycle():
        async with case.app.router.lifespan_context(case.app):
            case.transport.close.assert_not_called()
    case.client.loop.run_until_complete(lifecycle())
    case.transport.close.assert_called_once()
