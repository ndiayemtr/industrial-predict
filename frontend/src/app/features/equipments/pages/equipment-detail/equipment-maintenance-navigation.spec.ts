import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { EQUIPMENT_ROUTES } from '../../equipments.routes';
import { MAINTENANCE_ROUTES } from '../../../maintenance/maintenance.routes';
import { EquipmentDetailComponent } from './equipment-detail.component';

const company = { id: 7, name: 'Entreprise réelle', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, name: 'Site réel', company_id: 7 };
const equipment = { ...company, id: 12, name: 'Pompe réelle', site_id: 9, equipment_type: 'pump', status: 'maintenance', criticality: 'critical' };
const record = { id: 17, equipment_id: 12, title: 'Inspection réelle', maintenance_type: 'preventive', status: 'planned', priority: 'high',
  description: null, failure_code: null, root_cause: null, action_taken: null, technician: null, planned_at: null, started_at: null, completed_at: null,
  cost: null, downtime_minutes: null, created_at: '2026-10-23T12:00:00.123456', updated_at: '2026-10-23T12:00:00.654321Z' };
const context = 'company_id=99&site_id=88&equipment_id=77&search=Pompe&status=maintenance&criticality=critical&page=4&page_size=50&returnUrl=https://example.com';
const target = '/maintenance?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20';
const catalog = (items: unknown[]) => ({ items, total: items.length, page: 1, page_size: 50, pages: 1 });

