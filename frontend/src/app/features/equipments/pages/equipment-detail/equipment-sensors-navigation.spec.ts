import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { EQUIPMENT_ROUTES } from '../../equipments.routes';
import { SENSOR_ROUTES } from '../../../sensors/sensors.routes';
import { EquipmentDetailComponent } from './equipment-detail.component';

const company = { id: 7, name: 'Entreprise réelle', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, name: 'Site réel', company_id: 7 };
const equipment = { ...company, id: 12, name: 'Pompe réelle', site_id: 9, equipment_type: 'pump', status: 'maintenance', criticality: 'critical' };
const sensor = { ...company, id: 17, equipment_id: 12, name: 'Capteur réel', sensor_type: 'temperature', unit: '°C', status: 'active' };
const context = 'company_id=99&site_id=88&equipment_id=77&search=Pompe&status=maintenance&criticality=critical&page=4&page_size=50&returnUrl=https://example.com';
const target = '/sensors?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20';
const catalog = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 50, pages: 1 });

describe('Equipment detail to scoped Sensors navigation', () => {
  let http: HttpTestingController, harness: RouterTestingHarness, component: EquipmentDetailComponent;
  const root = () => harness.routeNativeElement!;
  const action = () => root().querySelector<HTMLAnchorElement>('.equipment-sensors');
  const read = (path: string) => http.expectOne(req => req.url === '/api/v1/' + path && req.method === 'GET');
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'equipments', children: EQUIPMENT_ROUTES }, { path: 'sensors', children: SENSOR_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.expectNone(req => req.method !== 'GET'); http.verify(); } finally { TestBed.resetTestingModule(); } });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/equipments/12') { harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, EquipmentDetailComponent); await settle(); }
  function parents() { read('sites/9').flush(site); read('companies/7').flush(company); }
  async function loaded(url = '/equipments/12') { await open(url); read('equipments/12').flush(equipment); parents(); await settle(); }
  it('waits for actual parents and never borrows Equipment filters or URL parents', async () => {
    await open('/equipments/12?' + context); expect(action()).toBeNull();
    read('equipments/12').flush(equipment); await settle(); expect(action()).toBeNull();
    read('sites/9').flush(site); await settle(); expect(action()).toBeNull();
    read('companies/7').flush(company); await settle();
    expect(action()?.textContent).toBe('Voir les capteurs'); expect(action()?.getAttribute('href')).toBe(target);
    expect(component.sensorsQuery()).toEqual({ company_id: 7, site_id: 9, equipment_id: 12, page: 1, page_size: 20 });
    action()!.focus(); expect(document.activeElement).toBe(action());
    expect(root().querySelector('.equipment-back')?.getAttribute('href')).toContain('company_id=99&site_id=88');
    http.expectNone(req => req.url === '/api/v1/sensors');
  });
  it('keeps actual context on a query-only Equipment navigation without rereading parents', async () => {
    await loaded(); await harness.navigateByUrl('/equipments/12?' + context); await settle(); expect(action()?.getAttribute('href')).toBe(target); http.expectNone(() => true);
  });
  it.each(['site', 'company'] as const)('rejects an inconsistent %s while preserving Equipment data', async scope => {
    await open('/equipments/12?' + context); read('equipments/12').flush(equipment);
    if (scope === 'site') read('sites/9').flush({ ...site, id: 88 }); else { read('sites/9').flush(site); read('companies/7').flush({ ...company, id: 99 }); }
    await settle(); expect(action()).toBeNull(); expect(component.sensorsQuery()).toBeNull(); expect(root().textContent).toContain('Pompe réelle'); http.expectNone(() => true);
  });
  describe.each(['site', 'company'] as const)('%s unavailable', scope => {
    it.each([0, 403, 404, 500])('hides the action after HTTP %s until a successful manual retry', async status => {
      await open('/equipments/12?' + context); read('equipments/12').flush(equipment); if (scope === 'company') read('sites/9').flush(site);
      const req = read(scope === 'site' ? 'sites/9' : 'companies/7');
      if (!status) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Unavailable' });
      await settle(); expect(action()).toBeNull(); expect(component.sensorsQuery()).toBeNull(); expect(root().textContent).toContain('Pompe réelle');
      if (scope === 'site') component.retrySite(); else component.retryCompany();
      if (!status || status >= 500) {
        await settle(); expect(action()).toBeNull(); if (scope === 'site') read('sites/9').flush(site); read('companies/7').flush(company); await settle(); expect(action()?.getAttribute('href')).toBe(target);
      }
      http.expectNone(() => true);
    });
  });
  it.each([0, -1, 1.5, 9007199254740992])('rejects invalid site FK %s locally', async id => {
    await open(); read('equipments/12').flush({ ...equipment, site_id: id }); await settle(); expect(action()).toBeNull(); expect(component.sensorsQuery()).toBeNull(); http.expectNone(() => true);
  });
  it.each([0, -1, 1.5, 9007199254740992])('rejects invalid company FK %s locally', async id => {
    await open(); read('equipments/12').flush(equipment); read('sites/9').flush({ ...site, company_id: id }); await settle(); expect(action()).toBeNull(); expect(component.sensorsQuery()).toBeNull(); http.expectNone(() => true);
  });
  it.each(['0', 'invalid'])('has no action on an invalid Equipment id %s', async id => {
    await open('/equipments/' + id); expect(action()).toBeNull(); expect(component.sensorsQuery()).toBeNull(); http.expectNone(() => true);
  });
  it('has no action for a mismatched or missing Equipment', async () => {
    await open(); read('equipments/12').flush({ ...equipment, id: 13 }); await settle(); expect(action()).toBeNull();
    await harness.navigateByUrl('/equipments/13'); await settle(); read('equipments/13').flush({}, { status: 404, statusText: 'Missing' }); await settle(); expect(action()).toBeNull(); http.expectNone(() => true);
  });
  it('removes stale context immediately and cancels obsolete parent reads on id change', async () => {
    await loaded(); await harness.navigateByUrl('/equipments/13'); await settle(); expect(action()).toBeNull();
    read('equipments/13').flush({ ...equipment, id: 13 }); read('sites/9').flush(site); const obsolete = read('companies/7');
    await harness.navigateByUrl('/equipments/14'); await settle(); expect(obsolete.cancelled).toBe(true); expect(action()).toBeNull();
    read('equipments/14').flush({ ...equipment, id: 14 }); parents(); await settle();
    expect(action()?.getAttribute('href')).toBe('/sensors?company_id=7&site_id=9&equipment_id=14&page=1&page_size=20');
  });
  async function navigateToSensors() {
    await loaded('/equipments/12?' + context); action()!.click(); await settle(); expect(TestBed.inject(Router).url).toBe(target);
    read('companies').flush(catalog([company])); http.expectNone(req => req.url === '/api/v1/sensors');
    read('equipments/12').flush(equipment); read('sites/9').flush(site); http.expectNone(req => req.url === '/api/v1/sensors');
    read('companies/7').flush(company); await settle(); read('sites').flush(catalog([site])); read('equipments').flush(catalog([equipment])); return read('sensors');
  }
  it('restores the chain and only requests Sensors of the actual equipment with fresh pagination', async () => {
    const req = await navigateToSensors();
    expect(Object.fromEntries(req.request.params.keys().map(key => [key, req.request.params.get(key)]))).toEqual({ equipment_id: '12', page: '1', page_size: '20' });
    req.flush({ items: [sensor], total: 1, page: 1, page_size: 20, pages: 1 }); await settle(); expect(root().querySelector('tbody')?.textContent).toContain('Capteur réel');
    for (const [key,label] of [['company','Entreprise réelle'],['site','Site réel'],['equipment','Pompe réelle']]) expect(root().querySelector<HTMLSelectElement>('#sensors-' + key)?.selectedOptions[0].textContent).toContain(label);
    expect(root().querySelector<HTMLInputElement>('#sensors-search')?.value).toBe('');
    expect(root().querySelector('tbody a')?.getAttribute('href')).toBe('/sensors/17?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20');
  });
  it('rejects a Sensors response from another equipment without a wider fallback', async () => {
    const req = await navigateToSensors(); req.flush({ items: [{ ...sensor, equipment_id: 99 }], total: 1, page: 1, page_size: 20, pages: 1 }); await settle();
    expect(root().textContent).toContain('autre équipement'); expect(root().querySelector('tbody')).toBeNull(); http.expectNone(() => true);
  });
});
