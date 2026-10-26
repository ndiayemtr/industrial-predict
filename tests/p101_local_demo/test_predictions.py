"""Synthetic SQL rows + real ML3 + simulated transactions. Never a PostgreSQL proof."""

import ast
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

import psycopg
import pytest
from sqlalchemy import URL
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.anomaly_detection.p101_contracts import Abstained, AbstentionCode, Computed
from app.p101_local_demo.contracts import CUTOFFS, CalculationContext, ComputedPair, SqlRows
from app.p101_local_demo import prediction_persistence as service, provisioning, reader
from app.p101_local_demo.prediction_mapping import FIELDS, PredictionError, compare_records, prepare_predictions
from app.p101_local_demo.processing import process_rows
from app.p101_local_demo.setup_config import CLUSTER, ROOT, ROLES, SetupSettings
from app.p101_persistence.contracts import CALCULATION_REVISION, FIXTURE_SHA256


@pytest.fixture(autouse=True)
def no_real_database_or_network(monkeypatch):
    def forbidden(*a, **kw): raise AssertionError('Only synthetic calculations and simulated SQL are authorized')
    for cls, name in ((Engine,'connect'),(Engine,'raw_connection'),(Connection,'execute'),
                      (Connection,'exec_driver_sql'),(Session,'execute'),(Session,'commit'),(Session,'flush')):
        monkeypatch.setattr(cls,name,forbidden)
    monkeypatch.setattr(psycopg,'connect',forbidden)
    for name in ('connect','connect_ex'): monkeypatch.setattr(socket.socket,name,forbidden)
    monkeypatch.setattr(socket,'getaddrinfo',forbidden)
    monkeypatch.setattr(socket,'create_connection',forbidden)
    for key in list(os.environ):
        if key.startswith('PG'): monkeypatch.delenv(key)


@pytest.fixture
def settings():
    return SetupSettings(str(ROOT.parent/'p101-private-example'),'127.0.0.1',55432,
        'industrial_predict_p101_local_demo','172.30.101.2',5432,'172.30.101.0/28',
        '00000000-0000-4000-8000-000000000054','2026-10-26T00:00:00.000000Z',
        tuple(zip(ROLES,('admin.password','owner.password','writer.password','reader.password'))))


@pytest.fixture
def context():
    return CalculationContext('00000000-0000-4000-8000-000000000055',
                              '2026-10-26T00:00:00.000000Z',CALCULATION_REVISION,CUTOFFS)


@pytest.fixture
def reference():
    return json.loads((ROOT/'tests/p101_anomaly/fixtures/p101-temperature-v1.json').read_text(encoding='utf-8'))


@pytest.fixture
def rows(reference):
    return SqlRows(
        ({'id':101,'code':'MLDEMO-COMP-P101'},),
        ({'id':202,'code':'MLDEMO-SITE-P101','company_id':101},),
        ({'id':303,'code':'MLDEMO-EQ-P101','site_id':202,'name':'Pompe P101 synthétique',
          'equipment_type':'pump','status':'operational','criticality':'medium'},),
        ({'id':404,'code':'MLDEMO-SEN-P101-TEMP','equipment_id':303,'sensor_type':'temperature',
          'unit':'°C','status':'active'},),
        tuple(dict(id=500+i,sensor_id=404,timestamp=datetime.fromisoformat(r['timestamp'].replace('Z','+00:00')),
                   value=float(r['value']),quality=r['quality']) for i,r in enumerate(reference['observations'],1)))


@pytest.fixture
def pair(rows,reference,context): return process_rows(rows,reference,context)


def plans_for(pair,settings,reference,context):
    return prepare_predictions(pair,settings.destination(ROLES[2]),reference,context,context.prepared_at)


def stored(plans):
    return tuple(dict(p.sql_values(),id=701+i) for i,p in enumerate(plans))


