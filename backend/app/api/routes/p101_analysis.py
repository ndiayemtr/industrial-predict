"""P101 v1 HTTP adapter, closed unless trusted server dependencies are installed."""

from fastapi import APIRouter, HTTPException, Path, Request

from app.core.caller_session import CallerUnauthenticated, CallerForbidden, SessionReference
from app.schemas.p101_analysis import AnalysisRequest, AnalysisResponse
from app.api.b2b import session_runtime, security_error
from app.core.caller_session import CallerProviderUnavailable


def require_b2b_integration():
    # Historical routes have no scoped authorizer. Do not enable via a boolean.
    raise HTTPException(503, 'B2B_INTEGRATION_REQUIRED')


def create_p101_analysis_router(*, service=None, session_resolver=None):
    router = APIRouter(prefix='/equipments', tags=['P101'])

    @router.post('/{equipment_id}/p101-analysis', response_model=AnalysisResponse)
    def analyze(data: AnalysisRequest, request: Request, equipment_id: int = Path(gt=0)):
        try:
            if service is None and session_resolver is None:
                runtime, reference = session_runtime(request)
                return runtime.analyze(reference=reference, equipment_id=equipment_id, request=data)
            if service is None or not callable(session_resolver):
                raise CallerProviderUnavailable()
            reference = session_resolver(request)
            if type(reference) is not SessionReference:
                raise CallerUnauthenticated()
            reference.__post_init__()
            return service.analyze(reference=reference, equipment_id=equipment_id, request=data)
        except CallerUnauthenticated:
            raise HTTPException(401, 'AUTHENTICATION_REQUIRED') from None
        except CallerForbidden:
            raise HTTPException(403, 'P101_ANALYSIS_FORBIDDEN') from None
        except HTTPException:
            raise
        except CallerProviderUnavailable as error:
            raise security_error(error) from None
        except Exception:
            raise HTTPException(503, 'P101_ANALYSIS_UNAVAILABLE') from None

    return router
