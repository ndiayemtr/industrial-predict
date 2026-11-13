"""Opt-in Google code flow. No provider, callback secret or cookies by default."""

from urllib.parse import urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.b2b_runtime import GoogleSessionLogin
from app.core.caller_session import CallerForbidden, CallerUnauthenticated, CallerProviderUnavailable
from app.api.b2b import security_error


CALLBACK_PATH = '/auth/oidc/google/callback'
BINDING_COOKIE = '__Host-industrial-oidc-binding'
HEADERS = {'Cache-Control': 'no-store', 'Pragma': 'no-cache', 'Referrer-Policy': 'no-referrer',
           'X-Content-Type-Options': 'nosniff', 'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'"}


def create_google_login_router(*, login=None, client_secret_loader=None):
    if login is not None:
        if type(login) is not GoogleSessionLogin or not callable(client_secret_loader):
            raise ValueError('OIDC_RUNTIME_REQUIRED')
        callback = urlsplit(login.client._config.callback_url)
        if callback.scheme != 'https' or callback.path != CALLBACK_PATH:
            raise ValueError('HTTPS_REGISTERED_CALLBACK_REQUIRED')
    router = APIRouter(tags=['Authentication'])

    def configured_origin(request):
        return (login is not None and request.url.scheme == 'https'
                and request.url.netloc == callback.netloc)

    @router.get('/auth/oidc/google/start')
    def start(request: Request):
        if not configured_origin(request):
            return JSONResponse({'detail': 'OIDC_RUNTIME_UNAVAILABLE'}, status_code=503, headers=HEADERS)
        try:
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
            if (len(request.query_params.getlist('state')) != 1 or len(request.query_params.getlist('code')) != 1
                    or 'error' in request.query_params or not request.cookies.get(BINDING_COOKIE)):
                raise CallerUnauthenticated()
            client_secret = client_secret_loader()
            if type(client_secret) is not str or not client_secret:
                raise CallerProviderUnavailable()
            issued = login.complete_callback(state=request.query_params['state'], code=request.query_params['code'],
                browser_binding=request.cookies[BINDING_COOKIE], client_secret=client_secret)
            # Transient bearer delivery, never an automatically attached API cookie.
            response = JSONResponse({'token_type': 'Bearer', 'session_token': issued.secret,
                'absolute_expires_at': issued.record.absolute_expires_at.isoformat()}, headers=HEADERS)
        except (CallerUnauthenticated, CallerForbidden) as error:
            failure = security_error(error)
            response = JSONResponse({'detail': failure.detail}, status_code=failure.status_code, headers=HEADERS)
        except Exception:
            response = JSONResponse({'detail': 'OIDC_RUNTIME_UNAVAILABLE'}, status_code=503, headers=HEADERS)
        response.delete_cookie(BINDING_COOKIE, path='/', secure=True, httponly=True, samesite='lax')
        return response

    return router