def test_full_mapping_and_real_synthetic_results(pair,settings,reference,context):
    before=deepcopy(pair)
    plans=plans_for(pair,settings,reference,context)
    assert [r.prediction.score for r in pair.results]==[0,1]
    assert [r.prediction.is_alert for r in pair.results]==[False,True]
    for i,p in enumerate(plans):
        v=p.sql_values()
        assert set(v)==set(FIELDS)-{'id'}
        assert (v['equipment_id'],v['sensor_id'],v['measurement_id'])==(303,404,511+i)
        assert v['prediction_type']=='anomaly' and v['model_name']=='statistical_deviation'
        assert v['model_version']=='p101-stat-v1' and v['level'] is None and v['horizon_hours'] is None
        assert v['details']['calculation']==pair.results[i].prediction.details
        assert len(json.dumps(v['details'],ensure_ascii=False).encode())<=6000
        assert v['predicted_at']==datetime(2026,1,11+i,8,tzinfo=timezone.utc)
        assert len(v['details']['local_demo']['idempotency_key'])==64
    assert pair==before
    checked=compare_records(stored(plans),plans,pair.identities,settings.destination(ROLES[2]),reference)
    assert [r['id'] for r in checked.records]==[701,702]
    checked.records[0]['details']['synthetic']=False
    assert checked.records[0]['details']['synthetic'] is True


@pytest.mark.parametrize('kind',['incomplete','abstained','duplicate','statistics','version','revision','digest','score_nan','mapping_duplicate','mapping_bool'])
def test_invalid_pair_rejected(pair,settings,reference,context,kind):
    result=pair.results[0]
    if kind=='incomplete': pair=replace(pair,results=pair.results[:1])
    elif kind=='abstained': pair=replace(pair,results=(Abstained(AbstentionCode.INVALID_INPUT,'DEMO-M-011',None,(),'test'),pair.results[1]))
    elif kind=='duplicate': pair=replace(pair,results=(result,result))
    elif kind=='statistics': pair=replace(pair,results=(replace(result,statistics=replace(result.statistics,mean=99)),pair.results[1]))
    elif kind=='version': pair=replace(pair,results=(replace(result,prediction=replace(result.prediction,model_version='p101-stat-v2')),pair.results[1]))
    elif kind=='digest': pair=replace(pair,results=(replace(result,dataset_sha256='0'*64),pair.results[1]))
    elif kind=='score_nan': pair=replace(pair,results=(replace(result,prediction=replace(result.prediction,score=float('nan'))),pair.results[1]))
    elif kind=='revision': context=replace(context,code_revision='0'*40)
    elif kind=='mapping_duplicate': pair=replace(pair,identities=replace(pair.identities,measurements=pair.identities.measurements[:-1]+(pair.identities.measurements[0],)))
    elif kind=='mapping_bool': pair=replace(pair,identities=replace(pair.identities,equipment_id=True))
    with pytest.raises(PredictionError): plans_for(pair,settings,reference,context)


def test_retry_new_attempt_returns_original_records(pair,settings,reference,context):
    plans=plans_for(pair,settings,reference,context)
    old=stored(plans)
    modified=[]
    for r in pair.results:
        d=r.prediction.details
        d.update(run_id='00000000-0000-4000-8000-000000000056',prepared_at='2026-10-27T00:00:00.000000Z')
        modified.append(replace(r,prediction=replace(r.prediction,details_json=json.dumps(d,ensure_ascii=False))))
    later=replace(context,run_id=d['run_id'],prepared_at=d['prepared_at'])
    new_plans=plans_for(replace(pair,results=tuple(modified)),settings,reference,later)
    assert [p.key_json for p in plans]==[p.key_json for p in new_plans]
    result=compare_records(old,new_plans,pair.identities,settings.destination(ROLES[2]),reference)
    assert result.disposition=='identical_retry'
    assert result.records[0]['details']==old[0]['details']
    assert result.records[0]['created_at']==context.prepared_at


