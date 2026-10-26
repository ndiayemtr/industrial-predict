"""No HTTP client, ASGI request, server or database: direct GET handlers + simulated reader."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

from fastapi import HTTPException
import psycopg
import pytest
from sqlalchemy import URL
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.p101_local_demo import api, api_reader, provisioning, reader, serve_api
from app.p101_local_demo.api_reads import ApiReads
from app.p101_local_demo.setup_config import CLUSTER,ROOT,ROLES,SetupSettings
from app.p101_persistence.contracts import CALCULATION_REVISION,FIXTURE_SHA256


@pytest.fixture(autouse=True)
def forbid_database_network_and_servers(monkeypatch):
    def forbidden(*a,**k): raise AssertionError('Only direct offline reader tests allowed')
    for cls,name in ((Engine,'connect'),(Engine,'raw_connection'),(Connection,'execute'),
                     (Connection,'exec_driver_sql'),(Session,'commit'),(Session,'flush')):
        monkeypatch.setattr(cls,name,forbidden)
    monkeypatch.setattr(psycopg,'connect',forbidden)
    for name in ('connect','connect_ex'): monkeypatch.setattr(socket.socket,name,forbidden)
    monkeypatch.setattr(socket,'getaddrinfo',forbidden)
    monkeypatch.setattr(socket,'create_connection',forbidden)
    import uvicorn
    monkeypatch.setattr(uvicorn,'run',forbidden)
    for key in list(os.environ):
        if key.startswith('PG'): monkeypatch.delenv(key)


@pytest.fixture
def settings():
    return SetupSettings(str(ROOT.parent/'p101-private-example'),'127.0.0.1',55432,
        'industrial_predict_p101_local_demo','172.30.101.2',5432,'172.30.101.0/28',
        '00000000-0000-4000-8000-000000000077','2026-10-26T00:00:00.000000Z',
        tuple(zip(ROLES,('admin.password','owner.password','writer.password','reader.password'))))


@pytest.fixture
def reference():
    return json.loads((ROOT/'tests/p101_anomaly/fixtures/p101-temperature-v1.json').read_text(encoding='utf-8'))


@pytest.fixture
def data(settings,reference):
    common=dict(description=None,created_at=datetime(2026,10,26),updated_at=datetime(2026,10,26))
    parents=dict(companies=[dict(common,id=101,name='Entreprise synthétique',code='MLDEMO-COMP-P101')],
        sites=[dict(common,id=202,name='Site synthétique',code='MLDEMO-SITE-P101',company_id=101)],
        equipments=[dict(common,id=303,name='Pompe P101 synthétique',code='MLDEMO-EQ-P101',site_id=202,
            equipment_type='pump',status='operational',criticality='medium')],
        sensors=[dict(common,id=404,name='Température synthétique',code='MLDEMO-SEN-P101-TEMP',equipment_id=303,
            sensor_type='temperature',unit='°C',status='active')])
    parents['measurements']=[dict(id=501+i,sensor_id=404,value=o['value'],quality='good',
        timestamp=datetime.fromisoformat(o['timestamp'].replace('Z','+00:00'))) for i,o in enumerate(reference['observations'])]
    mapping=dict(company_id=101,site_id=202,equipment_id=303,sensor_id=404,
                 measurements={f'DEMO-M-{i:03d}':500+i for i in range(1,13)})
    records=[]
    for i in range(2):
        observation=reference['observations'][10+i]
        target={k:observation[k] for k in ('fixture_id','timestamp','available_at','value','quality','unit')}
        # Already-persisted response stand-ins. No evaluate(), inference or INSERT creates these fixtures.
        reason='Démonstration synthétique : indicateur binaire sans probabilité de panne.'
        calc=dict(reason=reason,synthetic=True,target=target,producer=dict(code_revision=CALCULATION_REVISION),
            cutoff_utc=f'2026-01-{11+i:02d}T08:01:00.000000Z',prepared_at='2026-10-26T00:00:00.000000Z',
            statistics=dict(score_semantics='binary_indicator_non_probabilistic'))
        details=dict(schema_version='p101-local-demo-details-v1',synthetic=True,reason=reason,calculation=calc,
            local_demo=dict(instance_uuid=settings.instance_uuid,adapter_version='p101-local-persistence-v1',
                            idempotency_key='1'*64,content_sha256='2'*64,sql_mapping=deepcopy(mapping)))
        records.append(dict(id=701+i,equipment_id=303,sensor_id=404,measurement_id=511+i,
            prediction_type='anomaly',score=float(i),level=None,is_alert=bool(i),
            model_name='statistical_deviation',model_version='p101-stat-v1',horizon_hours=None,details=details,
            predicted_at=datetime(2026,1,11+i,8,tzinfo=timezone.utc),created_at=datetime(2026,10,26,tzinfo=timezone.utc)))
    parents['prediction_records']=list(reversed(records))
    return parents


class Result:
    def __init__(self,rows): self.rows=rows
    def mappings(self): return self
    def one(self): assert len(self.rows)==1; return self.rows[0]
    def scalar_one(self): return self.one()
    def __iter__(self): return iter(self.rows)


class FakeConnection:
    def __init__(self,settings,data):
        self.settings,self.data=settings,data
        self.events=[]; self.statements=[]; self.bad_guard=None; self.read_only='on'
        self.identity_overrides={}
        self.tx=SimpleNamespace(is_active=True,rollback=self.rollback)
        self.engine=SimpleNamespace(url=URL.create('postgresql+psycopg',host=settings.host,port=settings.port,
            database=settings.database,username=ROLES[3]))
        self.connection=SimpleNamespace(driver_connection=SimpleNamespace(info=SimpleNamespace(
            host=settings.host,port=settings.port,dbname=settings.database,user=ROLES[3],
            get_parameters=lambda:{'sslmode':'disable'}),pgconn=SimpleNamespace(ssl_in_use=False)))
    def __enter__(self): self.events.append('connect'); return self
    def __exit__(self,*a): self.events.append('close')
    def begin(self): self.events.append('begin'); self.tx.is_active=True; return self.tx
    def in_transaction(self): return self.tx.is_active
    def rollback(self): self.events.append('rollback'); self.tx.is_active=False
    def execute(self,statement):
        self.statements.append(statement)
        s=self.settings
        if statement is provisioning.IDENTITY:
            return Result([dict(database=s.database,session_role=ROLES[3],effective_role=ROLES[3],
                server_address=s.server_address,server_port=5432,cluster=CLUSTER,encoding='UTF8',isolation='read committed',
                no_protected_schema=True,no_memberships=True,rolsuper=False,rolcreatedb=False,
                rolcreaterole=False,rolreplication=False,rolbypassrls=False)])
        if statement is reader.IDENTITY_SQL:
            identity=dict(database=s.database,database_name=s.database,purpose='local-p101-functional-demo',
                session_role=ROLES[3],effective_role=ROLES[3],server_address=s.server_address,server_port=5432,
                isolation_level='read committed',encoding='UTF8',instance_uuid=s.instance_uuid,
                schema_revision='p101_local_0001',installed_revision='p101_local_0001',bootstrap_closed=True,
                no_protected_schema=True,limited_role=True,no_memberships=True,not_owner=True,
                source_read=True,sources_immutable=True)
            identity.update(self.identity_overrides)
            return Result([identity])
        if str(statement)=='SHOW transaction_read_only': return Result([self.read_only])
        if str(statement).lstrip().startswith('SELECT fixture_sha256'):
            row=dict(fixture_sha256=FIXTURE_SHA256,predictions_read_only=True,owner_closed=True)
            if self.bad_guard: row[self.bad_guard]=False
            return Result([row])
        assert getattr(statement,'is_select',False),'No mutation or recalculation SQL allowed'
        assert str(statement.compile(dialect=postgresql.dialect())).lstrip().startswith('SELECT')
        return Result(deepcopy(self.data[statement.get_final_froms()[0].name]))


@pytest.fixture
def reads(settings,reference,data): return ApiReads(FakeConnection(settings,data),settings.destination(ROLES[3]),reference)


def handler(app,path): return next(r for r in app.routes if r.path==path).endpoint


def history(db,**kwargs):
    return db.prediction_history(303,page=kwargs.pop('page',1),page_size=kwargs.pop('page_size',20),**kwargs)


def test_routes_contract_and_no_write_or_extra_routes(settings):
    app=api.create_app(settings)
    paths={'/api/v1/companies','/api/v1/companies/{company_id}','/api/v1/sites','/api/v1/sites/{site_id}',
           '/api/v1/equipments','/api/v1/equipments/{equipment_id}','/api/v1/equipments/{equipment_id}/predictions'}
    assert {r.path for r in app.routes}==paths
    assert all(r.methods=={'GET'} for r in app.routes)
    assert app.docs_url is None and app.openapi_url is None
    spec=app.openapi()
    fields=spec['components']['schemas']['PredictionRecordRead']['properties']
    assert len(fields)==14
    params=spec['paths']['/api/v1/equipments/{equipment_id}/predictions']['get']['parameters']
    assert {p['name'] for p in params}=={'equipment_id','page','page_size','prediction_type','level','is_alert','start_time','end_time'}
    assert next(p for p in params if p['name']=='page_size')['schema']['maximum']==100


def test_company_site_equipment_selection_handlers(settings,reads):
    app=api.create_app(settings)
    for path,kind,identity in (('/companies','companies',101),('/sites','sites',202),('/equipments','equipments',303)):
        kwargs=dict(page=1,page_size=50,search=None,db=reads)
        if kind=='sites': kwargs['company_id']=101
        if kind=='equipments': kwargs.update(site_id=202,status=None,criticality=None)
        result=handler(app,'/api/v1'+path)(**kwargs)
        assert result.total==1 and result.pages==1 and result.items[0]['id']==identity
    assert handler(app,'/api/v1/companies/{company_id}')(company_id=101,db=reads)['id']==101
    assert handler(app,'/api/v1/sites/{site_id}')(site_id=202,db=reads)['company_id']==101
    assert handler(app,'/api/v1/equipments/{equipment_id}')(equipment_id=303,db=reads)['site_id']==202
    assert reads.references('sites',page=1,page_size=20,company_id=999).total==0
    assert reads.references('equipments',page=1,page_size=20,site_id=999).total==0


def test_prediction_response_refresh_has_fourteen_fields_and_no_effect(settings,reads,data):
    from app.schemas.pagination import Page
    from app.schemas.prediction_record import PredictionRecordRead
    before=deepcopy(data)
    app=api.create_app(settings)
    get=handler(app,'/api/v1/equipments/{equipment_id}/predictions')
    kwargs=dict(equipment_id=303,page=1,page_size=20,prediction_type=None,level=None,is_alert=None,
                start_time=None,end_time=None,db=reads)
    first=get(**kwargs); second=get(**kwargs)
    body=Page[PredictionRecordRead].model_validate(first.model_dump()).model_dump(mode='json')
    assert body['total']==2 and body['pages']==1
    assert [(r['score'],r['is_alert']) for r in body['items']]==[(1.0,True),(0.0,False)]
    assert all(len(r)==14 and r['model_version']=='p101-stat-v1' for r in body['items'])
    assert all(r['details']['calculation']['statistics']['score_semantics']=='binary_indicator_non_probabilistic' for r in body['items'])
    assert first==second and data==before
    assert all(getattr(s,'is_select',False) for s in reads.connection.statements)


@pytest.mark.parametrize('filters,total', [({},2),({'is_alert':False},1),({'is_alert':True},1),
    ({'prediction_type':'anomaly'},2),({'prediction_type':'rul'},0),({'level':'high'},0),
    ({'start_time':datetime(2026,1,12,8,tzinfo=timezone.utc),'end_time':datetime(2026,1,12,8,tzinfo=timezone.utc)},1)])
def test_prediction_filters_inclusive_and_empty(reads,filters,total):
    assert history(reads,**filters).total==total


def test_pagination_keeps_existing_contract(reads):
    first=history(reads,page_size=1); second=history(reads,page=2,page_size=1)
    assert first.total==second.total==2 and first.pages==2
    assert first.items[0]['id']==702 and second.items[0]['id']==701
    assert history(reads,page=3,page_size=1).items==[]


@pytest.mark.parametrize('change',['partial','duplicate','score','alert','other_equipment','uuid','nonfinite','details_schema','mapping','unit','source_value'])
def test_bad_data_refused(reads,data,change):
    row=data['prediction_records'][0]
    if change=='partial': data['prediction_records'].pop()
    elif change=='duplicate': data['prediction_records'][1]=deepcopy(row)
    elif change=='score': row['score']=0
    elif change=='alert': row['is_alert']=1
    elif change=='other_equipment': row['equipment_id']=999
    elif change=='uuid': row['details']['local_demo']['instance_uuid']='wrong'
    elif change=='nonfinite': row['details']['score']=float('inf')
    elif change=='details_schema': row['details']['schema_version']='wrong'
    elif change=='mapping': row['details']['local_demo']['sql_mapping']['equipment_id']=True
    elif change=='unit': data['sensors'][0]['unit']='F'
    elif change=='source_value': data['measurements'][0]['value']=99
    with pytest.raises((ValueError,KeyError,TypeError)): history(reads)


@pytest.mark.parametrize('query', [dict(start_time=datetime(2026,1,1)),
    dict(start_time=datetime(2026,1,13,tzinfo=timezone.utc),end_time=datetime(2026,1,12,tzinfo=timezone.utc))])
def test_bad_period_is_422(settings,reads,query):
    get=handler(api.create_app(settings),'/api/v1/equipments/{equipment_id}/predictions')
    kwargs=dict(equipment_id=303,page=1,page_size=20,prediction_type=None,level=None,is_alert=None,
                start_time=None,end_time=None,db=reads)
    kwargs.update(query)
    with pytest.raises(HTTPException) as exc: get(**kwargs)
    assert exc.value.status_code==422


def test_not_found_and_private_errors_are_sanitized(settings,reads):
    get=handler(api.create_app(settings),'/api/v1/equipments/{equipment_id}')
    with pytest.raises(HTTPException) as exc: get(equipment_id=999,db=reads)
    assert exc.value.status_code==404
    reads.connection.execute=lambda *a: (_ for _ in ()).throw(RuntimeError('unit-only-sensitive-canary'))
    reads._rows=None
    with pytest.raises(HTTPException) as exc: get(equipment_id=303,db=reads)
    assert exc.value.status_code==503 and 'canary' not in str(exc.value)


@pytest.mark.parametrize('corruption',['missing_calculation_key','nonfinite_detail'])
def test_corrupt_stored_data_is_unavailable_not_missing_reference(settings,reads,data,corruption):
    if corruption=='missing_calculation_key':
        data['prediction_records'][0]['details']['calculation'].pop('producer')
    else:
        data['prediction_records'][0]['details']['calculation']['unexpected']=float('nan')
    get=handler(api.create_app(settings),'/api/v1/equipments/{equipment_id}/predictions')
    with pytest.raises(HTTPException) as exc:
        get(equipment_id=303,page=1,page_size=20,prediction_type=None,level=None,is_alert=None,
            start_time=None,end_time=None,db=reads)
    assert exc.value.status_code==503 and exc.value.detail=='P101_READ_UNAVAILABLE'


@pytest.mark.parametrize('field,value',[('database','industrial_predict_dev'),('host','localhost'),('port',5433),
                                      ('server_address','invalid'),('instance_uuid','invalid')])
def test_bad_destination_before_factory(settings,field,value):
    with pytest.raises(ValueError): api.create_app(replace(settings,**{field:value}))


@pytest.mark.parametrize('role',ROLES[:3])
def test_only_reader_role_permitted(settings,role):
    with pytest.raises(api_reader.ApiReadError):
        with api_reader.reader_connection(settings,role): pytest.fail('No connection allowed')


def test_implicit_pg_config_rejected(settings,monkeypatch):
    monkeypatch.setenv('PGSERVICE','unused-test-sentinel')
    with pytest.raises(ValueError): api.create_app(settings)


@pytest.mark.parametrize('failure',[None,'readonly','owner_closed','predictions_read_only','identity',
                                  'uuid','marker','role','port','revision'])
def test_reader_session_guard_rollback_and_no_commit(settings,data,monkeypatch,failure):
    import sqlalchemy
    c=FakeConnection(settings,data)
    if failure=='readonly': c.read_only='off'
    elif failure=='identity': c.connection.driver_connection.info.dbname='industrial_predict_dev'
    elif failure in ('uuid','marker','role','port','revision'):
        c.identity_overrides.update(dict([{
            'uuid':('instance_uuid','wrong'), 'marker':('bootstrap_closed',False),
            'role':('effective_role',ROLES[2]), 'port':('server_port',55432),
            'revision':('installed_revision','other')}[failure]]))
    elif failure: c.bad_guard=failure
    captured={}
    class FakeEngine:
        def connect(self): return c
        def dispose(self): c.events.append('dispose')
    def factory(url,**kwargs):
        captured.update(url=url,kwargs=kwargs)
        return FakeEngine()
    monkeypatch.setattr(sqlalchemy,'create_engine',factory)
    monkeypatch.setattr(api_reader,'read_secret',lambda *a:'test-only-private-secret-placeholder')
    def operation():
        with api_reader.reader_connection(settings) as connection:
            assert connection is c
    if failure:
        with pytest.raises(ValueError): operation()
    else: operation()
    assert c.events[-3:]==['rollback','close','dispose']
    assert 'commit' not in c.events
    assert captured['url'].username==ROLES[3]
    assert 'default_transaction_read_only=on' in captured['kwargs']['connect_args']['options']
    assert captured['kwargs']['hide_parameters'] is True


@pytest.mark.parametrize('method',['POST','PUT','PATCH','DELETE','HEAD','OPTIONS'])
def test_method_middleware_rejects_without_dependency(settings,method):
    app=api.create_app(settings)
    middleware=next(m for m in app.user_middleware if m.cls.__name__=='BaseHTTPMiddleware')
    async def forbidden(request): pytest.fail('Must not dispatch non-GET')
    coroutine=middleware.kwargs['dispatch'](SimpleNamespace(method=method),forbidden)
    with pytest.raises(StopIteration) as stopped:
        coroutine.send(None)  # Immediate rejection path, no event loop/socket or ASGI request.
    response=stopped.value.value
    assert response.status_code==405


def test_dedicated_proxy_and_loopback_launchers():
    proxy=json.loads((ROOT/'frontend/proxy.p101.conf.json').read_text(encoding='utf-8'))
    assert proxy=={'/api/v1/**':{'target':'http://127.0.0.1:8001','changeOrigin':True}}
    usual=json.loads((ROOT/'frontend/proxy.conf.json').read_text(encoding='utf-8'))
    assert usual['/api/v1/**']['target']=='http://127.0.0.1:8000'
    script=(ROOT/'frontend/scripts/serve-p101.ps1').read_text(encoding='utf-8')
    assert '--host 127.0.0.1 --port 4201 --proxy-config proxy.p101.conf.json' in script
    backend=(ROOT/'backend/app/p101_local_demo/serve_api.py').read_text(encoding='utf-8')
    assert "host='127.0.0.1',port=8001" in backend
    display=(ROOT/'frontend/src/app/features/predictions/utils/prediction-display.ts').read_text(encoding='utf-8')
    assert "anomaly: 'Indice d’anomalie'" in display
    assert "item.prediction_type === 'failure_risk' && validProbability" in display


def test_launcher_ack_required_without_server(settings,monkeypatch):
    monkeypatch.setattr(serve_api,'load_settings',lambda path:settings)
    assert serve_api.main(['--config','fictitious.json','--instance',settings.instance_uuid])==1
    assert serve_api.main(['--config','fictitious.json','--instance','wrong','--serve'])==1


def test_fresh_import_and_app_creation_cannot_load_dev_or_ml():
    script='''
import builtins,socket,sqlalchemy,psycopg
def forbidden(*a,**k): raise AssertionError('Forbidden side effect')
sqlalchemy.create_engine=forbidden
psycopg.connect=forbidden
socket.create_connection=forbidden
socket.socket.connect=forbidden
original=builtins.__import__
def guarded(name,*a,**k):
    if name.startswith(('app.core.database','app.core.config','app.models','app.services','app.api.routes',
        'app.p101_postgres','app.anomaly_detection.p101_core','app.p101_local_demo.processing',
        'app.p101_local_demo.prediction_persistence','app.p101_local_demo.run_predictions')): forbidden()
    return original(name,*a,**k)
builtins.__import__=guarded
from app.p101_local_demo.api import create_app
from app.p101_local_demo.setup_config import SetupSettings,ROLES,ROOT
s=SetupSettings(str(ROOT.parent/'p101-private-example'),'127.0.0.1',55432,'industrial_predict_p101_local_demo',
 '172.30.101.2',5432,'172.30.101.0/28','00000000-0000-4000-8000-000000000077',
 '2026-10-26T00:00:00.000000Z',tuple(zip(ROLES,('admin.password','owner.password','writer.password','reader.password'))))
assert len(create_app(s).routes)==7
print('safe')
'''
    env=dict(os.environ,PYTHONPATH=str(ROOT/'backend'),PYTHONDONTWRITEBYTECODE='1',DATABASE_URL='unused-test-sentinel')
    result=subprocess.run([sys.executable,'-B','-c',script],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='safe'
