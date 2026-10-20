import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbToastrService } from '@nebular/theme';
import { SENSOR_ROUTES } from '../../sensors.routes';
import { SensorsListComponent } from './sensors-list.component';

const company = { id: 7, name: 'Entreprise test', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7, name: 'Usine 日本', code: 'SITE' };
const equipment = { ...company, id: 12, site_id: 9, name: 'Pompe principale', code: 'POMPE', equipment_type: 'pump', status: 'operational', criticality: 'high' };
const sensor = { ...company, id: 17, equipment_id: 12, name: 'Température palier', code: 'TEMP', sensor_type: 'temperature', unit: '°C', status: 'active' };
const catalog = { items: [company], total: 1, page: 1, page_size: 50, pages: 1 };
const page = { items: [sensor], total: 21, page: 1, page_size: 20, pages: 2 };

describe('Sensors list, references and URL integration', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: SensorsListComponent;
  const root = () => harness.routeNativeElement!;
  const request = (url: string) => http.expectOne(req => req.url === `/api/v1/${url}`);
  const list = () => request('sensors');
  const button = (label: string) => [...root().querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent?.trim() === label)!;
  const url = () => TestBed.inject(Router).parseUrl(TestBed.inject(Router).url).queryParams;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [{ provide: NbToastrService, useValue: { success: vi.fn() } }, provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'sensors', children: SENSOR_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.expectNone(req => req.method !== 'GET'); http.verify(); } finally { TestBed.resetTestingModule(); } });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(path = '/sensors') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(path, SensorsListComponent); await settle();
  }
  function parents() { request('equipments/12').flush(equipment); request('sites/9').flush(site); request('companies/7').flush(company); }
  function catalogs() { request('sites').flush({ ...catalog, items: [site] }); request('equipments').flush({ ...catalog, items: [equipment] }); }
  async function ready(path = '/sensors?company_id=7&site_id=9&equipment_id=12') {
    await open(path); request('companies').flush(catalog); parents(); await settle(); catalogs(); list().flush(page); await settle();
  }
  async function reload() { parents(); const req = list(); req.flush(page); await settle(); return req; }

  it('waits for all three explicit selections even when each catalog contains one option', async () => {
    await open(); request('companies').flush(catalog); await settle();
    expect(component.company.value).toBeNull(); expect(component.site.disabled).toBe(true); expect(component.equipment.disabled).toBe(true);
    expect(button('Rechercher').disabled).toBe(true); expect(root().textContent).toContain('Sélectionnez une entreprise, puis un site et un équipement');
    http.expectNone(() => true);
    component.company.setValue(7); await settle(); request('companies/7').flush(company); await settle();
    request('sites').flush({ ...catalog, items: [site] }); await settle();
    expect(component.site.enabled).toBe(true); expect(component.site.value).toBeNull(); expect(component.equipment.disabled).toBe(true);
    component.site.setValue(9); await settle(); request('sites/9').flush(site); request('companies/7').flush(company); await settle();
    request('equipments').flush({ ...catalog, items: [equipment] }); await settle();
    expect(component.equipment.enabled).toBe(true); expect(component.equipment.value).toBeNull(); http.expectNone(() => true);
    component.equipment.setValue(12); await settle(); await reload(); expect(component.facade.state().status).toBe('success');
  });
  it('shows the five columns and French status, linking to the read-only detail with applied context', async () => {
    await ready();
    expect([...root().querySelectorAll('thead th')].map(el => el.textContent)).toEqual(['Nom', 'Code', 'Type', 'Unité', 'Statut']);
    expect(root().textContent).toContain('Actif'); expect(root().textContent).toContain('°C'); expect(root().textContent).toContain('Pompe principale - POMPE');
    const link = root().querySelector('.sensor-detail-link')!;
    expect(link.getAttribute('href')).toBe('/sensors/17?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20');
    expect(link.hasAttribute('aria-disabled')).toBe(false);
    expect(root().querySelector('a[href*="/new"]')).not.toBeNull();
    expect(root().querySelector('.table-scroll')?.getAttribute('tabindex')).toBe('0');
    expect(root().querySelectorAll('label[for]')).toHaveLength(6);
    expect(root().querySelectorAll('.results .scroll-help')).toHaveLength(1);
    expect(root().querySelector('.scroll-help')?.textContent).toBe('Sur petit écran, faites défiler le tableau horizontalement.');
  });
  it('opens the real detail from a paginated filtered list without changing its applied snapshot', async () => {
    await ready('/sensors?company_id=7&site_id=9&equipment_id=12&page=2&page_size=20&search=TEMP&status=active');
    root().querySelector<HTMLAnchorElement>('.sensor-detail-link')!.click(); await settle();
    expect(TestBed.inject(Router).url).toBe('/sensors/17?company_id=7&site_id=9&equipment_id=12&page=2&page_size=20&status=active&search=TEMP');
    request('sensors/17').flush(sensor); parents(); await settle();
    expect(root().querySelector('h1')?.textContent).toBe('Détail capteur');
    expect(root().querySelector('.sensor-back')?.getAttribute('href')).toBe('/sensors?company_id=7&site_id=9&equipment_id=12&page=2&page_size=20&search=TEMP&status=active');
    http.expectNone(() => true);
  });
  it('keeps a keyboard-accessible create action available without a selected parent', async () => {
    await open(); request('companies').flush(catalog); await settle();
    const action = root().querySelector<HTMLAnchorElement>('.new-sensor')!;
    expect(action.textContent?.trim()).toBe('Nouveau capteur'); expect(action.hasAttribute('title')).toBe(false);
    expect(action.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true');
    expect(action.getAttribute('href')).toBe('/sensors/new?return_page=1&return_page_size=20');
    action.focus(); expect(document.activeElement).toBe(action); action.click(); await settle(); request('companies').flush(catalog); await settle();
    expect(root().querySelector('app-sensor-form')).not.toBeNull(); http.expectNone(() => true);
  });
  it('separates verified prefill from the complete return snapshot and navigates once', async () => {
    await ready('/sensors?company_id=7&site_id=9&equipment_id=12&page=2&page_size=50&search=TEMP&status=inactive');
    const query = component.newQuery(); expect(query).toMatchObject({ company_id: 7, site_id: 9, equipment_id: 12, return_page: 2, return_page_size: 50, return_search: 'TEMP', return_status: 'inactive' });
    const router = TestBed.inject(Router), spy = vi.spyOn(router, 'navigateByUrl');
    root().querySelector<HTMLAnchorElement>('.new-sensor')!.click(); await settle();
    request('companies').flush(catalog); request('companies/7').flush(company); request('sites/9').flush(site); request('equipments/12').flush(equipment);
    request('sites').flush({ ...catalog, items: [site] }); request('equipments').flush({ ...catalog, items: [equipment] }); await settle();
    expect(spy).toHaveBeenCalledTimes(1); expect(root().querySelector('h1')?.textContent).toBe('Nouveau capteur industriel');
  });
  it('does not pass partial selection as prefill but keeps it for cancellation', async () => {
    await open('/sensors?company_id=7'); request('companies').flush(catalog); request('companies/7').flush(company); await settle();
    request('sites').flush({ ...catalog, items: [site] }); await settle();
    expect(component.newQuery()).toMatchObject({ return_company_id: 7 }); expect(component.newQuery()['company_id']).toBeUndefined();
  });
  it('searches only on submission, trims search and retains only the applied search on status changes', async () => {
    await ready(); component.search.setValue('  mm/s  '); await settle(); http.expectNone(() => true);
    root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle();
    const search = await reload(); expect(search.request.params.get('search')).toBe('mm/s'); expect(url()['search']).toBe('mm/s');
    component.search.setValue('Draft'); component.status.setValue('inactive'); await settle();
    const status = await reload(); expect(status.request.params.get('search')).toBe('mm/s'); expect(status.request.params.get('status')).toBe('inactive');
    component.clearSearch(); await settle(); expect((await reload()).request.params.has('search')).toBe(false);
  });
  it('blocks overlong search without HTTP and resets pagination when changing size', async () => {
    await ready(); component.search.setValue('x'.repeat(101)); component.applySearch(); await settle();
    expect(root().querySelector('#sensors-search-error')?.textContent).toContain('100 caractères'); http.expectNone(() => true);
    component.size.setValue(50); await settle(); const req = await reload();
    expect(req.request.params.get('page_size')).toBe('50'); expect(req.request.params.get('page')).toBe('1');
  });
  it('uses server pagination and keeps all context parameters on prepared detail links', async () => {
    await ready('/sensors?company_id=7&site_id=9&equipment_id=12&status=active&search=TEMP&page=1&page_size=20&tab=keep#context');
    button('Suivant').click(); await settle(); const req = await reload(); expect(req.request.params.get('page')).toBe('2');
    expect(url()['company_id']).toBe('7'); expect(url()['site_id']).toBe('9'); expect(url()['equipment_id']).toBe('12'); expect(url()['tab']).toBe('keep');
    expect(TestBed.inject(Router).url).toContain('#context');
    const target = component.detailUrl(17); expect(target).toContain('page=2'); expect(target).toContain('status=active'); expect(target).toContain('search=TEMP');
    expect(req.request.params.has('company_id')).toBe(false); expect(req.request.params.has('site_id')).toBe(false);
  });
  it.each([0, 1, 21])('renders count %s, empty state and pagination consistently', async total => {
    await open('/sensors?company_id=7&site_id=9&equipment_id=12'); request('companies').flush(catalog); parents(); await settle(); catalogs();
    list().flush({ ...page, total, items: total ? [sensor] : [], pages: total ? 2 : 0 }); await settle();
    expect(root().textContent).toContain(`${total} ${total > 1 ? 'capteurs' : 'capteur'}`);
    expect(root().querySelector('.pagination') !== null).toBe(total > 0);
    if (!total) { expect(root().textContent).toContain('Aucun capteur'); expect(root().querySelector('.scroll-help')).toBeNull(); }
  });
  it('distinguishes filtered empty from out-of-range and recovers a page manually', async () => {
    await open('/sensors?company_id=7&site_id=9&equipment_id=12&status=inactive&page=99');
    request('companies').flush(catalog); parents(); await settle(); catalogs();
    list().flush({ ...page, page: 99, items: [], pages: 2 }); await settle(); expect(root().textContent).toContain('Page hors plage'); expect(root().querySelector('.scroll-help')).toBeNull(); http.expectNone(() => true);
    button('Revenir aux résultats').click(); await settle(); parents();
    const req = list(); expect(req.request.params.get('page')).toBe('2'); req.flush({ ...page, items: [], total: 0, pages: 0 }); await settle();
    expect(root().textContent).toContain('Aucun résultat'); button('Effacer les critères').click(); await settle();
    expect((await reload()).request.params.has('status')).toBe(false);
  });
  it.each(['company_id', 'site_id', 'equipment_id'])('blocks invalid URL %s without loading a broader scope', async field => {
    await open('/sensors?' + new URLSearchParams({ company_id: '7', site_id: '9', equipment_id: '12', [field]: '0' }));
    request('companies').flush(catalog); await settle();
    expect(root().textContent).toContain('périmètre de l’URL est invalide'); http.expectNone(() => true);
    component.company.setValue(7); await settle(); request('companies/7').flush(company); await settle();
    request('sites').flush({ ...catalog, items: [site] }); await settle();
    expect(component.urlNotice()).toBe(''); expect(url()['site_id']).toBeUndefined(); expect(url()['equipment_id']).toBeUndefined();
    http.expectNone(() => true);
  });
  it('normalizes filter bounds before any Sensors read without losing the equipment scope', async () => {
    await open('/sensors?equipment_id=12&page=0&page_size=101&status=bad&search=%20TEMP%20');
    request('companies').flush(catalog); parents(); await settle(); catalogs();
    const req = list(); expect(req.request.params.get('page')).toBe('1'); expect(req.request.params.get('page_size')).toBe('20');
    expect(req.request.params.get('search')).toBe('TEMP'); expect(req.request.params.has('status')).toBe(false);
    req.flush(page); await settle(); expect(url()['company_id']).toBe('7'); expect(url()['site_id']).toBe('9');
  });
  it('resolves references outside first catalog pages without automatic child selection', async () => {
    await open('/sensors?equipment_id=12'); request('companies').flush({ ...catalog, items: [], total: 51, pages: 2 }); parents(); await settle();
    request('sites').flush({ ...catalog, items: [], total: 51, pages: 2 }); request('equipments').flush({ ...catalog, items: [], total: 51, pages: 2 }); list().flush(page); await settle();
    expect(component.companyOptions()).toEqual([company]); expect(component.siteOptions()).toEqual([site]); expect(component.equipmentOptions()).toEqual([equipment]);
    expect(url()['company_id']).toBe('7'); expect(url()['site_id']).toBe('9'); expect(url()['equipment_id']).toBe('12'); http.expectNone(() => true);
  });
  it('loads and deduplicates all three catalogs page by page', async () => {
    await ready();
    component.companies.update(value => ({ ...value, total: 51, pages: 2 }));
    component.sites.update(value => ({ ...value, total: 51, pages: 2 }));
    component.equipments.update(value => ({ ...value, total: 51, pages: 2 })); await settle();
    for (const [label, path, item] of [['entreprises', 'companies', company], ['sites', 'sites', site], ['équipements', 'equipments', equipment]] as const) {
      button(label === 'sites' ? 'Charger plus de sites' : `Charger plus d’${label}`).click(); const req = request(path);
      expect(req.request.params.get('page')).toBe('2'); expect(req.request.params.get('page_size')).toBe('50');
      req.flush({ ...catalog, items: [item, { ...item, id: 51 }], total: 51, page: 2, pages: 2 }); await settle();
    }
    expect(component.companyOptions()).toHaveLength(2); expect(component.siteOptions()).toHaveLength(2); expect(component.equipmentOptions()).toHaveLength(2);
  });
  it('keeps loaded catalog pages after failure and retries the failed page explicitly', async () => {
    await ready(); component.equipments.update(value => ({ ...value, total: 51, pages: 2 })); await settle();
    button('Charger plus d’équipements').click(); request('equipments').flush({}, { status: 500, statusText: 'Error' }); await settle();
    expect(component.equipmentOptions()).toEqual([equipment]); button('Réessayer les équipements').click();
    const req = request('equipments'); expect(req.request.params.get('page')).toBe('2');
    req.flush({ ...catalog, items: [{ ...equipment, id: 51 }], total: 51, page: 2, pages: 2 }); await settle(); expect(component.equipmentOptions()).toHaveLength(2);
  });
  it('rejects a mismatched equipment catalog and a contradictory explicit context', async () => {
    await open('/sensors?company_id=7&site_id=9'); request('companies').flush(catalog);
    request('sites/9').flush(site); request('companies/7').flush(company); await settle();
    request('sites').flush({ ...catalog, items: [site] }); request('equipments').flush({ ...catalog, items: [{ ...equipment, site_id: 99 }] }); await settle();
    expect(component.equipments().status).toBe('error'); expect(component.equipmentOptions()).toEqual([]);
    await TestBed.inject(Router).navigateByUrl('/sensors?company_id=7&site_id=99&equipment_id=12'); await settle();
    request('equipments/12').flush(equipment); await settle(); expect(root().textContent).toContain('n’appartient pas au site'); http.expectNone(() => true);
  });
  it('clears descendants and search on a parent change, retaining status and size', async () => {
    await ready('/sensors?company_id=7&site_id=9&equipment_id=12&status=inactive&search=TEMP&page=2&page_size=50');
    component.company.setValue(8); await settle(); request('companies/8').flush({ ...company, id: 8 }); await settle();
    request('sites').flush({ ...catalog, items: [], total: 0, pages: 0 }); await settle();
    expect(component.site.value).toBeNull(); expect(component.equipment.value).toBeNull(); expect(root().querySelector('table')).toBeNull();
    expect(url()['search']).toBeUndefined(); expect(url()['status']).toBe('inactive'); expect(url()['page_size']).toBe('50'); expect(url()['page']).toBe('1'); http.expectNone(() => true);
  });
  it('keeps verified parents available to correct a search after a Sensors error', async () => {
    await ready(); component.search.setValue('HTTP-500'); component.applySearch(); await settle(); parents();
    list().flush({}, { status: 500, statusText: 'Error' }); await settle();
    expect(root().textContent).toContain('Chargement impossible'); expect(button('Rechercher').disabled).toBe(false);
    expect(component.facade.company()).toEqual(company); expect(component.facade.site()).toEqual(site);
    component.search.setValue('TEMP'); component.applySearch(); await settle();
    expect((await reload()).request.params.get('search')).toBe('TEMP');
    expect(root().querySelector('table')).not.toBeNull(); http.expectNone(() => true);
  });
  it('cancels old catalog pages and sensor responses on rapid parent changes', async () => {
    await ready(); component.equipments.update(value => ({ ...value, total: 51, pages: 2 })); component.moreEquipments();
    const oldCatalog = request('equipments');
    component.status.setValue('inactive'); await settle(); parents(); const oldSensors = list();
    component.company.setValue(8); await settle(); expect(oldCatalog.cancelled).toBe(true); expect(oldSensors.cancelled).toBe(true);
    request('companies/8').flush({ ...company, id: 8 }); await settle(); request('sites').flush({ ...catalog, items: [], total: 0, pages: 0 }); await settle(); http.expectNone(() => true);
  });
});