@pytest.mark.parametrize('kind',['partial','duplicate','extra','score','alert','id_bool','created_at','target_time','mapping','metadata_float_id','hash','key','uuid','reason','schema','nonfinite','oversize','deep','unknown_field','missing_field','calculation'])
def test_stored_conflicts_and_invalid_states(pair,settings,reference,context,kind):
    plans=plans_for(pair,settings,reference,context)
    old=deepcopy(stored(plans))
    r=old[0]; d=r['details']
    if kind=='partial': old=old[:1]
    elif kind=='duplicate': old=(r,r)
    elif kind=='extra': old=old+(dict(r,id=999),)
    elif kind=='score': r['score']=1
    elif kind=='alert': r['is_alert']=1
    elif kind=='id_bool': r['id']=True
    elif kind=='created_at': r['created_at']=datetime(2020,1,1,tzinfo=timezone.utc)
    elif kind=='target_time': r['predicted_at']=datetime(2026,1,10,8,tzinfo=timezone.utc)
    elif kind=='mapping': r['measurement_id']=123
    elif kind=='metadata_float_id': d['local_demo']['sql_mapping']['equipment_id']=303.0
    elif kind=='hash': d['local_demo']['content_sha256']='0'*64
    elif kind=='key': d['local_demo']['idempotency_key']='0'*64
    elif kind=='uuid': d['local_demo']['instance_uuid']='00000000-0000-4000-8000-000000000057'
    elif kind=='reason': d['reason']='different'
    elif kind=='schema': d['schema_version']='unknown'
    elif kind=='nonfinite': d['calculation']['target']['value']=float('inf')
    elif kind=='oversize': d['reason']='x'*6001
    elif kind=='deep': d['local_demo']['unexpected']=[[[[[[[]]]]]]]
    elif kind=='unknown_field': r['unexpected']=1
    elif kind=='missing_field': r.pop('sensor_id')
    elif kind=='calculation': d['calculation']['cutoff_utc']='2026-01-11T08:02:00.000000Z'
    with pytest.raises(PredictionError): compare_records(old,plans,pair.identities,settings.destination(ROLES[2]),reference)


def test_coherent_existing_content_with_different_natural_identity_conflicts(pair,settings,reference,context):
    plans=plans_for(pair,settings,reference,context)
    other=replace(pair,identities=replace(pair.identities,equipment_id=909))
    old=stored(plans_for(other,settings,reference,context))
    with pytest.raises(PredictionError): compare_records(old,plans,pair.identities,settings.destination(ROLES[2]),reference)


class Result:
    def __init__(self,rows): self.rows=rows
    def mappings(self): return self
    def one(self): assert len(self.rows)==1; return self.rows[0]
    def __iter__(self): return iter(self.rows)


class FakeDatabase:
    def __init__(self,settings,rows):
        self.settings,self.rows=settings,rows
        self.records=[]; self.pending=[]; self.events=[]; self.next_id=701
        self.fail_second=False; self.partial_return=False; self.unique_conflict=False
        self.commit_failure=None; self.bad_guard=None

    def engine(self,url,**kwargs):
        db=self
        class FakeEngine:
            def connect(self): db.events.append('connect'); return FakeConnection(db,self)
            def dispose(self): db.events.append('dispose')
        engine=FakeEngine(); engine.url=url
        assert kwargs['hide_parameters'] is True and kwargs['connect_args']['sslmode']=='disable'
        return engine


