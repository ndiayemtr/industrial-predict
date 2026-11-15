"""Opt-in browser session API. No router/engine is installed on import."""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.api.b2b import security_error, session_reference_from_request
from app.api.routes.b2b_login import HEADERS
from app.b2b_runtime import B2BRouteRuntime
from app.core.b2b_browser import BrowserAuthProfile, BROWSER_BRIDGE
from app.core.caller_session import CallerForbidden, CallerUnauthenticated, CallerProviderUnavailable
from app.schemas.b2b_auth import AuthenticatedProfile


def create_b2b_auth_router(*, runtime, profile, client_secret_loader):
    if (type(runtime) is not B2BRouteRuntime or type(profile) is not BrowserAuthProfile
            or not callable(client_secret_loader)):
        raise ValueError('EXPLICIT_BROWSER_AUTH_PROFILE_REQUIRED')
    router = APIRouter(prefix='/api/v1/auth', tags=['Authentication'])

    def qualified(request):
        if request.url.scheme + '://' + request.url.netloc != profile.origin:
            raise CallerProviderUnavailable()
        origins = request.headers.getlist('origin')
        sites = request.headers.getlist('sec-fetch-site')
        if (request.query_params or len(origins) > 1 or (origins and origins != [profile.origin])
                or len(sites) > 1 or (sites and sites != ['same-origin'])
                or (request.method == 'POST' and origins != [profile.origin])):
            raise CallerForbidden()
        if (getattr(request.app.state, 'b2b_auth_runtime', None) is not runtime
                or getattr(request.app.state, 'sql_runtime', None) is not runtime.sql
                or getattr(request.app.state, 'b2b_runtime', None) is not None):
            raise CallerProviderUnavailable()
        profile.check(runtime.sql)

    def context(request):
        # Preserve 401-before-qualification for the existing bearer endpoints.
        if request.url.scheme + '://' + request.url.netloc != profile.origin:
            raise CallerProviderUnavailable()
        reference = session_reference_from_request(request)
        qualified(request)
        return reference

    def failure(error):
        if isinstance(error, HTTPException):
            code, detail, extra = error.status_code, error.detail, error.headers or {}
        else:
            mapped = security_error(error)
            code, detail, extra = mapped.status_code, mapped.detail, mapped.headers or {}
        return JSONResponse({'detail': detail}, status_code=code, headers={**HEADERS, **extra})

    @router.get('/readiness')
    def readiness(request: Request):
        """Local auth-only readiness, NOT Google reachability or user admission.

        No bearer, session, OIDC transaction or provider request is involved.
        The exact destination/TLS/schema/functions/ACL guard runs on every call.
        Only the already approved secret loader is used; its value never leaves
        this stack frame. It cannot certify that Google will accept that secret.
        """
        secret = None
        try:
            if request.headers.getlist('authorization'):
                raise CallerForbidden()
            qualified(request)
            secret = client_secret_loader()
            if (type(secret) is not str or not 0 < len(secret) <= 4096
                    or secret != secret.strip() or any(ord(c) < 32 or ord(c) == 127 for c in secret)):
                raise CallerProviderUnavailable()
            return JSONResponse({'status': 'ready', 'profile': 'auth-only', 'bridgeVersion': BROWSER_BRIDGE}, headers=HEADERS)
        except (CallerForbidden, CallerProviderUnavailable) as error:
            return failure(error)
        except Exception:
            return failure(CallerProviderUnavailable())
        finally:
            secret = None

    @router.get('/me', response_model=AuthenticatedProfile)
    def me(request: Request):
        try:
            value = runtime.browser_profile(reference=context(request))
            result = AuthenticatedProfile.model_validate(value)
            return JSONResponse(result.model_dump(mode='json'), headers=HEADERS)
        except (HTTPException, CallerUnauthenticated, CallerForbidden, CallerProviderUnavailable) as error:
            return failure(error)
        except Exception:
            return failure(CallerProviderUnavailable())

    @router.post('/logout', status_code=204, response_class=Response)
    def logout(request: Request):
        try:
            runtime.logout(reference=context(request))
            return Response(status_code=204, headers=HEADERS)
        except (HTTPException, CallerUnauthenticated, CallerForbidden, CallerProviderUnavailable) as error:
            return failure(error)
        except Exception:
            return failure(CallerProviderUnavailable())

    return router
