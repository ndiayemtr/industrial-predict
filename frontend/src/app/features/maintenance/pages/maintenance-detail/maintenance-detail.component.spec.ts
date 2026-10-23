import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { MAINTENANCE_ROUTES } from '../../maintenance.routes';
import { MaintenanceDetailComponent } from './maintenance-detail.component';

const record = { id: 17, equipment_id: 12, title: 'Inspection 日本', maintenance_type: 'predictive', status: 'planned', priority: 'critical',
  description: 'Diagnostic réel\nLigne suivante', failure_code: '', root_cause: null, action_taken: 'Contrôle effectué', technician: 'Équipe A',
  planned_at: '2026-10-23T17:30:00.123456+05:30', started_at: null, completed_at: null, cost: 0, downtime_minutes: 0,
  created_at: '2026-10-23T12:00:00.654321', updated_at: '2026-10-23T12:00:00.000001Z' };
const company = { id: 7, name: 'Entreprise réelle', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7, name: 'Site réel' };
const equipment = { ...company, id: 12, site_id: 9, name: 'Pompe réelle', equipment_type: 'pump', status: 'operational', criticality: 'high' };
const paths = ['equipments/12', 'sites/9', 'companies/7'];
const data = [equipment, site, company];
const keys = ['equipment', 'site', 'company'];
const context = 'company_id=7&site_id=9&equipment_id=12&maintenance_type=predictive&status=planned&priority=critical&search=Inspection&start_time=2026-10-23T17%3A30%3A00.123456%2B05%3A30&end_time=2026-10-24T00%3A00%3A00.000001Z&page=3&page_size=50';