class FakeConnection:
    def __init__(self,db,engine):
        self.db,self.engine,self.active=db,engine,False
        s=db.settings
        self.connection=SimpleNamespace(driver_connection=SimpleNamespace(info=SimpleNamespace(
            host=s.host,port=s.port,dbname=s.database,user=ROLES[2],get_parameters=lambda:{'sslmode':'disable'}),
            pgconn=SimpleNamespace(ssl_in_use=False)))
    def __enter__(self): return self
    def __exit__(self,*a): self.db.events.append('close')
    def in_transaction(self): return self.active
    def begin(self):
        conn=self; db=self.db
        class Transaction:
            def __enter__(self): conn.active=True; db.pending=[]; db.events.append('begin')
            def __exit__(self,typ,value,tb):
                conn.active=False
                if typ:
                    db.pending=[]; db.events.append('rollback'); return
                db.events.append('commit')
                if db.commit_failure!='not_committed': db.records.extend(db.pending)
                db.pending=[]
                if db.commit_failure: raise RuntimeError('Simulated lost commit response')
        return Transaction()

    def execute(self,statement,parameters=None):
        db=self.db; s=db.settings
        assert self.active
        if statement is provisioning.IDENTITY:
            return Result([dict(database=s.database,session_role=ROLES[2],effective_role=ROLES[2],
                server_address=s.server_address,server_port=5432,cluster=CLUSTER,encoding='UTF8',
                isolation='read committed',no_protected_schema=True,no_memberships=True,
                rolsuper=False,rolcreatedb=False,rolcreaterole=False,rolreplication=False,rolbypassrls=False)])
        if statement is reader.IDENTITY_SQL:
            return Result([dict(database=s.database,database_name=s.database,purpose='local-p101-functional-demo',
                session_role=ROLES[2],effective_role=ROLES[2],server_address=s.server_address,server_port=5432,
                isolation_level='read committed',encoding='UTF8',instance_uuid=s.instance_uuid,
                schema_revision=s.destination(ROLES[2]).schema_revision,installed_revision=s.destination(ROLES[2]).schema_revision,
                bootstrap_closed=True,no_protected_schema=True,limited_role=True,no_memberships=True,
                not_owner=True,source_read=True,sources_immutable=True)])
        if statement is service.WRITER_SQL:
            row=dict(fixture_sha256=FIXTURE_SHA256,bootstrap_sha256='1'*64,owner_closed=True,
                no_owner_session=True,prediction_rights=True,marker_immutable=True,unique_index=True,local_check=True)
            if db.bad_guard: row[db.bad_guard]=False
            return Result([row])
        if str(statement).startswith('SELECT pg_advisory_xact_lock'):
            assert parameters=={'key':provisioning.LOCK}; db.events.append('lock'); return Result([])
        if getattr(statement,'is_insert',False):
            assert statement.table is service.prediction_records
            db.events.append('insert_batch')
            if db.unique_conflict:
                raise IntegrityError('simulated',{},SimpleNamespace(sqlstate='23505'))
            compiled=statement.compile(dialect=postgresql.dialect())
            assert 'RETURNING' in str(compiled) and 'ON CONFLICT' not in str(compiled)
            for i in range(2):
                if i==1 and db.fail_second: raise RuntimeError('Simulated second-row failure')
                row={name:compiled.params[f'{name}_m{i}'] for name in FIELDS if name!='id'}
                db.pending.append(dict(row,id=db.next_id)); db.next_id+=1
            return Result(deepcopy(db.pending[:1] if db.partial_return else db.pending))
        assert getattr(statement,'is_select',False), 'No UPDATE/DELETE/DDL allowed'
        table=statement.get_final_froms()[0].name
        if table=='prediction_records':
            db.events.append('read_predictions'); return Result(deepcopy((db.records+db.pending)[:3]))
        assert table in ('companies','sites','equipments','sensors','measurements')
        db.events.append('read_source')
        return Result(deepcopy(getattr(db.rows,table)))


@pytest.fixture
def database(settings,rows,monkeypatch):
    db=FakeDatabase(settings,rows)
    monkeypatch.setattr(provisioning,'create_engine',db.engine)
    monkeypatch.setattr(provisioning,'read_secret',lambda *a:'test-only-private-secret-placeholder')
    return db


def run(database,reference,context,**kwargs):
    return service.run_predictions(database.settings,reference,context,execute=True,
        instance=database.settings.instance_uuid,**kwargs)


def test_one_transaction_real_ml_and_identical_retry(database,reference,context):
    original=deepcopy(database.rows)
    first=run(database,reference,context)
    assert first.disposition=='inserted' and len(database.records)==2
    assert database.events.count('begin')==database.events.count('commit')==1
    assert database.events.count('insert_batch')==1 and 'rollback' not in database.events
    assert database.events.index('lock')<database.events.index('read_source')<database.events.index('insert_batch')<database.events.index('commit')
    new=replace(context,run_id='00000000-0000-4000-8000-000000000058',prepared_at='2026-10-27T00:00:00.000000Z')
    retry=run(database,reference,new)
    assert retry.disposition=='identical_retry' and retry.records==first.records
    assert len(database.records)==2 and database.events.count('insert_batch')==1
    assert database.rows==original


