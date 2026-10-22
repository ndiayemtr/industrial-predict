import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, NavigationEnd } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { SENSOR_ROUTES } from '../../sensors.routes';
import { MEASUREMENT_ROUTES } from '../../../measurements/measurements.routes';
import { SensorDetailComponent } from './sensor-detail.component';

const company = { id: 7, name: 'Entreprise réelle', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, name: 'Site réel', company_id: 7 };
const equipment = { ...company, id: 12, name: 'Pompe réelle', site_id: 9, equipment_type: 'pump', status: 'maintenance', criticality: 'critical' };
const sensor = { ...company, id: 17, equipment_id: 12, name: 'Capteur réel', sensor_type: 'temperature', unit: '°C', status: 'active' };
const context = 'company_id=99&site_id=88&equipment_id=77&search=Pompe&status=inactive&quality=bad&start_time=2026-01-01T00%3A00%3A00Z&page=4&page_size=50&returnUrl=https://example.com';
const target = '/measurements?company_id=7&site_id=9&equipment_id=12&sensor_id=17&page=1&page_size=20';
const catalog = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 50, pages: 1 });

describe('Sensor detail to scoped Measurements navigation', () => {
  let http: HttpTestingController, harness: RouterTestingHarness, component: SensorDetailComponent;
  const root = () => harness.routeNativeElement!;
  const action = () => root().querySelector<HTMLAnchorElement>('.sensor-measurements');
  const read = (path: string) => http.expectOne(req => req.url === '/api/v1/' + path && req.method === 'GET');
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'sensors', children: SENSOR_ROUTES }, { path: 'measurements', children: MEASUREMENT_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.expectNone(req => req.method !== 'GET'); http.verify(); } finally { TestBed.resetTestingModule(); } });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/sensors/17') { harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, SensorDetailComponent); await settle(); }
  function parents() { read('equipments/12').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); }
  async function loaded(url = '/sensors/17') { await open(url); read('sensors/17').flush(sensor); parents(); await settle(); }
  it('waits for all real parents and preserves existing actions without borrowing return filters', async () => {
    await open('/sensors/17?' + context); expect(action()).toBeNull();
    read('sensors/17').flush(sensor); await settle(); expect(action()).toBeNull();
    read('equipments/12').flush(equipment); await settle(); expect(action()).toBeNull();
    read('sites/9').flush(site); await settle(); expect(action()).toBeNull();
    read('companies/7').flush(company); await settle();
    expect(action()?.textContent).toBe('Voir les mesures'); expect(action()?.getAttribute('href')).toBe(target);
    expect(component.measurementsQuery()).toEqual({ company_id: 7, site_id: 9, equipment_id: 12, sensor_id: 17, page: 1, page_size: 20 });
    expect([...root().querySelectorAll('app-page-header a')].map(link => link.textContent)).toEqual(['Retour à la liste des capteurs', 'Voir les mesures', 'Modifier']);
    action()!.focus(); expect(document.activeElement).toBe(action());
    const query = 'company_id=99&site_id=88&equipment_id=77&page=4&page_size=50&search=Pompe&status=inactive';
    expect(root().querySelector('.sensor-back')?.getAttribute('href')).toBe('/sensors?' + query);
    expect(root().querySelector('.sensor-edit')?.getAttribute('href')).toBe('/sensors/17/edit?' + query);
    http.expectNone(req => req.url === '/api/v1/measurements');
  });
  it('does not reread or borrow changed query-only return context', async () => {
    await loaded(); await harness.navigateByUrl('/sensors/17?' + context); await settle(); expect(action()?.getAttribute('href')).toBe(target); http.expectNone(() => true);
  });
  describe.each(['equipment', 'site', 'company'] as const)('%s parent', scope => {
    function reach() { read('sensors/17').flush(sensor); if (scope !== 'equipment') read('equipments/12').flush(equipment); if (scope === 'company') read('sites/9').flush(site); }
    const path = () => scope === 'equipment' ? 'equipments/12' : scope === 'site' ? 'sites/9' : 'companies/7';
    it('rejects an inconsistent identity and retains Sensor and edit', async () => {
      await open(); reach(); read(path()).flush(scope === 'equipment' ? { ...equipment, id: 99 } : scope === 'site' ? { ...site, id: 99 } : { ...company, id: 99 });
      await settle(); expect(action()).toBeNull(); expect(component.measurementsQuery()).toBeNull(); expect(root().textContent).toContain('Capteur réel'); expect(root().querySelector('.sensor-edit')).not.toBeNull(); http.expectNone(() => true);
    });
    it('rejects an invalid foreign key locally', async () => {
      await open(); read('sensors/17').flush(scope === 'equipment' ? { ...sensor, equipment_id: 0 } : sensor);
      if (scope !== 'equipment') read('equipments/12').flush(scope === 'site' ? { ...equipment, site_id: 0 } : equipment);
      if (scope === 'company') read('sites/9').flush({ ...site, company_id: 0 });
      await settle(); expect(action()).toBeNull(); expect(component.measurementsQuery()).toBeNull(); http.expectNone(() => true);
    });
    it.each([0, 403, 404, 500])('hides the link after HTTP %s and during manual retry', async status => {
      await open('/sensors/17?' + context); reach(); const req = read(path());
      if (!status) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Unavailable' });
      await settle(); expect(action()).toBeNull(); expect(root().textContent).toContain('Capteur réel');
      if (scope === 'equipment') component.retryEquipment(); else if (scope === 'site') component.retrySite(); else component.retryCompany();
      await settle(); expect(action()).toBeNull();
      if (!status || status >= 500) {
        if (scope === 'equipment') read('equipments/12').flush(equipment);
        if (scope !== 'company') read('sites/9').flush(site);
        read('companies/7').flush(company); await settle(); expect(action()?.getAttribute('href')).toBe(target);
      }
      http.expectNone(() => true);
    });
  });
  it.each(['0', 'invalid'])('has no action for an invalid Sensor id %s', async id => { await open('/sensors/' + id); expect(action()).toBeNull(); http.expectNone(() => true); });
  it('has no action for mismatched or missing Sensor', async () => {
    await open(); read('sensors/17').flush({ ...sensor, id: 18 }); await settle(); expect(action()).toBeNull();
    await harness.navigateByUrl('/sensors/18'); await settle(); read('sensors/18').flush({}, { status: 404, statusText: 'Missing' }); await settle(); expect(action()).toBeNull(); http.expectNone(() => true);
  });
  it('removes old context and cancels obsolete parent reads on Sensor navigation', async () => {
    await loaded(); await harness.navigateByUrl('/sensors/18'); await settle(); expect(action()).toBeNull();
    read('sensors/18').flush({ ...sensor, id: 18 }); read('equipments/12').flush(equipment); read('sites/9').flush(site); const obsolete = read('companies/7');
    await harness.navigateByUrl('/sensors/19'); await settle(); expect(obsolete.cancelled).toBe(true); expect(action()).toBeNull();
    read('sensors/19').flush({ ...sensor, id: 19 }); parents(); await settle();
    expect(action()?.getAttribute('href')).toBe('/measurements?company_id=7&site_id=9&equipment_id=12&sensor_id=19&page=1&page_size=20');
  });
  async function navigateToMeasurements() {
    await loaded('/sensors/17?' + context);
    const router = TestBed.inject(Router), navigations: string[] = [];
    const subscription = router.events.subscribe(event => { if (event instanceof NavigationEnd) navigations.push(event.urlAfterRedirects); });
    action()!.click(); await settle(); subscription.unsubscribe();
    expect(navigations).toEqual([target]); expect(router.url).toBe(target);
    read('companies').flush(catalog([company])); http.expectNone(req => req.url === '/api/v1/measurements');
    read('sensors/17').flush(sensor); read('equipments/12').flush(equipment); read('sites/9').flush(site); http.expectNone(req => req.url === '/api/v1/measurements');
    read('companies/7').flush(company); await settle(); read('sites').flush(catalog([site])); read('equipments').flush(catalog([equipment])); read('sensors').flush(catalog([sensor])); return read('measurements');
  }
  const row = { id: 23, sensor_id: 17, timestamp: '2026-10-22T12:00:00.123456Z', value: 65.4, quality: 'good' };
  it('restores all four parents and loads only selected Sensor measurements with fresh pagination', async () => {
    const req = await navigateToMeasurements();
    expect(Object.fromEntries(req.request.params.keys().map(key => [key, req.request.params.get(key)]))).toEqual({ sensor_id: '17', page: '1', page_size: '20' });
    req.flush({ items: [row], total: 1, page: 1, page_size: 20, pages: 1 }); await settle();
    expect(root().querySelector('tbody')?.textContent).toContain('65,4');
    for (const [key, label] of [['company', 'Entreprise réelle'], ['site', 'Site réel'], ['equipment', 'Pompe réelle'], ['sensor', 'Capteur réel']]) expect(root().querySelector<HTMLSelectElement>('#measurements-' + key)?.selectedOptions[0].textContent).toContain(label);
    expect(root().querySelector('tbody a')?.getAttribute('href')).toBe('/measurements/23?company_id=7&site_id=9&equipment_id=12&sensor_id=17&page=1&page_size=20');
  });
  it('rejects measurements from another Sensor without any broader fallback', async () => {
    const req = await navigateToMeasurements(); req.flush({ items: [{ ...row, sensor_id: 99 }], total: 1, page: 1, page_size: 20, pages: 1 }); await settle();
    expect(root().querySelector('tbody')).toBeNull(); expect(root().textContent).toContain('autre capteur'); http.expectNone(() => true);
  });
});