describe('Maintenance read-only detail', () => {
  let http: HttpTestingController, h: RouterTestingHarness, c: MaintenanceDetailComponent;
  const root = () => h.routeNativeElement!;
  const read = (path: string) => http.expectOne('/api/v1/' + path);
  const value = (field: string) => root().querySelector(`[data-field="${field}"] dd`)?.textContent?.trim();
  async function settle() { h.fixture.detectChanges(); TestBed.tick(); await h.fixture.whenStable(); h.fixture.detectChanges(); }
  async function open(url = '/maintenance/17') { h = await RouterTestingHarness.create(); c = await h.navigateByUrl(url, MaintenanceDetailComponent); await settle(); }
  function parents() { paths.forEach((path, index) => read(path).flush(data[index])); }
  async function loaded(url = '/maintenance/17', override = {}) { await open(url); read('maintenance/17').flush({ ...record, ...override }); parents(); await settle(); }
  beforeEach(() => { TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([{ path: 'maintenance', children: MAINTENANCE_ROUTES }])] }); http = TestBed.inject(HttpTestingController); });
  afterEach(() => { try { http.expectNone(req => req.method !== 'GET'); http.verify(); } finally { TestBed.resetTestingModule(); } });

  it('renders all 18 actual fields, null, empty text and zero without invented units', async () => {
    await loaded();
    expect([...root().querySelectorAll('[data-field]')].map(el => el.getAttribute('data-field')).sort()).toEqual(Object.keys(record).sort());
    expect(value('id')).toBe('17'); expect(value('equipment_id')).toBe('12'); expect(value('title')).toBe(record.title);
    expect(value('description')).toBe(record.description); expect(value('failure_code')).toBe('Texte vide'); expect(value('root_cause')).toBe('Non renseigné');
    expect(value('cost')).toBe('0'); expect(value('downtime_minutes')).toBe('0'); expect(value('technician')).toBe('Équipe A');
    expect(root().textContent).toContain('pas la preuve d’une prédiction IA'); expect(root().textContent).toContain('Aucune devise');
    expect(root().querySelectorAll('h1')).toHaveLength(1); expect(root().querySelector('form,input,select,button')).toBeNull();
    expect(root().textContent).not.toMatch(/Supprimer|Modifier|Démarrer|Terminer/);
    const link = root().querySelector<HTMLAnchorElement>('.equipment-reference')!; link.focus(); expect(document.activeElement).toBe(link);
    expect(link.getAttribute('href')).toBe('/equipments/12?site_id=9&company_id=7&page=1&page_size=20');
  });
  it('emphasizes the actual title and groups the technician with administrative tracking without losing fields', async () => {
    await loaded(); expect(root().querySelector('h2#intervention-title')?.textContent).toBe(record.title);
    const tracking = root().querySelector('[aria-labelledby="tracking-title"]')!;
    expect([...tracking.querySelectorAll('[data-field]')].map(e => e.getAttribute('data-field'))).toEqual(['technician', 'created_at', 'updated_at']);
    expect(root().querySelector('[aria-labelledby="technician-title"]')).toBeNull(); expect(root().querySelectorAll('section.maintenance-detail')).toHaveLength(6);
    expect(root().querySelector('.badge.status-badge')?.textContent).toBe('Planifiée'); expect(root().querySelector('.badge.priority-badge')?.textContent).toBe('Critique');
  });
  it('offers a safe explicit list destination on a direct visit with no return history', async () => {
    await loaded('/maintenance/17?returnUrl=https://example.invalid');
    const link = root().querySelector<HTMLAnchorElement>('.maintenance-back')!; expect(link.textContent).toBe('Retour à la liste des interventions');
    expect(link.getAttribute('href')).toBe('/maintenance'); link.focus(); expect(document.activeElement).toBe(link);
    link.click(); await settle(); expect(TestBed.inject(Router).url).toBe('/maintenance');
    http.expectOne(req => req.url === '/api/v1/companies').flush({ items: [], total: 0, page: 1, page_size: 50, pages: 0 }); await settle();
    http.expectNone(req => req.url === '/api/v1/maintenance');
  });
  it('retains precise ISO offsets and never assigns UTC to naive administrative dates', async () => {
    await loaded(); const date = root().querySelector('[data-field="planned_at"] time')!;
    expect(date.textContent).toBe('23/10/2026 à 12:00:00.123456 UTC'); expect(date.getAttribute('datetime')).toBe(record.planned_at);
    expect(value('created_at')).toContain(record.created_at + ' (fuseau non fourni)'); expect(value('created_at')).not.toContain(record.created_at + 'Z');
    expect(root().querySelector('[data-field="created_at"] code')?.textContent).toBe(record.created_at);
    expect(value('updated_at')).toContain('12:00:00.000001 UTC'); expect(value('started_at')).toBe('Non renseignée');
  });
  it.each([null, 0, 0.000001, 123456.789012, 1e25])('preserves cost %s without rounding or currency', async cost => {
    await loaded('/maintenance/17', { cost }); expect(value('cost')).toBe(cost === null ? 'Non renseigné' : String(cost));
  });
  it.each([null, 0, 123456])('preserves declared minutes %s without calculation', async downtime_minutes => {
    await loaded('/maintenance/17', { downtime_minutes }); expect(value('downtime_minutes')).toBe(downtime_minutes === null ? 'Non renseigné' : String(downtime_minutes));
  });
  it.each(['preventive', 'corrective', 'predictive'])('renders actual type %s', async maintenance_type => {
    await loaded('/maintenance/17', { maintenance_type }); expect(value('maintenance_type')).toBe(c.typeLabels[maintenance_type as keyof typeof c.typeLabels]);
  });
  it.each(['planned', 'in_progress', 'completed', 'cancelled'])('renders actual status %s without a transition control', async status => {
    await loaded('/maintenance/17', { status }); expect(value('status')).toBe(c.statusLabels[status as keyof typeof c.statusLabels]);
  });
  it.each(['low', 'medium', 'high', 'critical'])('renders actual priority %s', async priority => {
    await loaded('/maintenance/17', { priority }); expect(value('priority')).toBe(c.priorityLabels[priority as keyof typeof c.priorityLabels]);
  });
  it.each(['0', '-1', 'abc', 'new', '1.5', '1e2', '9007199254740992'])('blocks invalid id %s before HTTP', async id => {
    await open('/maintenance/' + id); expect(root().textContent).toContain('Identifiant invalide'); http.expectNone(() => true);
  });
  it.each([0, 400, 401, 403, 404, 422, 500])('distinguishes HTTP error %s and permits only manual transient retry', async status => {
    await open(); const req = read('maintenance/17'); if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' }); await settle();
    expect(c.state()).toMatchObject({ status: 'error', retryable: status === 0 || status >= 500 }); expect(root().querySelector('dl')).toBeNull();
    if (status === 404) expect(root().textContent).toContain('Intervention introuvable (404)'); if (status === 0) expect(root().textContent).toContain('Connexion impossible');
    c.retry(); if (status === 0 || status >= 500) { read('maintenance/17').flush(record); parents(); await settle(); expect(c.state().status).toBe('success'); } else http.expectNone(() => true);
  });
  it.each([{ id: 99 }, { equipment_id: 0 }, { maintenance_type: 'unknown' }, { status: 'unknown' }, { priority: 'unknown' }, { cost: NaN }, { cost: Infinity }, { cost: -1 }, { downtime_minutes: 1.5 }, { downtime_minutes: -1 }, { created_at: null }, { title: null }, { planned_at: '2026-10-23T12:00:00' }])('rejects invalid contract %j before parent HTTP', async override => {
    await open(); read('maintenance/17').flush({ ...record, ...override }); await settle(); expect(c.state()).toMatchObject({ status: 'error', title: 'Réponse invalide', retryable: false }); http.expectNone(() => true);
  });
  it('rejects a missing required field instead of creating an empty dossier', async () => {
    await open(); const { technician, ...incomplete } = record; read('maintenance/17').flush(incomplete); await settle(); expect(c.state().status).toBe('error'); expect(root().querySelector('dl')).toBeNull(); http.expectNone(() => true);
  });
  it('uses only actual ids, exposes Equipment after its read and never derives parents from URL', async () => {
    await open('/maintenance/17?company_id=99&site_id=88&equipment_id=77&status=completed&page=4');
    const request = read('maintenance/17'); expect(request.request.params.keys()).toHaveLength(0); request.flush(record); await settle();
    expect(value('title')).toBe(record.title); expect(root().querySelector('.equipment-reference')).toBeNull(); read('equipments/12').flush(equipment); await settle();
    expect(root().querySelector('.equipment-reference')?.getAttribute('href')).toBe('/equipments/12?site_id=9&page=1&page_size=20');
    read('sites/9').flush(site); read('companies/7').flush(company); await settle(); expect(root().textContent).toContain('diffère du contexte de retour');
    expect(c.equipmentQuery()).toEqual({ site_id: 9, company_id: 7, page: 1, page_size: 20 }); http.expectNone(() => true);
  });
  it.each([0, 1, 2])('preserves record and resolved parents when reference %s is absent', async index => {
    await open(); read('maintenance/17').flush(record); for (let n = 0; n < index; n++) read(paths[n]).flush(data[n]); read(paths[index]).flush({}, { status: 404, statusText: 'Missing' }); await settle();
    expect(c.state()).toMatchObject({ status: 'success', data: record, references: { [keys[index]]: { status: 'error', retryable: false } } });
    expect(value('title')).toBe(record.title); expect(root().textContent).toContain('L’intervention reste affichée');
    expect(!!root().querySelector('.equipment-reference')).toBe(index > 0); c.retryReferences(); http.expectNone(() => true);
  });
  it.each([0, 1, 2])('rejects incoherent actual reference %s', async index => {
    await open(); read('maintenance/17').flush(record); for (let n = 0; n < index; n++) read(paths[n]).flush(data[n]); read(paths[index]).flush({ ...data[index], id: 99 }); await settle();
    expect(c.state()).toMatchObject({ status: 'success', references: { [keys[index]]: { status: 'error', retryable: false } } }); expect(root().textContent).toContain('ne correspond pas au rattachement réel'); http.expectNone(() => true);
  });
  it.each([0, 1])('blocks invalid foreign key at reference %s', async index => {
    await open(); read('maintenance/17').flush(record); for (let n = 0; n < index; n++) read(paths[n]).flush(data[n]); read(paths[index]).flush({ ...data[index], [index === 0 ? 'site_id' : 'company_id']: 0 }); await settle();
    expect(c.state()).toMatchObject({ status: 'success', references: { [keys[index + 1]]: { status: 'error' } } }); expect(value('id')).toBe('17'); http.expectNone(() => true);
  });
  it.each([0, 403, 500])('preserves record on inaccessible parent %s and retries transient references only', async status => {
    await open(); read('maintenance/17').flush(record); const req = read('equipments/12'); if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' }); await settle();
    expect(value('id')).toBe('17'); c.retryReferences(); if (status === 0 || status >= 500) { parents(); await settle(); expect(c.state()).toMatchObject({ references: { company: { status: 'success' } } }); } http.expectNone(() => true);
  });
  it('preserves whitelist, raw microseconds, offsets, repeated filters and fragment on return', async () => {
    await loaded('/maintenance/17?' + context + '&search=second&returnUrl=https://example.invalid&extra=x#history');
    const link = root().querySelector<HTMLAnchorElement>('.maintenance-back')!; const tree = TestBed.inject(Router).parseUrl(link.getAttribute('href')!);
    expect(tree.queryParams).toEqual({ company_id: '7', site_id: '9', equipment_id: '12', maintenance_type: 'predictive', status: 'planned', priority: 'critical', search: ['Inspection', 'second'], start_time: record.planned_at, end_time: '2026-10-24T00:00:00.000001Z', page: '3', page_size: '50' });
    expect(tree.fragment).toBe('history'); expect(root().querySelector('a[href^="https:"]')).toBeNull();
    await TestBed.inject(Router).navigate([], { queryParams: { page: 4 }, queryParamsHandling: 'merge', preserveFragment: true }); await settle(); http.expectNone(() => true); expect(link.getAttribute('href')).toContain('page=4');
  });
  it('cancels stale detail and then stale parent requests on rapid navigation', async () => {
    await open(); const old = read('maintenance/17'); await h.navigateByUrl('/maintenance/18', MaintenanceDetailComponent); await settle(); expect(old.cancelled).toBe(true);
    read('maintenance/18').flush({ ...record, id: 18 }); const parent = read('equipments/12'); await h.navigateByUrl('/maintenance/19', MaintenanceDetailComponent); await settle(); expect(parent.cancelled).toBe(true); expect(root().querySelector('[data-field]')).toBeNull();
    read('maintenance/19').flush({}, { status: 404, statusText: 'Missing' }); await settle(); c.retryReferences(); http.expectNone(() => true);
  });
});