@pytest.mark.parametrize('failure',['second_row','return_validation','unique','partial_existing','duplicate_existing','content_conflict'])
def test_no_partial_commit(database,reference,context,failure):
    if failure in ('partial_existing','duplicate_existing','content_conflict'):
        run(database,reference,context)
        if failure=='partial_existing': database.records=database.records[:1]
        elif failure=='duplicate_existing': database.records=[database.records[0],deepcopy(database.records[0])]
        else: database.records[0]['details']['local_demo']['content_sha256']='0'*64
        database.events=[]
    if failure=='second_row': database.fail_second=True
    if failure=='return_validation': database.partial_return=True
    if failure=='unique': database.unique_conflict=True
    before=deepcopy(database.records)
    with pytest.raises(PredictionError): run(database,reference,context)
    assert database.records==before and not database.pending
    assert 'rollback' in database.events and 'commit' not in database.events
    assert database.events.count('connect')==1


@pytest.mark.parametrize('applied',['committed','not_committed'])
def test_commit_uncertain_no_automatic_retry(database,reference,context,applied):
    database.commit_failure=applied
    with pytest.raises(PredictionError,match='COMMIT_UNCERTAIN'): run(database,reference,context)
    assert database.events.count('connect')==1 and database.events.count('commit')==1
    assert len(database.records)==(2 if applied=='committed' else 0)
    database.commit_failure=None
    outcome=run(database,reference,context)
    assert outcome.disposition==('identical_retry' if applied=='committed' else 'inserted')
    assert len(database.records)==2


@pytest.mark.parametrize('field',['owner_closed','no_owner_session','prediction_rights','marker_immutable','unique_index','local_check'])
def test_bad_writer_guard_before_calculation(database,reference,context,field):
    database.bad_guard=field
    with pytest.raises(PredictionError): run(database,reference,context)
    assert 'read_source' not in database.events and 'insert_batch' not in database.events


@pytest.mark.parametrize('change',['database','port','reader_role','missing_ack','missing_instance'])
def test_wrong_destination_or_execution_permission(database,reference,context,change):
    if change=='reader_role':
        with pytest.raises(PredictionError): service.guard_writer(None,database.settings.destination(ROLES[3]))
        return
    if change in ('database','port'):
        database.settings=replace(database.settings,**({'database':'industrial_predict_dev'} if change=='database' else {'port':5433}))
    with pytest.raises((PredictionError,ValueError)):
        service.run_predictions(database.settings,reference,context,
            execute=change!='missing_ack',instance=None if change=='missing_instance' else database.settings.instance_uuid)
    assert 'connect' not in database.events


def test_sql_source_divergence_is_not_replaced_from_json(database,reference,context):
    database.rows.measurements[0]['value']=99
    with pytest.raises(PredictionError): run(database,reference,context)
    assert 'insert_batch' not in database.events and database.records==[]


def test_imports_and_future_cli_have_no_side_effects():
    script='''
import builtins,socket,sqlalchemy,psycopg,sys
def forbidden(*a,**k): raise AssertionError('No automatic connection/configuration allowed')
sqlalchemy.create_engine=forbidden
psycopg.connect=forbidden
socket.create_connection=forbidden
socket.socket.connect=forbidden
original=builtins.__import__
def guarded(name,*a,**k):
    if name.startswith(('app.core','app.models','app.services','app.p101_postgres')): forbidden()
    return original(name,*a,**k)
builtins.__import__=guarded
import app.p101_local_demo.run_predictions
assert 'app.core.database' not in sys.modules
print('safe')
'''
    env=dict(os.environ,PYTHONPATH=str(ROOT/'backend'),PYTHONDONTWRITEBYTECODE='1',DATABASE_URL='unused-test-sentinel')
    result=subprocess.run([sys.executable,'-B','-c',script],env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    assert result.stdout.strip()=='safe'
    tree=ast.parse((ROOT/'backend/app/p101_local_demo/prediction_persistence.py').read_text())
    assert not any(isinstance(n,ast.Attribute) and n.attr in ('commit','rollback','create_all','update','delete') for n in ast.walk(tree))
