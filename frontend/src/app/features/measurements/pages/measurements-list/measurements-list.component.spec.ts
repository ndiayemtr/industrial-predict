import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { MEASUREMENT_ROUTES } from '../../measurements.routes';
import { MeasurementsListComponent } from './measurements-list.component';

const company={id:7,name:'Entreprise test',code:'ENT',description:null,created_at:'',updated_at:''};
const site={...company,id:9,company_id:7,name:'Usine 日本'};
const equipment={...company,id:12,site_id:9,equipment_type:'pump',status:'operational',criticality:'high',name:'Pompe'};
const sensor={...company,id:17,equipment_id:12,sensor_type:'temperature',unit:'°C',status:'inactive',name:'Palier'};
const row={id:23,sensor_id:17,timestamp:'2026-10-22T17:30:00.123456+05:30',value:-2.5,quality:'missing'};
const page={items:[row],total:21,page:1,page_size:20,pages:2};
const catalog=(items:unknown[])=>({items,total:items.length,page:1,page_size:50,pages:1});
describe('Measurements list, four selections and applied URL',()=>{
  let http:HttpTestingController,h:RouterTestingHarness,c:MeasurementsListComponent;
  const root=()=>h.routeNativeElement!;
  const read=(path:string)=>http.expectOne(req=>req.url==='/api/v1/'+path);
  const params=()=>TestBed.inject(Router).parseUrl(TestBed.inject(Router).url).queryParams;
  beforeEach(()=>{TestBed.configureTestingModule({providers:[provideHttpClient(),provideHttpClientTesting(),provideRouter([{path:'measurements',children:MEASUREMENT_ROUTES}])]});http=TestBed.inject(HttpTestingController);});
  afterEach(()=>{try{http.expectNone(req=>req.method!=='GET');http.verify();}finally{TestBed.resetTestingModule();}});
  async function settle(){h.fixture.detectChanges();TestBed.tick();await h.fixture.whenStable();h.fixture.detectChanges();}
  async function open(path='/measurements'){h=await RouterTestingHarness.create();c=await h.navigateByUrl(path,MeasurementsListComponent);await settle();}
  function chain(){read('sensors/17').flush(sensor);read('equipments/12').flush(equipment);read('sites/9').flush(site);read('companies/7').flush(company);}
  function catalogs(){read('sites').flush(catalog([site]));read('equipments').flush(catalog([equipment]));read('sensors').flush(catalog([sensor]));}
  async function ready(extra=''){await open('/measurements?company_id=7&site_id=9&equipment_id=12&sensor_id=17'+extra);read('companies').flush(catalog([company]));chain();await settle();catalogs();read('measurements').flush(page);await settle();}
  it('never auto-selects a singleton catalogue and waits for the fourth explicit choice',async()=>{
    await open();read('companies').flush(catalog([company]));await settle();
    expect(root().querySelectorAll('[id$="-help"]')).toHaveLength(5);expect(c.company.value).toBeNull();expect(c.site.disabled).toBe(true);expect(c.sensor.disabled).toBe(true);http.expectNone(()=>true);
    c.company.setValue(7);await settle();expect(root().querySelector('#company-help')).not.toBeNull();read('companies/7').flush(company);await settle();read('sites').flush(catalog([site]));await settle();
    expect(root().querySelector('#company-help')).toBeNull();expect(root().querySelector('#site-help')).not.toBeNull();expect(c.site.value).toBeNull();c.site.setValue(9);await settle();read('sites/9').flush(site);read('companies/7').flush(company);await settle();read('equipments').flush(catalog([equipment]));await settle();
    expect(root().querySelector('#site-help')).toBeNull();expect(root().querySelector('#equipment-help')).not.toBeNull();c.equipment.setValue(12);await settle();read('equipments/12').flush(equipment);read('sites/9').flush(site);read('companies/7').flush(company);await settle();read('sensors').flush(catalog([sensor]));await settle();
    expect(root().querySelector('#equipment-help')).toBeNull();expect(root().querySelector('#sensor-help')).not.toBeNull();expect(c.sensor.value).toBeNull();expect(c.sensor.enabled).toBe(true);http.expectNone(()=>true);
    c.sensor.setValue(17);await settle();chain();read('measurements').flush(page);await settle();expect(c.facade.state().status).toBe('success');expect(root().querySelectorAll('.parents [id$="-help"]')).toHaveLength(0);
  });
  it('renders real microseconds, negative values, quality and current unit with an active detail link',async()=>{
    await ready();expect([...root().querySelectorAll('thead th')].map(el=>el.textContent)).toEqual(['Horodatage UTC','Valeur','Unité actuelle','Qualité','Référence']);
    expect(root().querySelector('time')?.textContent).toBe('22/10/2026 à 12:00:00.123456 UTC');expect(root().querySelector('time')?.getAttribute('datetime')).toBe(row.timestamp);
    expect(root().querySelector('tbody')?.textContent).toContain('-2,5');expect(root().querySelector('tbody')?.textContent).toContain('Manquante');expect(root().querySelector('tbody')?.textContent).toContain('°C');
    expect(root().querySelector('a[href*="/new"]')).toBeNull();
    expect(root().querySelector('tbody a')?.getAttribute('href')).toContain('/measurements/23?');
    expect(root().querySelector('tbody a')?.getAttribute('tabindex')).not.toBe('-1');expect(root().querySelector('.table-scroll')?.getAttribute('tabindex')).toBe('0');
    expect(root().querySelectorAll('label[for]')).toHaveLength(12);
  });
  it('completes sensor-only context without duplicate measurement reads and preserves unknown params/fragment',async()=>{
    await open('/measurements?sensor_id=17&return_sensor_search=TEMP&extra=yes#history');read('companies').flush(catalog([company]));chain();await settle();catalogs();read('measurements').flush(page);await settle();
    expect(params()).toMatchObject({company_id:'7',site_id:'9',equipment_id:'12',sensor_id:'17',page:'1',page_size:'20',return_sensor_search:'TEMP',extra:'yes'});
    expect(TestBed.inject(Router).url).toContain('#history');http.expectNone(()=>true);
  });
  it.each(['company_id','site_id','equipment_id','sensor_id'])('blocks invalid %s in URL without loading any industrial reference',async key=>{
    await open('/measurements?'+key+'=0');read('companies').flush(catalog([company]));expect(root().textContent).toContain('périmètre');http.expectNone(()=>true);
  });
  it.each(['2026-01-01T12:00:00','invalid','2026-01-01T00:00:00.1234567Z'])('blocks invalid URL period %s before parent requests',async raw=>{
    await open('/measurements?sensor_id=17&start_time='+encodeURIComponent(raw));read('companies').flush(catalog([company]));expect(root().textContent).toContain('Période invalide');http.expectNone(()=>true);
  });
  it('rejects an invalid quality without dropping the filter and allows explicit repair',async()=>{
    await open('/measurements?sensor_id=17&quality=UNKNOWN');read('companies').flush(catalog([company]));http.expectNone(()=>true);
    c.quality.setValue('good');await settle();chain();await settle();catalogs();read('measurements').flush(page);await settle();expect(params()['quality']).toBe('good');
  });
  it('normalizes pagination before reading and keeps valid URL sizes outside the selector defaults',async()=>{
    await ready('&page=0&page_size=101');expect(params()).toMatchObject({page:'1',page_size:'20'});
    await TestBed.inject(Router).navigateByUrl('/measurements?company_id=7&site_id=9&equipment_id=12&sensor_id=17&page_size=1');await settle();
    const req=read('measurements');expect(req.request.params.get('page_size')).toBe('1');req.flush({...page,page_size:1});await settle();expect(c.sizes()).toContain(1);
  });
  it('applies UTC controls explicitly without sending parents or unapplied drafts',async()=>{
    await ready();const start='2026-10-22T12:00:00.123456Z',end='2026-10-22T12:00:00.123457Z';
    c.start.setValue({date:'2026-10-22',time:'12:00:00',fraction:'123456'});c.end.setValue({date:'2026-10-22',time:'12:00:00',fraction:'123457'});
    http.expectNone(()=>true);c.applyPeriod();await settle();const req=read('measurements');
    expect(req.request.params.get('start_time')).toBe(start);expect(req.request.params.get('end_time')).toBe(end);
    expect(req.request.params.keys().sort()).toEqual(['sensor_id','page','page_size','start_time','end_time'].sort());req.flush(page);await settle();expect(params()['start_time']).toBe(start);
    c.start.controls.date.setValue('draft');c.quality.setValue('suspect');await settle();const next=read('measurements');expect(next.request.params.get('start_time')).toBe(start);expect(next.request.params.get('quality')).toBe('suspect');next.flush(page);await settle();
  });
  it('rejects equal instants and retains applied results without HTTP',async()=>{
    await ready();c.start.setValue({date:'2026-01-01',time:'00:00:00',fraction:''});c.end.setValue(c.start.getRawValue());c.applyPeriod();await settle();
    expect(c.periodError()).toContain('Période invalide');expect(params()['start_time']).toBeUndefined();expect(c.facade.state().status).toBe('success');http.expectNone(()=>true);
    expect(root().querySelector('#measurements-start-date')?.getAttribute('aria-invalid')).toBe('true');
  });
  it.each(['good','suspect','bad','missing','estimated'] as const)('sends exact quality %s and starts at page 1',async quality=>{
    await ready('&page=2');c.quality.setValue(quality);await settle();const req=read('measurements');expect(req.request.params.get('quality')).toBe(quality);expect(req.request.params.get('page')).toBe('1');req.flush(page);await settle();
  });
  it('changes pages without reloading parents or sending unsubmitted dates',async()=>{
    await ready();c.start.controls.date.setValue('draft');c.changePage(2);await settle();const req=read('measurements');expect(req.request.params.get('page')).toBe('2');expect(req.request.params.has('start_time')).toBe(false);req.flush({...page,page:2});await settle();http.expectNone(()=>true);
  });
  it('recovers an out-of-range page only on explicit action',async()=>{
    await open('/measurements?sensor_id=17&page=9');read('companies').flush(catalog([company]));chain();await settle();catalogs();read('measurements').flush({...page,items:[],page:9});await settle();
    expect(root().textContent).toContain('Page hors plage');http.expectNone(()=>true);c.recoverPage();await settle();const req=read('measurements');expect(req.request.params.get('page')).toBe('2');req.flush(page);await settle();
  });
  it('loads catalogue continuation with deduplication and preserves loaded options after a failed next page',async()=>{
    await ready();c.companies.set({...c.companies(),pages:2,total:51});c.moreCompanies();read('companies').flush({}, {status:500,statusText:'Failure'});await settle();
    expect(c.companyOptions()).toHaveLength(1);expect(root().querySelector('#company-help')).toBeNull();expect(root().textContent).toContain('Le catalogue ne peut pas être chargé.');c.retryCompanies();const req=read('companies');expect(req.request.params.get('page')).toBe('2');req.flush({...catalog([company,{...company,id:8}]),page:2,pages:2,total:51});await settle();expect(c.companyOptions()).toHaveLength(2);
    c.sensors.set({...c.sensors(),pages:2,total:51});c.moreSensors();const more=read('sensors');expect(more.request.params.get('equipment_id')).toBe('12');expect(more.request.params.has('status')).toBe(false);more.flush({...catalog([sensor,{...sensor,id:18}]),page:2,pages:2,total:51});await settle();expect(c.sensorOptions()).toHaveLength(2);
  });
  it('rejects a sensor catalogue belonging to another equipment',async()=>{
    await open('/measurements?equipment_id=12');read('companies').flush(catalog([company]));read('equipments/12').flush(equipment);read('sites/9').flush(site);read('companies/7').flush(company);await settle();
    read('sites').flush(catalog([site]));read('equipments').flush(catalog([equipment]));read('sensors').flush(catalog([{...sensor,equipment_id:99}]));await settle();expect(c.sensors().status).toBe('error');expect(c.sensorOptions()).toHaveLength(0);http.expectNone(()=>true);
  });
  it('cancels obsolete catalogues and clears all descendants when a parent changes',async()=>{
    await ready();c.sensors.set({...c.sensors(),pages:2});c.moreSensors();const old=read('sensors');c.company.setValue(null);await settle();expect(old.cancelled).toBe(true);expect(c.sensor.value).toBeNull();expect(c.sensor.disabled).toBe(true);expect(root().querySelectorAll('.parents [id$="-help"]')).toHaveLength(4);expect(root().querySelector('table')).toBeNull();http.expectNone(()=>true);
  });
  it('removes previously resolved context immediately while a contradictory URL is checked',async()=>{
    await ready();await TestBed.inject(Router).navigateByUrl('/measurements?company_id=99&site_id=9&equipment_id=12&sensor_id=17');await settle();
    expect(c.facade.sensor()).toBeNull();expect(root().querySelector('.context')).toBeNull();expect(root().querySelector('table')).toBeNull();
    read('sensors/17').flush(sensor);read('equipments/12').flush(equipment);read('sites/9').flush(site);await settle();
    expect(c.facade.state().status).toBe('error');http.expectNone(()=>true);
  });
  it('distinguishes unfiltered empty history from filtered empty results',async()=>{
    await ready();c.facade.load({...c.facade.query()!,page:2});read('measurements').flush({...page,items:[],total:0,pages:0});await settle();expect(root().textContent).toContain('Aucune mesure');expect(root().querySelector('.pagination')).toBeNull();
    c.quality.setValue('bad');await settle();read('measurements').flush({...page,items:[],total:0,pages:0});await settle();expect(root().textContent).toContain('Aucun résultat');
  });
  it('restores original offset and microseconds, retaining them when Apply is used without editing',async()=>{
    const raw='2026-10-22T17:30:00.123456+05:30';await ready('&start_time='+encodeURIComponent(raw));
    expect(c.start.getRawValue()).toEqual({date:'2026-10-22',time:'12:00:00',fraction:'123456'});
    c.applyPeriod();await settle();expect(params()['start_time']).toBe(raw);http.expectNone(()=>true);
    c.end.setValue({date:'2026-10-23',time:'12:00:00',fraction:''});c.applyPeriod();await settle();
    const req=read('measurements');expect(req.request.params.get('start_time')).toBe(raw);expect(req.request.params.get('end_time')).toBe('2026-10-23T12:00:00Z');req.flush(page);await settle();
    c.clearFilters();await settle();const cleared=read('measurements');expect(cleared.request.params.has('start_time')).toBe(false);expect(cleared.request.params.has('end_time')).toBe(false);cleared.flush(page);await settle();
    expect(c.start.getRawValue()).toEqual({date:'',time:'',fraction:''});expect(params()['sensor_id']).toBe('17');
  });
  it('binds native calendar and time events and preserves the six fractional digits',async()=>{
    await ready();
    const edit=(id:string,value:string)=>{const input=root().querySelector<HTMLInputElement>('#'+id)!;input.value=value;input.dispatchEvent(new Event('input'));};
    expect(root().querySelector('#measurements-start-date')?.getAttribute('type')).toBe('date');
    expect(root().querySelector('#measurements-start-time')?.getAttribute('step')).toBe('1');
    edit('measurements-start-date','2026-02-28');edit('measurements-start-time','23:59:59');edit('measurements-start-fraction','000001');
    root().querySelector('form')!.dispatchEvent(new Event('submit',{cancelable:true}));await settle();
    const req=read('measurements');expect(req.request.params.get('start_time')).toBe('2026-02-28T23:59:59.000001Z');req.flush(page);await settle();
    expect(c.start.controls.fraction.value).toBe('000001');
    for(const label of root().querySelectorAll('label[for]'))expect(root().querySelector('#'+label.getAttribute('for'))).not.toBeNull();
    expect(root().querySelector('input[tabindex="-1"]')).toBeNull();
  });
  it.each([
    {date:'2026-02-30',time:'12:00:00',fraction:''},
    {date:'2026-02-28',time:'',fraction:''},
    {date:'',time:'12:00:00',fraction:''},
    {date:'2026-02-28',time:'12:00:00',fraction:'1234567'},
    {date:'2026-02-28',time:'12:00:00',fraction:' 1'},
  ])('blocks invalid bound %j before HTTP and keeps draft values',async parts=>{
    await ready();c.start.setValue(parts);c.applyPeriod();await settle();expect(c.periodError()).toContain('Période invalide');expect(c.start.getRawValue()).toEqual(parts);http.expectNone(()=>true);
  });
  it('does not hide hints merely because URL identifiers are present or a reference fails',async()=>{
    await open('/measurements?company_id=7&site_id=9&equipment_id=12&sensor_id=17');read('companies').flush(catalog([company]));
    expect(root().querySelectorAll('.parents [id$="-help"]')).toHaveLength(4);
    read('sensors/17').flush({}, {status:404,statusText:'Missing'});await settle();
    expect(root().querySelectorAll('.parents [id$="-help"]')).toHaveLength(4);expect(root().textContent).toContain('Chargement impossible');http.expectNone(()=>true);
  });

  it('blocks a partially typed native date even when the browser exposes an empty value',async()=>{
    await ready();const input=root().querySelector<HTMLInputElement>('#measurements-start-date')!;
    // jsdom does not implement partial native picker editing; simulate the browser validity contract.
    Object.defineProperty(input,'validity',{configurable:true,get:()=>({valid:false,badInput:true})});
    c.applyPeriod();await settle();expect(c.periodError()).toContain('Période invalide');http.expectNone(()=>true);
  });

  it('navigates list to detail and back with the applied snapshot, repeats and fragment, ignoring a temporal draft',async()=>{
    const raw='2026-10-22T17:30:00.123456+05:30';
    await ready('&page=2&page_size=50&quality=missing&start_time='+encodeURIComponent(raw)+'&extra=a&extra=b&return_sensor_search=TEMP#history');
    c.start.controls.fraction.setValue('999999');
    const detail=root().querySelector<HTMLAnchorElement>('tbody a')!;expect(detail.getAttribute('href')).toContain('/measurements/23?');detail.click();await settle();
    read('measurements/23').flush(row);chain();await settle();
    const back=root().querySelector<HTMLAnchorElement>('.measurement-back')!;const router=TestBed.inject(Router);const snapshot=router.parseUrl(back.getAttribute('href')!);
    expect(snapshot.queryParams).toMatchObject({company_id:'7',site_id:'9',equipment_id:'12',sensor_id:'17',quality:'missing',page:'2',page_size:'50',start_time:raw,extra:['a','b'],return_sensor_search:'TEMP'});expect(snapshot.fragment).toBe('history');
    back.click();await settle();read('companies').flush(catalog([company]));chain();await settle();catalogs();const req=read('measurements');
    expect(req.request.params.get('page')).toBe('2');expect(req.request.params.get('page_size')).toBe('50');expect(req.request.params.get('quality')).toBe('missing');expect(req.request.params.get('start_time')).toBe(raw);
    expect(req.request.params.has('company_id')).toBe(false);req.flush({...page,page:2,page_size:50});await settle();expect(root().querySelector('time')).not.toBeNull();
  });

});
