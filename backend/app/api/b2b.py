"""Bearer application sessions only; never accept an ID token as an API session."""

from fastapi import HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.application_session_store import session_reference
from app.b2b_runtime import B2BRouteRuntime
from app.core.authorization import Permission
from app.core.caller_session import CallerUnauthenticated, CallerForbidden, CallerProviderUnavailable


def session_runtime(request):
    values = request.headers.getlist('authorization')
    if len(values) != 1 or not values[0].startswith('Bearer '):
        raise HTTPException(401, 'AUTHENTICATION_REQUIRED', headers={'WWW-Authenticate': 'Bearer'})
    try:
        reference = session_reference(values[0][7:])
    except Exception:
        raise HTTPException(401, 'AUTHENTICATION_REQUIRED', headers={'WWW-Authenticate': 'Bearer'}) from None
    runtime = getattr(request.app.state, 'b2b_runtime', None)
    if type(runtime) is not B2BRouteRuntime:
        raise HTTPException(503, 'B2B_RUNTIME_UNAVAILABLE')
    return runtime, reference


def security_error(error):
    if isinstance(error, CallerUnauthenticated):
        return HTTPException(401, 'AUTHENTICATION_REQUIRED', headers={'WWW-Authenticate': 'Bearer'})
    if isinstance(error, CallerForbidden):
        return HTTPException(403, 'B2B_FORBIDDEN')
    return HTTPException(503, 'B2B_RUNTIME_UNAVAILABLE')


def _equipment_db(request, equipment_id, *, write):
    runtime, reference = session_runtime(request)
    permissions = (Permission.PREDICTIONS_READ, Permission.MAINTENANCE_WRITE) if write else (Permission.PREDICTIONS_READ,)
    try:
        with runtime.authorized_equipment(reference=reference, equipment_id=equipment_id,
                                           permissions=permissions, write=write) as (db, scope):
            yield db
    except (CallerUnauthenticated, CallerForbidden, CallerProviderUnavailable) as error:
        raise security_error(error) from None
    except SQLAlchemyError:
        raise HTTPException(503, 'B2B_RUNTIME_UNAVAILABLE') from None


def prediction_read_db(request: Request, equipment_id: int):
    yield from _equipment_db(request, equipment_id, write=False)


def recommendation_write_db(request: Request, equipment_id: int):
    yield from _equipment_db(request, equipment_id, write=True)
