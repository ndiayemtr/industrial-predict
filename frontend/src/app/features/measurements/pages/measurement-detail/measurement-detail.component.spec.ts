import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { MEASUREMENT_ROUTES } from '../../measurements.routes';
import { MeasurementDetailComponent } from './measurement-detail.component';

const measurement={id:23,sensor_id:17,timestamp:'2026-10-22T17:30:00.123456+05:30',value:-2.5,quality:'missing'};
const company={id:7,name:'Entreprise réelle',code:'ENT',description:null,created_at:'',updated_at:''};
const site={...company,id:9,company_id:7,name:'Site réel'};
const equipment={...company,id:12,site_id:9,name:'Pompe réelle',equipment_type:'pump',status:'operational',criticality:'high'};
const sensor={...company,id:17,equipment_id:12,name:'Capteur réel',sensor_type:'temperature',unit:'°C',status:'inactive'};
const context='company_id=7&site_id=9&equipment_id=12&sensor_id=17&quality=missing&start_time=2026-10-22T17%3A30%3A00.123456%2B05%3A30&end_time=2026-10-23T00%3A00%3A00.000001Z&page=3&page_size=50';
const refPaths=['sensors/17','equipments/12','sites/9','companies/7'];
const refData=[sensor,equipment,site,company];
const refKeys=['sensor','equipment','site','company'];

