import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { MAINTENANCE_ROUTES } from '../../maintenance.routes';
import { MaintenanceListComponent } from './maintenance-list.component';

const company = { id: 7, name: 'Entreprise test', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7 };
const equipment = { ...company, id: 12, site_id: 9, equipment_type: 'pump', status: 'operational', criticality: 'high' };
const record = { id: 17, equipment_id: 12, title: 'Inspection 日本', maintenance_type: 'predictive', status: 'planned', priority: 'critical',
 description: null, failure_code: null, root_cause: null, action_taken: null, technician: null, cost: null, downtime_minutes: null,
 planned_at: null, started_at: null, completed_at: null, created_at: '2026-10-23T12:00:00.123456', updated_at: '2026-10-23T12:00:00Z' };
const catalog = { items: [company], total: 1, page: 1, page_size: 50, pages: 1 };
const page = { items: [record], total: 21, page: 1, page_size: 20, pages: 2 };
const base = '/maintenance?company_id=7&site_id=9&equipment_id=12';

describe('Maintenance list and applied context', () => {
 let http: HttpTestingController, h: RouterTestingHarness, c: MaintenanceListComponent;
 const root = () => h.routeNativeElement!;
 const req = (name: string) => http.expectOne(r => r.url === '/api/v1/' + name);
 const list = () => req('maintenance');
 const url = () => TestBed.inject(Router).parseUrl(TestBed.inject(Router).url).queryParams;
 async function settle() { h.fixture.detectChanges(); TestBed.tick(); await h.fixture.whenStable(); h.fixture.detectChanges(); }
 async function open(path = '/maintenance') { h = await RouterTestingHarness.create(); c = await h.navigateByUrl(path, MaintenanceListComponent); await settle(); }
 function parents() { req('equipments/12').flush(equipment); req('sites/9').flush(site); req('companies/7').flush(company); }
 function catalogs() { req('sites').flush({ ...catalog, items: [site] }); req('equipments').flush({ ...catalog, items: [equipment] }); }
 async function ready(path = base) { await open(path); req('companies').flush(catalog); parents(); await settle(); catalogs(); list().flush(page); await settle(); }
 async function reload() { parents(); list().flush(page); await settle(); }
 beforeEach(() => { TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([{ path: 'maintenance', children: MAINTENANCE_ROUTES }])] }); http = TestBed.inject(HttpTestingController); });
 afterEach(() => { try { http.expectNone(r => r.method !== 'GET'); http.verify(); } finally { TestBed.resetTestingModule(); } });
 it('requires explicit selections even with single options and hides helpers only after verification', async () => {
  await open(); req('companies').flush(catalog); await settle(); expect(c.company.value).toBeNull(); expect(c.site.disabled).toBe(true); http.expectNone(() => true);
  c.company.setValue(7); await settle(); req('companies/7').flush(company); await settle(); req('sites').flush({ ...catalog, items: [site] }); await settle();
  expect(c.site.value).toBeNull(); expect(c.equipment.disabled).toBe(true); expect(root().querySelector('#company-help')).toBeNull();
  c.site.setValue(9); await settle(); req('sites/9').flush(site); req('companies/7').flush(company); await settle(); req('equipments').flush({ ...catalog, items: [equipment] }); await settle();
  expect(c.equipment.value).toBeNull(); http.expectNone(() => true); c.equipment.setValue(12); await settle(); await reload(); expect(root().querySelector('#equipment-help')).toBeNull();
 });
 it('renders seven real columns, null and naive dates without adding UTC or links', async () => {
  await ready(); expect([...root().querySelectorAll('thead th')].map(e => e.textContent)).toEqual(['#ID', 'Titre', 'Type', 'Statut', 'Priorité', 'Date planifiée', 'Date de création']);
  expect(root().textContent).toContain('Prédictive'); expect(root().textContent).toContain('Non renseignée'); expect(root().textContent).toContain(record.created_at + ' (fuseau non fourni)');
  expect(root().querySelector('time[datetime="' + record.created_at + '"]')?.textContent).not.toContain('Z'); expect(root().querySelectorAll('a')).toHaveLength(0);
 });
 it('restores references outside first catalog pages and offers more for all three catalogs', async () => {
  await open(base + '&page=2&page_size=37'); req('companies').flush({ ...catalog, items: [], total: 51, pages: 2 }); parents(); await settle();
  req('sites').flush({ ...catalog, items: [], total: 51, pages: 2 }); req('equipments').flush({ ...catalog, items: [], total: 51, pages: 2 });
  const r = list(); expect(r.request.params.get('page_size')).toBe('37'); r.flush({ ...page, page: 2, page_size: 37, pages: 1 }); await settle();
  expect(c.companyOptions().map(i => i.id)).toContain(7); expect(c.siteOptions().map(i => i.id)).toContain(9); expect(c.equipmentOptions().map(i => i.id)).toContain(12);
  c.moreCompanies(); c.moreSites(); c.moreEquipments(); for (const name of ['companies', 'sites', 'equipments']) { const r = req(name); expect(r.request.params.get('page')).toBe('2'); r.flush({ ...catalog, items: [], page: 2, total: 51, pages: 2 }); } await settle(); expect(c.sizes()).toEqual([20, 37, 50, 100]);
 });
 it('searches only on submit with raw spaces, removes an empty search and blocks 101 characters', async () => {
  await ready(); c.search.setValue('  日本 %_  '); await settle(); http.expectNone(() => true); c.applySearch(); await settle(); parents(); const r = list(); expect(r.request.params.get('search')).toBe('  日本 %_  '); r.flush(page); await settle();
  c.search.setValue('é'.repeat(101)); c.applySearch(); await settle(); expect(c.searchError()).not.toBe(''); http.expectNone(() => true);
  c.search.setValue(''); c.applySearch(); await settle(); await reload(); expect(url()['search']).toBeUndefined();
 });
 it('accepts exactly 100 Unicode code points', async () => { await ready(); c.search.setValue('😀'.repeat(100)); c.applySearch(); await settle(); parents(); const r = list(); expect(r.request.params.get('search')).toBe('😀'.repeat(100)); r.flush(page); await settle(); });
 it.each([['maintenanceType', 'corrective', 'maintenance_type'], ['status', 'completed', 'status'], ['priority', 'high', 'priority']] as const)('applies %s on page one with exact API alias', async (control, value, key) => {
  await ready(base + '&page=2'); c[control].setValue(value as never); await settle(); parents(); const r = list(); expect(r.request.params.get(key)).toBe(value); expect(r.request.params.get('page')).toBe('1'); expect(r.request.params.has('company_id')).toBe(false); expect(r.request.params.has('site_id')).toBe(false); r.flush(page); await settle(); expect(url()[key]).toBe(value);
 });
 it('preserves raw microseconds and offsets for unchanged restored periods', async () => {
  const start = '2026-10-23T12:00:00.123456+02:00', end = '2026-10-23T10:00:00.123457Z'; await ready(base + '&start_time=' + encodeURIComponent(start) + '&end_time=' + encodeURIComponent(end));
  expect(c.start.value).toEqual({ date: '2026-10-23', time: '10:00:00', fraction: '123456' }); c.applyPeriod(); await settle(); http.expectNone(() => true);
  c.size.setValue(50); await settle(); parents(); const r = list(); expect(r.request.params.get('start_time')).toBe(start); expect(r.request.params.get('end_time')).toBe(end); r.flush(page); await settle();
 });
 it('serializes a UTC calendar, time and optional fraction with a single bound', async () => {
  await ready(base + '&page=2'); c.start.setValue({ date: '2026-10-23', time: '12:34:56', fraction: '123456' }); c.applyPeriod(); await settle(); parents(); const r = list(); expect(r.request.params.get('start_time')).toBe('2026-10-23T12:34:56.123456Z'); expect(r.request.params.has('end_time')).toBe(false); r.flush(page); await settle(); expect(root().textContent).toContain('Période de création du dossier (UTC)');
 });
 it.each([{ date: '2026-10-23', time: '', fraction: '' }, { date: '2026-10-23', time: '12:00:00', fraction: '1234567' }])('blocks invalid temporal draft %s', async parts => { await ready(); c.start.setValue(parts); c.applyPeriod(); await settle(); expect(c.periodError()).not.toBe(''); http.expectNone(() => true); });
 it.each(['bad', '2026-10-23T12:00:00', ''])('blocks invalid URL period %s without a widened query', async start => { await open(base + '&start_time=' + encodeURIComponent(start)); req('companies').flush(catalog); await settle(); expect(c.periodError()).not.toBe(''); expect(c.facade.state().status).toBe('error'); http.expectNone(() => true); });
 it.each(['status=unknown', 'priority=urgent', 'maintenance_type=repair', 'search='])('blocks invalid URL %s', async filter => { await open(base + '&' + filter); req('companies').flush(catalog); await settle(); expect(c.urlNotice()).not.toBe(''); http.expectNone(() => true); });
 it('blocks invalid identifiers in the URL', async () => { await open('/maintenance?equipment_id=0'); req('companies').flush(catalog); await settle(); expect(c.urlNotice()).not.toBe(''); http.expectNone(() => true); });
 it('blocks contradictory parentage and leaves help visible', async () => { await open(base); req('companies').flush(catalog); req('equipments/12').flush({ ...equipment, site_id: 99 }); await settle(); expect(c.facade.state().status).toBe('error'); expect(root().querySelector('#equipment-help')).not.toBeNull(); http.expectNone(() => true); });
 it('clears descendants, search and period while retaining enums and size on parent change', async () => {
  await ready(base + '&search=old&status=completed&priority=high&maintenance_type=corrective&page_size=50&start_time=2026-10-23T00:00:00Z'); c.company.setValue(null); await settle();
  expect(url()).toMatchObject({ status: 'completed', priority: 'high', maintenance_type: 'corrective', page_size: '50', page: '1' }); for (const key of ['site_id', 'equipment_id', 'search', 'start_time', 'end_time']) expect(url()[key]).toBeUndefined(); expect(c.equipment.value).toBeNull(); expect(root().querySelector('#company-help')).not.toBeNull(); http.expectNone(() => true);
 });
 it('supports manual out-of-range recovery with no silent read', async () => { await ready(); c.changePage(2); await settle(); parents(); const r = list(); expect(r.request.params.get('page')).toBe('2'); r.flush({ ...page, items: [], page: 2 }); await settle(); expect(root().textContent).toContain('Page hors plage'); http.expectNone(() => true); c.recoverPage(); await settle(); await reload(); expect(url()['page']).toBe('1'); });
 it.each([false, true])('distinguishes filtered empty %s', async filtered => { await open(base + (filtered ? '&priority=critical' : '')); req('companies').flush(catalog); parents(); await settle(); catalogs(); list().flush({ ...page, total: 0, pages: 0, items: [] }); await settle(); expect(root().textContent).toContain(filtered ? 'Aucun résultat' : 'Aucune intervention'); });
 it('shows busy and network errors with manual retry', async () => { await open(base); req('companies').flush(catalog); expect(root().querySelector('.results')?.getAttribute('aria-busy')).toBe('true'); parents(); await settle(); catalogs(); list().error(new ProgressEvent('error')); await settle(); expect(root().textContent).toContain('Impossible de joindre le serveur'); http.expectNone(() => true); c.facade.retry(); await reload(); });
 it('cancels obsolete catalog and Maintenance requests', async () => { await open(base); const companies = req('companies'); parents(); await settle(); const sites = req('sites'), equipments = req('equipments'), read = list(); companies.flush(catalog); c.company.setValue(null); await settle(); expect(sites.cancelled).toBe(true); expect(equipments.cancelled).toBe(true); expect(read.cancelled).toBe(true); http.expectNone(() => true); });
 it('offers manual catalog retry and retains next-page request number', async () => { await open(); req('companies').error(new ProgressEvent('error')); await settle(); expect(root().textContent).toContain('Le catalogue ne peut pas être chargé'); c.retryCompanies(); req('companies').flush({ ...catalog, total: 51, pages: 2 }); await settle(); c.moreCompanies(); req('companies').error(new ProgressEvent('error')); await settle(); c.retryCompanies(); const r = req('companies'); expect(r.request.params.get('page')).toBe('2'); r.flush({ ...catalog, page: 2, total: 51, pages: 2 }); await settle(); });
 it('refreshes manually retaining filters, pages and context', async () => { await ready(base + '&priority=critical&page=2'); c.refresh(); await reload(); expect(url()['priority']).toBe('critical'); expect(url()['page']).toBe('2'); });
 it('has labelled controls, a focusable region and no write actions', async () => { await ready(); for (const label of root().querySelectorAll('label[for]')) expect(root().querySelector('#' + label.getAttribute('for'))).not.toBeNull(); const input = root().querySelector<HTMLInputElement>('#maintenance-search')!; input.focus(); expect(document.activeElement).toBe(input); expect(root().querySelector('.table-scroll')?.getAttribute('tabindex')).toBe('0'); expect(root().textContent).not.toMatch(/Modifier|Supprimer|Nouvelle intervention/); });
 it('resets equipment-specific criteria on changing equipment and cancels late reads', async () => {
  await ready(base + '&search=old&status=cancelled&priority=high&maintenance_type=corrective&page_size=50&start_time=2026-10-23T00:00:00Z');
  c.equipment.setValue(13); await settle(); req('equipments/13').flush({ ...equipment, id: 13 }); req('sites/9').flush(site); req('companies/7').flush(company);
  const r = list(); expect(r.request.params.keys().sort()).toEqual(['equipment_id','maintenance_type','page','page_size','priority','status']); expect(r.request.params.get('equipment_id')).toBe('13');
  r.flush({ ...page, items: [], total: 0, pages: 0, page_size: 50 }); await settle(); expect(url()['search']).toBeUndefined(); expect(url()['start_time']).toBeUndefined(); expect(url()['status']).toBe('cancelled');
 });
 it('rejects an inconsistent catalog and clears only the period explicitly', async () => {
  await ready(base + '&search=test&priority=high'); c.clearPeriod(); await settle(); http.expectNone(() => true); expect(url()['priority']).toBe('high'); expect(url()['search']).toBe('test');
  c.company.setValue(8); await settle(); req('companies/8').flush({ ...company, id: 8 }); await settle(); req('sites').flush({ ...catalog, items: [site] }); await settle(); expect(c.sites().status).toBe('error'); expect(c.siteOptions()).toEqual([]); http.expectNone(() => true);
 });

 it('keeps temporal drafts separate from applied offsets across pagination and enum changes', async () => {
  const start = '2026-10-23T12:00:00.123456+02:00';
  await ready(base + '&start_time=' + encodeURIComponent(start));
  c.start.controls.time.setValue('11:00:00'); await settle(); http.expectNone(() => true);
  expect(c.periodDraft()).toBe(true); expect(root().textContent).toContain('Brouillon de période non appliqué');
  expect(root().querySelector('.applied-period')?.textContent).toContain(start);
  c.status.setValue('completed'); await settle(); parents(); let r = list(); expect(r.request.params.get('start_time')).toBe(start); r.flush(page); await settle();
  expect(c.start.controls.time.value).toBe('11:00:00'); expect(c.periodDraft()).toBe(true);
  c.changePage(2); await settle(); parents(); r = list(); expect(r.request.params.get('start_time')).toBe(start); r.flush({ ...page, page: 2 }); await settle();
  expect(c.start.controls.time.value).toBe('11:00:00'); expect(c.facade.query()?.start_time).toBe(start);
 });
 it('preserves applied results on an invalid draft without GET or default hour', async () => {
  await ready(base + '&start_time=2026-10-23T10:00:00.123456Z'); const state = c.facade.state();
  c.start.controls.time.setValue(''); c.applyPeriod(); await settle();
  expect(c.facade.state()).toBe(state); expect(c.start.controls.time.value).toBe(''); expect(c.periodDraft()).toBe(true);
  expect(root().querySelector('#start-time-error')?.textContent).toContain('heure UTC');
  expect(root().querySelector('#maintenance-start-time')?.getAttribute('aria-invalid')).toBe('true');
  expect(document.activeElement?.id).toBe('maintenance-start-time'); http.expectNone(() => true);
 });
 it.each([
  [{ date: '2026-10-23', time: '', fraction: '' }, 'start-time'],
  [{ date: '', time: '12:00:00', fraction: '' }, 'start-date'],
  [{ date: '2026-10-23', time: '12:00:00', fraction: 'abcdef' }, 'start-fraction'],
  [{ date: '2026-10-23', time: '12:00:00', fraction: '1234567' }, 'start-fraction'],
  [{ date: '2026-02-30', time: '12:00:00', fraction: '' }, 'start-date'],
  [{ date: '2026-10-23', time: '24:00:00', fraction: '' }, 'start-time'],
  [{ date: '2026-10-23', time: '12:60:00', fraction: '' }, 'start-time'],
  [{ date: '2026-10-23', time: '12:00:60', fraction: '' }, 'start-time']
 ] as const)('places precise invalid draft %s error at %s without HTTP', async (parts, field) => {
  await ready(); c.start.setValue({ ...parts }); c.applyPeriod(); await settle(); expect(c.fieldErrors()[field]).toBeTruthy();
  expect(root().querySelector('#' + field + '-error')?.getAttribute('role')).toBe('alert');
  expect(root().querySelector('#maintenance-' + field)?.getAttribute('aria-describedby')).toContain(field + '-error'); http.expectNone(() => true);
 });
 it.each(['12:00:00','11:59:59'])('rejects end %s equal or before start next to the end fields', async time => {
  await ready(); c.start.setValue({ date: '2026-10-23', time: '12:00:00', fraction: '' }); c.end.setValue({ date: '2026-10-23', time, fraction: '' }); c.applyPeriod(); await settle();
  expect(root().querySelector('#end-date-error')?.textContent).toContain('strictement antérieur'); http.expectNone(() => true);
 });
 it('shows the error of a naive restored bound next to its date without inventing UTC', async () => {
  await open(base + '&end_time=2026-10-23T12:00:00'); req('companies').flush(catalog); await settle();
  expect(root().querySelector('#end-date-error')?.textContent).toContain('offset'); expect(url()['end_time']).toBe('2026-10-23T12:00:00'); http.expectNone(() => true);
 });
 it('clears only temporal criteria while retaining industrial, business and search filters', async () => {
  await ready(base + '&search=Inspection&maintenance_type=preventive&status=planned&priority=high&page=2&page_size=50&start_time=2026-10-23T00:00:00Z');
  c.clearPeriod(); await settle(); parents(); const r = list();
  expect(r.request.params.keys().sort()).toEqual(['equipment_id','maintenance_type','page','page_size','priority','search','status']);
  expect(r.request.params.get('search')).toBe('Inspection'); expect(r.request.params.get('page')).toBe('1'); r.flush(page); await settle();
  expect(c.periodDraft()).toBe(false); expect(url()['priority']).toBe('high'); expect(url()['status']).toBe('planned');
 });
 it('retains a draft search through pagination and applying a period until explicitly searched', async () => {
  await ready(base + '&search=applied'); c.search.setValue('draft'); await settle(); http.expectNone(() => true);
  expect(c.searchDraft()).toBe(true); expect(root().querySelector('.applied-search')?.textContent).toContain('applied');
  c.start.setValue({ date: '2026-10-23', time: '12:00:00', fraction: '000001' }); c.applyPeriod(); await settle(); parents(); const r = list();
  expect(r.request.params.get('search')).toBe('applied'); expect(r.request.params.get('start_time')).toBe('2026-10-23T12:00:00.000001Z'); r.flush(page); await settle();
  expect(c.search.value).toBe('draft'); expect(c.searchDraft()).toBe(true); c.applySearch(); await settle(); parents(); const searched = list(); expect(searched.request.params.get('search')).toBe('draft'); searched.flush(page); await settle(); expect(c.searchDraft()).toBe(false);
 });
 it('removes a draft notice when initial values are restored and renders textual badges', async () => {
  await ready(); c.start.controls.fraction.setValue('1'); c.start.controls.fraction.setValue(''); c.search.setValue('draft'); c.search.setValue(''); await settle();
  expect(c.periodDraft()).toBe(false); expect(c.searchDraft()).toBe(false); expect(root().querySelector('.status-badge')?.textContent).toBe('Planifiée'); expect(root().querySelector('.priority-badge')?.textContent).toBe('Critique');
  expect(root().querySelector('.record-title')?.textContent).toBe(record.title); expect(root().querySelectorAll('a')).toHaveLength(0); http.expectNone(() => true);
 });

 it('does not discard an invalid unrelated URL filter when clearing the period', async () => {
  await open(base + '&status=unknown&start_time=invalid'); req('companies').flush(catalog); await settle(); c.clearPeriod(); await settle();
  expect(url()['status']).toBe('unknown'); expect(url()['start_time']).toBeUndefined(); expect(c.urlNotice()).not.toBe(''); http.expectNone(() => true);
 });

});
