"""Seven GET routes for existing Angular Predictions; explicit validated factory only."""

from app.p101_local_demo.api_reader import reader_connection, validate_api_settings


def create_app(settings):
    destination = validate_api_settings(settings)
    # No generic route/service/model import: those import app.core.database eagerly.
    import json
    from datetime import datetime
    from fastapi import Depends, FastAPI, HTTPException, Path, Query
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    from starlette.responses import JSONResponse
    from app.core.enums import EquipmentCriticality, EquipmentStatus, PredictionType
    from app.schemas.company import CompanyRead
    from app.schemas.site import SiteRead
    from app.schemas.equipment import EquipmentRead
    from app.schemas.prediction_record import PredictionRecordRead
    from app.schemas.pagination import Page
    from app.p101_local_demo.api_reader import ApiQueryError, ApiReadError, ApiReferenceNotFound
    from app.p101_local_demo.api_reads import ApiReads
    from app.p101_local_demo.reader import validate_fixture
    from app.p101_local_demo.setup_config import ROOT

    reference = json.loads((ROOT/'tests/p101_anomaly/fixtures/p101-temperature-v1.json').read_text(encoding='utf-8'))
    validate_fixture(reference)
    app = FastAPI(title='P101 local predictions — read only', docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1'])

    @app.middleware('http')
    async def get_only(request, call_next):
        if request.method != 'GET':
            return JSONResponse({'detail':'P101_READ_ONLY_API'}, status_code=405)
        return await call_next(request)

    def reads():
        try:
            with reader_connection(settings) as connection:
                yield ApiReads(connection, destination, reference)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=503, detail='P101_READ_UNAVAILABLE') from None

    def call(method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except ApiReferenceNotFound:
            raise HTTPException(status_code=404, detail='P101_REFERENCE_NOT_FOUND') from None
        except ApiReadError:
            raise HTTPException(status_code=503, detail='P101_READ_UNAVAILABLE') from None
        except ApiQueryError:
            raise HTTPException(status_code=422, detail='P101_QUERY_REJECTED') from None
        except Exception:
            raise HTTPException(status_code=503, detail='P101_READ_UNAVAILABLE') from None

    prefix = '/api/v1'

    @app.get(prefix+'/companies', response_model=Page[CompanyRead])
    def companies(page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100),
                  search:str|None=Query(None,min_length=1,max_length=100), db:ApiReads=Depends(reads)):
        return call(db.references,'companies',page=page,page_size=page_size,search=search)

    @app.get(prefix+'/companies/{company_id}', response_model=CompanyRead)
    def company(company_id:int=Path(ge=1), db:ApiReads=Depends(reads)):
        return call(db.reference_by_id,'companies',company_id)

    @app.get(prefix+'/sites', response_model=Page[SiteRead])
    def sites(page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100),
              company_id:int|None=Query(None,ge=1), search:str|None=Query(None,min_length=1,max_length=100),
              db:ApiReads=Depends(reads)):
        return call(db.references,'sites',page=page,page_size=page_size,search=search,company_id=company_id)

    @app.get(prefix+'/sites/{site_id}', response_model=SiteRead)
    def site(site_id:int=Path(ge=1), db:ApiReads=Depends(reads)):
        return call(db.reference_by_id,'sites',site_id)

    @app.get(prefix+'/equipments', response_model=Page[EquipmentRead])
    def equipments(page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100),
                   site_id:int|None=Query(None,ge=1), status:EquipmentStatus|None=Query(None),
                   criticality:EquipmentCriticality|None=Query(None),
                   search:str|None=Query(None,min_length=1,max_length=100), db:ApiReads=Depends(reads)):
        return call(db.references,'equipments',page=page,page_size=page_size,search=search,
                    site_id=site_id,status=status,criticality=criticality)

    @app.get(prefix+'/equipments/{equipment_id}', response_model=EquipmentRead)
    def equipment(equipment_id:int=Path(ge=1), db:ApiReads=Depends(reads)):
        return call(db.reference_by_id,'equipments',equipment_id)

    @app.get(prefix+'/equipments/{equipment_id}/predictions', response_model=Page[PredictionRecordRead])
    def predictions(equipment_id:int=Path(ge=1), page:int=Query(1,ge=1), page_size:int=Query(20,ge=1,le=100),
                    prediction_type:PredictionType|None=Query(None), level:str|None=Query(None,min_length=1,max_length=50),
                    is_alert:bool|None=Query(None), start_time:datetime|None=Query(None), end_time:datetime|None=Query(None),
                    db:ApiReads=Depends(reads)):
        return call(db.prediction_history,equipment_id,page=page,page_size=page_size,
                    prediction_type=prediction_type.value if prediction_type is not None else None,
                    level=level,is_alert=is_alert,start_time=start_time,end_time=end_time)

    return app
