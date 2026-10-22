import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { MeasurementsListFacade } from './measurements-list.facade';

const company = { id:7,name:'Entreprise',code:'ENT',description:null,created_at:'',updated_at:'' };
const site = { ...company,id:9,company_id:7 };
const equipment = { ...company,id:12,site_id:9,equipment_type:'pump',status:'operational',criticality:'high' };
const sensor = { ...company,id:17,equipment_id:12,sensor_type:'temperature',unit:'°C',status:'inactive' };
const row = { id:23,sensor_id:17,timestamp:'2026-10-22T12:00:00.123456Z',value:-2.5,quality:'missing' };
const page = { items:[row],total:1,page:1,page_size:20,pages:1 };
const query = { company_id:7,site_id:9,equipment_id:12,sensor_id:17,page:1,page_size:20 };
describe('Measurements facade verified scope and cancellation', () => {
  let facade: MeasurementsListFacade, http: HttpTestingController;
  const read = (path:string) => http.expectOne(req => req.url === '/api/v1/'+path);
  beforeEach(() => { TestBed.configureTestingModule({ providers:[provideHttpClient(),provideHttpClientTesting(),MeasurementsListFacade] }); facade=TestBed.inject(MeasurementsListFacade); http=TestBed.inject(HttpTestingController); });
  afterEach(() => { try { http.expectNone(req => req.method !== 'GET'); http.verify(); } finally { TestBed.resetTestingModule(); } });
  function chain() { read('sensors/17').flush(sensor); read('equipments/12').flush(equipment); read('sites/9').flush(site); http.expectNone(req=>req.url==='/api/v1/measurements'); read('companies/7').flush(company); }
  function ready() { facade.load(query); chain(); read('measurements').flush(page); }
  it('waits for explicit descendants and never selects the first available child', () => {
    facade.load({page:1,page_size:20}); expect(facade.state().status).toBe('idle'); http.expectNone(()=>true);
    facade.load({company_id:7,page:1,page_size:20}); read('companies/7').flush(company); expect(facade.sensor()).toBeNull(); http.expectNone(()=>true);
    facade.load({equipment_id:12,page:1,page_size:20}); read('equipments/12').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company);
    expect(facade.state().status).toBe('idle'); http.expectNone(()=>true);
  });
  it('resolves a sensor-only URL and waits for the real company before GET', () => {
    facade.load({sensor_id:17,page:1,page_size:20}); chain();
    const req=read('measurements'); expect(Object.fromEntries(req.request.params.keys().map(k=>[k,req.request.params.get(k)]))).toEqual({sensor_id:'17',page:'1',page_size:'20'});
    req.flush(page); expect(facade.query()).toEqual(query); expect(facade.sensor()?.status).toBe('inactive'); expect(facade.state().status).toBe('success');
  });
  it.each(['equipment','site','company'])('rejects contradictory %s ids without widening scope', level => {
    facade.load({...query,[level+'_id']:99}); read('sensors/17').flush(sensor);
    if(level!=='equipment') read('equipments/12').flush(equipment);
    if(level==='company') read('sites/9').flush(site);
    expect(facade.state().status).toBe('error'); expect(facade.sensor()).toBeNull(); http.expectNone(()=>true);
  });
  it.each(['sensor','equipment','site','company'])('rejects a mismatched %s response', level => {
    facade.load(query);
    if(level==='sensor') read('sensors/17').flush({...sensor,id:18});
    else { read('sensors/17').flush(sensor); if(level==='equipment') read('equipments/12').flush({...equipment,id:13});
      else { read('equipments/12').flush(equipment); if(level==='site') read('sites/9').flush({...site,id:10}); else { read('sites/9').flush(site); read('companies/7').flush({...company,id:8}); } } }
    expect(facade.state().status).toBe('error'); http.expectNone(()=>true);
  });
  it.each([0,403,404,500])('handles parent HTTP %s and only allows transient retry', status => {
    facade.load(query); const req=read('sensors/17'); if(status) req.flush({}, {status,statusText:'Failure'}); else req.error(new ProgressEvent('error'));
    expect(facade.state()).toMatchObject({status:'error',retryable:status===0||status===500}); http.expectNone(()=>true);
  });
  it('does not load any reference or measurements for an invalid period', () => {
    facade.load({...query,start_time:'2026-01-01T00:00Z',end_time:'2026-01-01T00:00Z'}); expect(facade.state()).toMatchObject({status:'error',retryable:false}); http.expectNone(()=>true);
  });
  it('only reloads Measurements for filter/page changes on an already verified chain', () => {
    ready(); facade.load({...query,quality:'estimated',page:2,page_size:50,start_time:'2026-01-01T00:00:00.123456Z'});
    const req=read('measurements'); expect(req.request.params.keys().sort()).toEqual(['sensor_id','quality','page','page_size','start_time'].sort());
    req.flush({...page,items:[],page:2,total:1}); expect(facade.state().status).toBe('success'); http.expectNone(()=>true);
  });
  it('cancels obsolete parent and measurement reads and clears their results', () => {
    facade.load(query); const obsolete=read('sensors/17'); facade.load({...query,sensor_id:18}); expect(obsolete.cancelled).toBe(true);
    read('sensors/18').flush({...sensor,id:18}); read('equipments/12').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company);
    const pending=read('measurements'); facade.load(null); expect(pending.cancelled).toBe(true); expect(facade.state().status).toBe('idle'); expect(facade.sensor()).toBeNull();
  });
  it.each([400,422,500])('handles Measurements HTTP %s without fabricating results', status=>{
    ready(); facade.load({...query,page:2}); read('measurements').flush({}, {status,statusText:'Failure'});
    expect(facade.state()).toMatchObject({status:'error',retryable:status===500});
  });
  it('rejects foreign sensor responses and non-finite values',()=>{
    ready(); facade.load(query); read('measurements').flush({...page,items:[{...row,sensor_id:99}]}); expect(facade.state()).toMatchObject({status:'error',retryable:false});
    facade.load(query); read('measurements').flush({...page,items:[{...row,value:null}]}); expect(facade.state()).toMatchObject({status:'error',retryable:false});
  });
  it('distinguishes empty history and retries only on request',()=>{
    facade.load(query); chain(); read('measurements').flush({...page,items:[],total:0,pages:0}); expect(facade.state().status).toBe('empty');
    facade.load(query); read('measurements').error(new ProgressEvent('error')); facade.retry(); read('measurements').flush(page); expect(facade.state().status).toBe('success');
  });
});
