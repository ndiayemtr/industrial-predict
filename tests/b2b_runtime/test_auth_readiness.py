"""Only the new local readiness contract, using ASGI and synthetic dependencies.

The existing offline fixture forbids SQL/network/process access. No Google login
or actual identity/TLS/ACL qualification is claimed by these unit doubles.
"""
from types import SimpleNamespace as NS
from unittest.mock import Mock

from fastapi import FastAPI
import pytest

from app import b2b_runtime as binding
from app.core.b2b_browser import BROWSER_BRIDGE
from b2b_runtime.test_browser_auth import case, offline, ORIGIN, PRIVATE
from p101_integration.test_analysis import InProcessClient

PATH = '/api/v1/auth/readiness'


@pytest.fixture
def ready_case(case):
    # Reuse the existing synthetic assembly, with an inspectable secret loader.
    app = FastAPI()
    app.state.sql_runtime = case.h.runtime
    loader = Mock(return_value='synthetic-client-secret')
    runtime = binding.install_google_b2b(app, sql=case.h.runtime, config=case.cfg,
        approved_domains=('factory.example',), client_secret_loader=loader,
        clock=lambda: case.h.now, browser_profile=case.profile)
    case.state.guard.reset_mock()
    return NS(app=app, client=InProcessClient(app, case.client.loop), loader=loader,
              runtime=runtime, original=case)


def get(case, *, origin=ORIGIN, suffix='', headers=None):
    return case.client.request('GET', origin + PATH + suffix, headers=headers or {})


def test_readiness_runs_real_integration_guard_without_bearer_or_authentication(ready_case):
    c = ready_case
    response = get(c)
    assert response.status_code == 200
    assert response.json() == {'status': 'ready', 'profile': 'auth-only', 'bridgeVersion': BROWSER_BRIDGE}
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['pragma'] == 'no-cache'
    assert 'set-cookie' not in response.headers and 'location' not in response.headers
    c.original.state.guard.assert_called_once_with(c.runtime.sql)
    c.loader.assert_called_once_with()
    assert c.original.h.events == []
    c.original.state.provider._transactions.create.assert_not_called()
    c.original.state.provider.complete_callback.assert_not_called()
    c.original.transport.handle_request.assert_not_called()
    for value in (c.original.issued.secret, 'synthetic-client-secret', PRIVATE, 'ui47_app', 'industrial_predict_dev'):
        assert value not in response.text


@pytest.mark.parametrize('cause', ['identity', 'revision', 'tls', 'acl', 'functions'])
def test_failed_qualification_is_generic_503_and_does_not_load_secret(ready_case, cause):
    c = ready_case
    c.original.state.guard.side_effect = RuntimeError(PRIVATE + cause)
    response = get(c)
    assert response.status_code == 503
    assert response.json() == {'detail': 'B2B_RUNTIME_UNAVAILABLE'}
    assert PRIVATE not in response.text and c.original.h.events == []
    c.loader.assert_not_called()


@pytest.mark.parametrize('result', [True, False])
def test_boolean_guard_never_proves_readiness(ready_case, result):
    ready_case.original.state.guard.return_value = result
    assert get(ready_case).status_code == 503
    ready_case.loader.assert_not_called()


@pytest.mark.parametrize('headers,suffix', [
    ({'Origin': 'https://foreign.test'}, ''),
    ({'Sec-Fetch-Site': 'cross-site'}, ''),
    ({'Sec-Fetch-Site': 'same-site'}, ''),
    ({'Authorization': 'Bearer must-not-be-used'}, ''),
    ({}, '?enabled=true'),
    ({}, '?session_token=must-not-be-used'),
])
def test_readiness_rejects_foreign_context_and_query_or_bearer_selectors(ready_case, headers, suffix):
    assert get(ready_case, headers=headers, suffix=suffix).status_code == 403
    ready_case.original.state.guard.assert_not_called()
    ready_case.loader.assert_not_called()


@pytest.mark.parametrize('origin', ['http://login.test', 'https://other.test'])
def test_wrong_https_origin_cannot_obtain_readiness(ready_case, origin):
    assert get(ready_case, origin=origin).status_code == 503
    ready_case.original.state.guard.assert_not_called()


@pytest.mark.parametrize('fault', ['runtime', 'sql', 'business'])
def test_unbound_or_business_runtime_cannot_prove_auth_only_readiness(ready_case, fault):
    if fault == 'runtime':
        ready_case.app.state.b2b_auth_runtime = None
    elif fault == 'sql':
        ready_case.app.state.sql_runtime = object()
    else:
        ready_case.app.state.b2b_runtime = object()
    assert get(ready_case).status_code == 503
    ready_case.original.state.guard.assert_not_called()


@pytest.mark.parametrize('secret', [None, '', True, ' leading-space', 'invalid\nsecret', 'a' * 4097])
def test_unavailable_or_malformed_secret_never_enables_the_button(ready_case, secret):
    ready_case.loader.return_value = secret
    response = get(ready_case)
    assert response.status_code == 503 and 'secret' not in response.text.lower()
    assert ready_case.original.h.events == []


def test_loader_failure_is_redacted_and_not_retried(ready_case):
    ready_case.loader.side_effect = RuntimeError(PRIVATE)
    response = get(ready_case)
    assert response.status_code == 503 and PRIVATE not in response.text
    ready_case.loader.assert_called_once_with()


def test_readiness_is_fresh_and_never_a_cached_boolean(ready_case):
    assert get(ready_case).status_code == 200
    ready_case.original.state.guard.side_effect = RuntimeError(PRIVATE)
    assert get(ready_case).status_code == 503
    assert ready_case.original.state.guard.call_count == 2
    ready_case.loader.assert_called_once_with()


def test_closed_application_has_no_readiness_and_auth_only_never_exposes_crud(ready_case):
    closed = InProcessClient(FastAPI(), ready_case.client.loop)
    assert closed.request('GET', ORIGIN + PATH).status_code == 404
    assert get(ready_case).status_code == 200
    assert getattr(ready_case.app.state, 'b2b_runtime', None) is None
    for path in ('/api/v1/companies', '/api/v1/equipments/303/predictions', '/api/v1/equipments/303/recommendations'):
        assert ready_case.client.request('GET', ORIGIN + path).status_code == 404
    assert ready_case.original.h.events == []