describe('Measurement read-only detail and actual industrial references',()=>{
  let http:HttpTestingController,h:RouterTestingHarness,c:MeasurementDetailComponent;
  const root=()=>h.routeNativeElement!;
  const read=(path:string)=>http.expectOne('/api/v1/'+path);
  beforeEach(()=>{TestBed.configureTestingModule({providers:[provideHttpClient(),provideHttpClientTesting(),provideRouter([{path:'measurements',children:MEASUREMENT_ROUTES}])]});http=TestBed.inject(HttpTestingController);});
  afterEach(()=>{try{http.expectNone(req=>req.method!=='GET');http.verify();}finally{TestBed.resetTestingModule();}});
  async function settle(){h.fixture.detectChanges();TestBed.tick();await h.fixture.whenStable();h.fixture.detectChanges();}
  async function open(url='/measurements/23'){h=await RouterTestingHarness.create();c=await h.navigateByUrl(url,MeasurementDetailComponent);await settle();}
  function parents(){refPaths.forEach((path,index)=>read(path).flush(refData[index]));}
  async function loaded(url='/measurements/23'){await open(url);read('measurements/23').flush(measurement);parents();await settle();}
  const fieldValues=()=>[...root().querySelectorAll('.measurement-fields > div')].map(el=>[el.querySelector('dt')!.textContent!,el.querySelector('dd')!.textContent!.trim()]);

  it('renders exactly the five real fields with explicit UTC and original ISO source',async()=>{
    await loaded();expect(fieldValues().map(([label])=>label)).toEqual(['Identifiant de la mesure','Identifiant du capteur','Horodatage UTC','Valeur','Qualité déclarée']);
    expect(root().querySelector('time')?.textContent).toBe('22/10/2026 à 12:00:00.123456 UTC');expect(root().querySelector('time')?.getAttribute('datetime')).toBe(measurement.timestamp);
    expect(root().querySelector('.source-timestamp')?.textContent).toBe(measurement.timestamp);expect(root().querySelector('.measurement-value')?.textContent).toBe('-2,5');
    expect(root().textContent).toContain('Manquante');expect(root().textContent).toContain('ne certifie pas la fiabilité physique');
    expect(root().querySelector('.sensor-unit')?.textContent).toBe('°C');expect(root().textContent).toContain('ne constitue pas une unité historique garantie');
    expect(root().querySelectorAll('h1')).toHaveLength(1);expect(root().querySelector('form,input,select,button')).toBeNull();expect(root().textContent).not.toMatch(/Modifier|Supprimer|Création|Dernière modification|Prédiction/);
    const link=root().querySelector<HTMLAnchorElement>('.sensor-reference')!;expect(link.getAttribute('href')).toBe('/sensors/17?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20');link.focus();expect(document.activeElement).toBe(link);
  });
  it('reads only real parent ids sequentially and preserves data and return context during resolution',async()=>{
    await open('/measurements/23?company_id=99&site_id=88&equipment_id=77&sensor_id=66&page=4&page_size=1');
    http.expectNone(req=>req.url.includes('/sensors/'));const request=read('measurements/23');expect(request.request.params.keys()).toHaveLength(0);request.flush(measurement);await settle();
    expect(root().querySelector('.measurement-value')?.textContent).toBe('-2,5');expect(root().querySelector('.sensor-reference')).toBeNull();expect(root().textContent).toContain('Chargement du capteur réel');
    read('sensors/17').flush(sensor);await settle();expect(root().querySelector('.sensor-reference')?.getAttribute('href')).toBe('/sensors/17');
    read('equipments/12').flush(equipment);await settle();read('sites/9').flush(site);await settle();read('companies/7').flush(company);await settle();
    expect(root().querySelector('.context-notice')?.textContent).toContain('conservé pour revenir à la liste');
    expect(root().querySelector('.measurement-back')?.getAttribute('href')).toBe('/measurements?company_id=99&site_id=88&equipment_id=77&sensor_id=66&page=4&page_size=1');http.expectNone(()=>true);
  });
  it('preserves raw URL filters, microseconds, offsets, repeats, return params and fragment without parent reads from URL',async()=>{
    await loaded('/measurements/23?'+context+'&extra=a&extra=b&return_sensor_search=TEMP#history');
    const link=root().querySelector<HTMLAnchorElement>('.measurement-back')!;const tree=TestBed.inject(Router).parseUrl(link.getAttribute('href')!);
    expect(tree.queryParams).toMatchObject({company_id:'7',site_id:'9',equipment_id:'12',sensor_id:'17',quality:'missing',start_time:measurement.timestamp,end_time:'2026-10-23T00:00:00.000001Z',page:'3',page_size:'50',extra:['a','b'],return_sensor_search:'TEMP'});expect(tree.fragment).toBe('history');
    await TestBed.inject(Router).navigate([], {queryParams:{quality:'good'},queryParamsHandling:'merge'});await settle();http.expectNone(()=>true);expect(root().querySelector('.measurement-back')?.getAttribute('href')).toContain('quality=good');
  });
  it('keeps invalid return filters intact without using or normalizing them as measurement reads',async()=>{
    await loaded('/measurements/23?sensor_id=0&start_time=invalid&page=0&page_size=200');
    expect(root().querySelector('.measurement-back')?.getAttribute('href')).toBe('/measurements?sensor_id=0&start_time=invalid&page=0&page_size=200');http.expectNone(()=>true);
  });
  it('uses only bounded separate Sensors return parameters for the Sensor link',async()=>{
    await loaded('/measurements/23?'+context+'&return_sensor_company_id=8&return_sensor_site_id=10&return_sensor_equipment_id=13&return_sensor_page=4&return_sensor_page_size=50&return_sensor_status=inactive&return_sensor_search=TEMP');
    expect(c.sensorQuery()).toEqual({company_id:8,site_id:10,equipment_id:13,page:4,page_size:50,status:'inactive',search:'TEMP'});
    expect(c.sensorQuery()['quality']).toBeUndefined();expect(c.sensorQuery()['start_time']).toBeUndefined();
  });
  it('falls back to real parents if a Sensors return snapshot is invalid',async()=>{
    await loaded('/measurements/23?return_sensor_company_id=0&return_sensor_page_size=999&returnUrl=https://example.invalid');
    expect(c.sensorQuery()).toEqual({company_id:7,site_id:9,equipment_id:12,page:1,page_size:20});expect(root().querySelector('a[href^="https://"]')).toBeNull();
  });
  it.each(['0','-1','abc','new','1.5','1e2','9007199254740992'])('rejects invalid id %s without HTTP',async id=>{
    await open('/measurements/'+id);expect(root().textContent).toContain('Identifiant invalide');http.expectNone(()=>true);
  });
  it.each([0,400,401,403,404,422,500])('handles Measurement HTTP %s with manual transient retry only',async status=>{
    await open();const req=read('measurements/23');if(status===0)req.error(new ProgressEvent('error'));else req.flush({}, {status,statusText:'Error'});await settle();
    expect(c.state()).toMatchObject({status:'error',retryable:status===0||status>=500});expect(root().querySelector('dl')).toBeNull();if(status===404)expect(root().textContent).toContain('Mesure introuvable (404)');
    c.retry();if(status===0||status>=500){read('measurements/23').flush(measurement);parents();await settle();expect(c.state().status).toBe('success');}else http.expectNone(()=>true);
  });
  it.each([0,-0,-2.5,1e-7,123456.789,1e25])('preserves numerical value %s without rounding',async value=>{
    await open();read('measurements/23').flush({...measurement,value});parents();await settle();expect(root().querySelector('.measurement-value')?.textContent).toBe((Object.is(value,-0)?'-0':String(value)).replace('.',','));
  });
  it.each([null,true,'2',NaN,Infinity])('rejects invalid numeric value %s rather than displaying zero',async value=>{
    await open();read('measurements/23').flush({...measurement,value});await settle();expect(c.state().status).toBe('error');expect(root().querySelector('.measurement-value')).toBeNull();http.expectNone(()=>true);
  });
  it.each(['good','suspect','bad','missing','estimated'])('renders declared quality %s consistently with the list',async quality=>{
    await open();read('measurements/23').flush({...measurement,quality});parents();await settle();expect(fieldValues()).toContainEqual(['Qualité déclarée',c.qualityLabels[quality as keyof typeof c.qualityLabels]]);
  });
  it.each([{id:99},{sensor_id:0},{timestamp:'2026-10-22T12:00:00'},{quality:'UNKNOWN'}])('rejects a broken Measurement contract %j before parent reads',async override=>{
    await open();read('measurements/23').flush({...measurement,...override});await settle();expect(c.state().status).toBe('error');http.expectNone(()=>true);
  });
  it.each([0,1,2,3])('keeps the Measurement and already resolved parents when reference %s fails',async index=>{
    await open();read('measurements/23').flush(measurement);for(let n=0;n<index;n++)read(refPaths[n]).flush(refData[n]);read(refPaths[index]).flush({}, {status:404,statusText:'Missing'});await settle();
    expect(c.state()).toMatchObject({status:'success',data:measurement,references:{[refKeys[index]]:{status:'error',retryable:false}}});expect(root().querySelector('.measurement-value')?.textContent).toBe('-2,5');expect(root().textContent).toContain('La mesure reste affichée');
    if(index===0){expect(root().querySelector('.sensor-reference')).toBeNull();expect(root().querySelector('.sensor-unit')?.textContent).toContain('indisponible');}
    else{expect(root().querySelector('.sensor-reference')).not.toBeNull();expect(root().querySelector('.sensor-unit')?.textContent).toBe('°C');}
    c.retryReferences();http.expectNone(()=>true);
  });
  it.each([0,1,2,3])('rejects mismatching actual reference %s without using return ids',async index=>{
    await open();read('measurements/23').flush(measurement);for(let n=0;n<index;n++)read(refPaths[n]).flush(refData[n]);read(refPaths[index]).flush({...refData[index],id:99});await settle();
    expect(c.state()).toMatchObject({status:'success',references:{[refKeys[index]]:{status:'error',retryable:false}}});expect(root().textContent).toContain('ne correspond pas au rattachement réel');http.expectNone(()=>true);
  });
  it.each([0,1,2])('rejects an invalid foreign key at chain level %s without requesting id 0',async index=>{
    await open();read('measurements/23').flush(measurement);for(let n=0;n<index;n++)read(refPaths[n]).flush(refData[n]);
    const fk=['equipment_id','site_id','company_id'][index];read(refPaths[index]).flush({...refData[index],[fk]:0});await settle();
    expect(c.state()).toMatchObject({status:'success',references:{[refKeys[index+1]]:{status:'error'}}});http.expectNone(()=>true);
  });
  it.each([0,500])('retries a reference failure %s without reloading the measurement',async status=>{
    await open();read('measurements/23').flush(measurement);const req=read('sensors/17');if(status===0)req.error(new ProgressEvent('error'));else req.flush({}, {status,statusText:'Error'});await settle();
    c.retryReferences();parents();await settle();expect(c.state()).toMatchObject({status:'success',data:measurement,references:{company:{status:'success'}}});http.expectNone(()=>true);
  });
  it('does not invent a unit if the real sensor leaves it empty',async()=>{
    await open();read('measurements/23').flush(measurement);read('sensors/17').flush({...sensor,unit:''});refPaths.slice(1).forEach((path,index)=>read(path).flush(refData[index+1]));await settle();expect(c.currentUnit()).toBeNull();expect(root().querySelector('.sensor-unit')?.textContent).toContain('non renseignée');
  });
  it('cancels obsolete measurement requests and removes old data before a new id',async()=>{
    await open();const old=read('measurements/23');await h.navigateByUrl('/measurements/24',MeasurementDetailComponent);await settle();expect(old.cancelled).toBe(true);read('measurements/24').flush({...measurement,id:24});parents();await settle();expect(c.state()).toMatchObject({status:'success',data:{id:24}});
  });
  it('cancels obsolete parent reads and retries when navigating to another measurement',async()=>{
    await open();read('measurements/23').flush(measurement);const old=read('sensors/17');await h.navigateByUrl('/measurements/24',MeasurementDetailComponent);await settle();expect(old.cancelled).toBe(true);expect(root().querySelector('.measurement-value')).toBeNull();read('measurements/24').flush({}, {status:404,statusText:'Missing'});await settle();c.retryReferences();http.expectNone(()=>true);
  });
});
