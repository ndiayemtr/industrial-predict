"""Opt-in Google code flow. No provider, callback secret or cookies by default."""

from urllib.parse import urlsplit
import json
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from app.b2b_runtime import GoogleSessionLogin
from app.core.caller_session import CallerForbidden, CallerUnauthenticated, CallerProviderUnavailable
from app.api.b2b import security_error
from app.core.b2b_browser import BrowserAuthProfile, BROWSER_BRIDGE


CALLBACK_PATH = '/auth/oidc/google/callback'
BINDING_COOKIE = '__Host-industrial-oidc-binding'
HEADERS = {'Cache-Control': 'no-store', 'Pragma': 'no-cache', 'Referrer-Policy': 'no-referrer',
           'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'"}


def popup_response(payload, *, origin, status_code=200):
    """Opaque in-memory delivery, exact target origin and nonce-only inline JS."""
    nonce = secrets.token_urlsafe(24)
    def javascript(value):
        return json.dumps(value, ensure_ascii=True, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    script = f"""(() => {{
  'use strict';
  const targetOrigin = {javascript(origin)};
  let payload = {javascript(payload)};
  try {{
    window.history.replaceState(null, '', '{CALLBACK_PATH}');
    const target = window.opener;
    if (window.location.origin !== targetOrigin || !target || target.closed || target.location.origin !== targetOrigin) return;
    target.postMessage(payload, targetOrigin);
    window.close();
  }} catch (_) {{
    // No diagnostics, URL delivery, storage or fallback recipient.
  }} finally {{ payload = null; }}
}})();"""
    headers = {**HEADERS, 'X-Frame-Options': 'DENY', 'Content-Security-Policy':
        f"default-src 'none'; script-src 'nonce-{nonce}'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; object-src 'none'; connect-src 'none'"}
    html = ('<!doctype html><html lang="fr"><meta charset="utf-8"><title>Connexion professionnelle</title>'
            '<p role="status">Revenez à la fenêtre Industrial Predict AI pour vérifier votre connexion.</p>'
            f'<script nonce="{nonce}">{script}</script></html>')
    return HTMLResponse(html, status_code=status_code, headers=headers)


def create_google_login_router(*, login=None, client_secret_loader=None, browser_profile=None):
    if browser_profile is not None and (type(browser_profile) is not BrowserAuthProfile or login is None):
        raise ValueError('EXPLICIT_BROWSER_AUTH_PROFILE_REQUIRED')
    if login is not None:
        if type(login) is not GoogleSessionLogin or not callable(client_secret_loader):
            raise ValueError('OIDC_RUNTIME_REQUIRED')
        callback = urlsplit(login.client._config.callback_url)
        if callback.scheme != 'https' or callback.path != CALLBACK_PATH:
            raise ValueError('HTTPS_REGISTERED_CALLBACK_REQUIRED')
        if browser_profile is not None and browser_profile.origin != callback.scheme + '://' + callback.netloc:
            raise ValueError('BROWSER_CALLBACK_ORIGIN_MISMATCH')
    router = APIRouter(tags=['Authentication'])

    def configured_origin(request):
        return (login is not None and request.url.scheme == 'https'
                and request.url.netloc == callback.netloc)

    def qualified(request):
        if browser_profile is not None:
            runtime = getattr(request.app.state, 'b2b_auth_runtime', None)
            if (runtime is None or runtime.sql is not login.runtime
                    or getattr(request.app.state, 'sql_runtime', None) is not login.runtime):
                raise CallerProviderUnavailable()
            browser_profile.check(login.runtime)

    def callback_response(payload, status_code):
        if browser_profile is None:
            return JSONResponse(payload, status_code=status_code, headers=HEADERS)
        if status_code != 200:
            payload = {'kind': BROWSER_BRIDGE, 'error': 'unavailable' if status_code == 503 else 'denied'}
        else:
            payload = {'kind': BROWSER_BRIDGE, **payload}
        try:
            return popup_response(payload, origin=browser_profile.origin, status_code=status_code)
        except Exception:
            # If safe HTML/CSP construction fails, never downgrade to a JSON
            # bearer response or unsafe inline script in browser mode.
            return JSONResponse({'detail': 'OIDC_RUNTIME_UNAVAILABLE'}, status_code=503, headers=HEADERS)

    @router.get('/auth/oidc/google/start')
    def start(request: Request):
        if not configured_origin(request):
            return JSONResponse({'detail': 'OIDC_RUNTIME_UNAVAILABLE'}, status_code=503, headers=HEADERS)
        try:
            qualified(request)
            transaction, url = login.begin(return_target='predictions')
            response = RedirectResponse(url, status_code=302, headers=HEADERS)
            response.set_cookie(BINDING_COOKIE, transaction.browser_binding, path='/', secure=True,
                httponly=True, samesite='lax', max_age=login.client._config.transaction_ttl_seconds)
            return response
        except Exception:
            return JSONResponse({'detail': 'OIDC_RUNTIME_UNAVAILABLE'}, status_code=503, headers=HEADERS)

    @router.get(CALLBACK_PATH)
    def complete(request: Request):
        if not configured_origin(request):
            return JSONResponse({'detail': 'OIDC_RUNTIME_UNAVAILABLE'}, status_code=503, headers=HEADERS)
        try:
            qualified(request)
            bindings = [item.strip().split('=', 1)[0] for header in request.headers.getlist('cookie') for item in header.split(';')]
            if (len(request.query_params.getlist('state')) != 1 or len(request.query_params.getlist('code')) != 1
                    or 'error' in request.query_params or not request.cookies.get(BINDING_COOKIE)
                    or bindings.count(BINDING_COOKIE) != 1):
                raise CallerUnauthenticated()
            client_secret = client_secret_loader()
            if type(client_secret) is not str or not client_secret:
                raise CallerProviderUnavailable()
            arguments = dict(state=request.query_params['state'], code=request.query_params['code'],
                browser_binding=request.cookies[BINDING_COOKIE], client_secret=client_secret)
            if browser_profile is not None:
                arguments['require_company_access'] = True
            issued = login.complete_callback(**arguments)
            # Transient bearer delivery, never an automatically attached API cookie.
            response = callback_response({'token_type': 'Bearer', 'session_token': issued.secret,
                'absolute_expires_at': issued.record.absolute_expires_at.isoformat()}, 200)
        except (CallerUnauthenticated, CallerForbidden) as error:
            failure = security_error(error)
            response = callback_response({'detail': failure.detail}, failure.status_code)
        except Exception:
            response = callback_response({'detail': 'OIDC_RUNTIME_UNAVAILABLE'}, 503)
        response.delete_cookie(BINDING_COOKIE, path='/', secure=True, httponly=True, samesite='lax')
        return response

    return router