describe('Equipment detail to scoped Maintenance navigation', () => {
  let http: HttpTestingController, harness: RouterTestingHarness, component: EquipmentDetailComponent;
  const root = () => harness.routeNativeElement!;
  const action = () => root().querySelector<HTMLAnchorElement>('.equipment-maintenance');
  const read = (path: string) => http.expectOne(req => req.url === '/api/v1/' + path && req.method === 'GET');
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'equipments', children: EQUIPMENT_ROUTES }, { path: 'maintenance', children: MAINTENANCE_ROUTES }])] });
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
    expect(action()?.textContent).toBe('Voir les interventions'); expect(action()?.getAttribute('href')).toBe(target);
    expect(component.maintenanceQuery()).toEqual({ company_id: 7, site_id: 9, equipment_id: 12, page: 1, page_size: 20 });
    action()!.focus(); expect(document.activeElement).toBe(action());
    expect(root().querySelector('.equipment-back')?.getAttribute('href')).toContain('company_id=99&site_id=88');
    http.expectNone(req => req.url === '/api/v1/maintenance');
  });
  it('retains relative order and destinations of existing actions', async () => {
    await loaded('/equipments/12?' + context);
    expect([...root().querySelectorAll('app-page-header a')].map(e => e.textContent)).toEqual(['Retour à la liste des équipements', 'Voir les capteurs', 'Voir les interventions', 'Voir les prédictions', 'Modifier']);
    expect(root().querySelector('.equipment-sensors')?.getAttribute('href')).toBe('/sensors?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20');
    expect(root().querySelector('.equipment-edit')?.getAttribute('href')).toContain('/equipments/12/edit?company_id=99&site_id=88');
    expect(TestBed.inject(Router).parseUrl(TestBed.inject(Router).url).queryParams).toEqual(TestBed.inject(Router).parseUrl('/equipments/12?' + context).queryParams);
  });
  it('keeps actual context on a query-only Equipment navigation without rereading parents', async () => {
    await loaded(); await harness.navigateByUrl('/equipments/12?' + context); await settle(); expect(action()?.getAttribute('href')).toBe(target); http.expectNone(() => true);
  });
  it.each(['site', 'company'] as const)('rejects an inconsistent %s while preserving Equipment data', async scope => {
    await open('/equipments/12?' + context); read('equipments/12').flush(equipment);
    if (scope === 'site') read('sites/9').flush({ ...site, id: 88 }); else { read('sites/9').flush(site); read('companies/7').flush({ ...company, id: 99 }); }
    await settle(); expect(action()).toBeNull(); expect(component.maintenanceQuery()).toBeNull(); expect(root().textContent).toContain('Pompe réelle'); http.expectNone(() => true);
  });
  describe.each(['site', 'company'] as const)('%s unavailable', scope => {
    it.each([0, 403, 404, 500])('hides the action after HTTP %s until a successful manual retry', async status => {
      await open('/equipments/12?' + context); read('equipments/12').flush(equipment); if (scope === 'company') read('sites/9').flush(site);
      const req = read(scope === 'site' ? 'sites/9' : 'companies/7');
      if (!status) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Unavailable' });
      await settle(); expect(action()).toBeNull(); expect(component.maintenanceQuery()).toBeNull(); expect(root().textContent).toContain('Pompe réelle');
      if (scope === 'site') component.retrySite(); else component.retryCompany();
      if (!status || status >= 500) {
        await settle(); expect(action()).toBeNull(); if (scope === 'site') read('sites/9').flush(site); read('companies/7').flush(company); await settle(); expect(action()?.getAttribute('href')).toBe(target);
      }
      http.expectNone(() => true);
    });
  });
  it.each([0, -1, 1.5, 9007199254740992])('rejects invalid site FK %s locally', async id => {
    await open(); read('equipments/12').flush({ ...equipment, site_id: id }); await settle(); expect(action()).toBeNull(); expect(component.maintenanceQuery()).toBeNull(); http.expectNone(() => true);
  });
  it.each([0, -1, 1.5, 9007199254740992])('rejects invalid company FK %s locally', async id => {
    await open(); read('equipments/12').flush(equipment); read('sites/9').flush({ ...site, company_id: id }); await settle(); expect(action()).toBeNull(); expect(component.maintenanceQuery()).toBeNull(); http.expectNone(() => true);
  });
  it.each(['0', 'invalid'])('has no action on an invalid Equipment id %s', async id => {
    await open('/equipments/' + id); expect(action()).toBeNull(); expect(component.maintenanceQuery()).toBeNull(); http.expectNone(() => true);
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
    expect(action()?.getAttribute('href')).toBe('/maintenance?company_id=7&site_id=9&equipment_id=14&page=1&page_size=20');
  });
  async function navigateToMaintenance() {
    await loaded('/equipments/12?' + context); action()!.click(); await settle(); expect(TestBed.inject(Router).url).toBe(target);
    read('companies').flush(catalog([company])); http.expectNone(req => req.url === '/api/v1/maintenance');
    read('equipments/12').flush(equipment); read('sites/9').flush(site); http.expectNone(req => req.url === '/api/v1/maintenance');
    read('companies/7').flush(company); await settle(); read('sites').flush(catalog([site])); read('equipments').flush(catalog([equipment])); return read('maintenance');
  }
  it('restores the chain and only requests Maintenance of the actual equipment with fresh pagination', async () => {
    const req = await navigateToMaintenance();
    expect(Object.fromEntries(req.request.params.keys().map(key => [key, req.request.params.get(key)]))).toEqual({ equipment_id: '12', page: '1', page_size: '20' });
    req.flush({ items: [record], total: 1, page: 1, page_size: 20, pages: 1 }); await settle(); expect(root().querySelector('tbody')?.textContent).toContain('Inspection réelle');
    for (const [key,label] of [['company','Entreprise réelle'],['site','Site réel'],['equipment','Pompe réelle']]) expect(root().querySelector<HTMLSelectElement>('#maintenance-' + key)?.selectedOptions[0].textContent).toContain(label);
    expect(root().querySelector<HTMLInputElement>('#maintenance-search')?.value).toBe('');
    expect(root().querySelector('tbody a')?.getAttribute('href')).toBe('/maintenance/17?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20');
  });
  it('blocks Maintenance if a real parent changes between the action and list verification, without replacing URL ids', async () => {
    await loaded('/equipments/12?' + context); action()!.click(); await settle();
    read('companies').flush(catalog([company])); read('equipments/12').flush({ ...equipment, site_id: 88 }); await settle();
    expect(TestBed.inject(Router).url).toBe(target); expect(root().textContent).toContain('n’appartient pas au site sélectionné');
    http.expectNone(req => req.url === '/api/v1/maintenance'); http.expectNone(req => req.url === '/api/v1/sites/88');
  });
  it('rejects a Maintenance response from another equipment without a wider fallback', async () => {
    const req = await navigateToMaintenance(); req.flush({ items: [{ ...record, equipment_id: 99 }], total: 1, page: 1, page_size: 20, pages: 1 }); await settle();
    expect(root().textContent).toContain('invalide'); expect(root().querySelector('tbody')).toBeNull(); http.expectNone(() => true);
  });
  it('resolves Maintenance -> Equipment from real references and preserves its own full return URL', async () => {
    const query = 'company_id=99&site_id=88&equipment_id=77&maintenance_type=preventive&status=planned&priority=high&search=Inspection&start_time=2026-10-23T14%3A00%3A00.123456%2B02%3A00&end_time=2026-10-24T00%3A00%3A00.999999Z&page=2&page_size=1';
    harness = await RouterTestingHarness.create('/maintenance/17?' + query + '#history'); await settle();
    read('maintenance/17').flush(record); await settle(); expect(root().querySelector('.equipment-reference')).toBeNull();
    read('equipments/12').flush(equipment); await settle();
    expect(root().querySelector('.equipment-reference')?.getAttribute('href')).toBe('/equipments/12?site_id=9&page=1&page_size=20');
    parents(); await settle();
    const inverse = root().querySelector<HTMLAnchorElement>('.equipment-reference')!;
    expect(inverse.getAttribute('href')).toBe('/equipments/12?site_id=9&company_id=7&page=1&page_size=20');
    const back = TestBed.inject(Router).parseUrl(root().querySelector('.maintenance-back')!.getAttribute('href')!);
    expect(back.queryParams).toMatchObject({ company_id: '99', site_id: '88', equipment_id: '77', maintenance_type: 'preventive', status: 'planned', priority: 'high', search: 'Inspection', start_time: '2026-10-23T14:00:00.123456+02:00', end_time: '2026-10-24T00:00:00.999999Z', page: '2', page_size: '1' }); expect(back.fragment).toBe('history');
    inverse.click(); await settle(); expect(action()).toBeNull();
    read('equipments/12').flush(equipment); read('sites/9').flush(site); http.expectNone(req => req.url === '/api/v1/maintenance');
    read('companies/7').flush(company); await settle(); expect(action()?.getAttribute('href')).toBe(target);
    expect(root().querySelector('.equipment-back')?.getAttribute('href')).toBe('/equipments?company_id=7&site_id=9&page=1&page_size=20'); http.expectNone(() => true);
  });

});
