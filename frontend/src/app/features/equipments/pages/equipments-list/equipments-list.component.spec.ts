import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbToastrService } from '@nebular/theme';
import { EQUIPMENT_ROUTES } from '../../equipments.routes';
import { EquipmentsListComponent } from './equipments-list.component';

const company = { id: 7, name: 'Entreprise test', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7, name: 'Usine 日本', code: 'SITE' };
const equipment = { ...company, id: 12, name: 'Pompe principale', code: 'POMPE', site_id: 9, equipment_type: 'Pompe', status: 'operational', criticality: 'high' };
const catalog = { items: [company], total: 1, page: 1, page_size: 50, pages: 1 };
const siteCatalog = { ...catalog, items: [site] };
const page = { items: [equipment], total: 21, page: 1, page_size: 20, pages: 2 };

describe('Equipments list, references and URL', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: EquipmentsListComponent;
  const root = () => harness.routeNativeElement!;
  const request = (url: string) => http.expectOne(req => req.url === `/api/v1/${url}`);
  const list = () => request('equipments');
  const button = (label: string) => [...root().querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent?.trim() === label)!;
  const url = () => TestBed.inject(Router).parseUrl(TestBed.inject(Router).url).queryParams;
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), { provide: NbToastrService, useValue: { success: vi.fn() } },
      provideRouter([{ path: 'equipments', children: EQUIPMENT_ROUTES }, { path: 'other', component: EquipmentsListComponent }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET'); http.verify(); });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(path = '/equipments') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(path, EquipmentsListComponent); await settle();
  }
  function parents() { request('companies/7').flush(company); request('sites/9').flush(site); }
  async function ready(path = '/equipments?company_id=7&site_id=9') {
    await open(path); request('companies').flush(catalog); request('sites').flush(siteCatalog); parents(); list().flush(page); await settle();
  }
  async function reload() { parents(); const req = list(); req.flush(page); await settle(); return req; }

  it('requires explicit selections and provides a real create link without delete actions', async () => {
    await open(); request('companies').flush(catalog); await settle();
    expect(component.company.value).toBeNull(); expect(component.site.value).toBeNull(); expect(component.site.disabled).toBe(true);
    expect(root().querySelector('#companies-help')).not.toBeNull(); expect(root().querySelector('#sites-help')).not.toBeNull();
    expect(root().querySelector('#equipments-company')?.getAttribute('aria-describedby')).toBe('companies-help');
    expect(root().querySelector('#equipments-site')?.getAttribute('aria-describedby')).toBe('sites-help');
    expect(root().textContent).toContain('Sélectionnez une entreprise puis un site');
    expect(root().querySelector('table')).toBeNull(); expect(root().querySelector('.new-equipment')?.getAttribute('href')).toBe('/equipments/new?page=1&page_size=20');
    expect(button('Rechercher').disabled).toBe(true); http.expectNone(() => true);
    component.company.setValue(7); await settle(); request('sites').flush(siteCatalog); request('companies/7').flush(company); await settle();
    expect(component.site.enabled).toBe(true); expect(component.site.value).toBeNull(); http.expectNone(() => true);
    expect(root().querySelector('#companies-help')).toBeNull(); expect(root().querySelector('#sites-help')).not.toBeNull();
    component.site.setValue(9); await settle(); await reload(); expect(component.facade.state().status).toBe('success');
  });
  it('navigates to creation with the seven applied context parameters', async () => {
    await ready('/equipments?company_id=7&site_id=9&status=maintenance&criticality=high&search=Pompe&page=2&page_size=50');
    root().querySelector<HTMLAnchorElement>('.new-equipment')!.click(); await settle();
    expect(root().querySelector('app-feature-placeholder')).toBeNull();
    request('companies').flush(catalog); request('companies/7').flush(company); request('sites/9').flush(site); request('sites').flush(siteCatalog); await settle();
    expect(TestBed.inject(Router).url).toBe('/equipments/new?company_id=7&site_id=9&page=2&page_size=50&search=Pompe&status=maintenance&criticality=high');
    expect(root().querySelector<HTMLSelectElement>('#equipment-site_id')?.selectedOptions[0].textContent).toContain(site.name);
  });
  it('hides only verified parent guidance and restores it when selections are cleared', async () => {
    await ready();
    expect(root().querySelector('#companies-help')).toBeNull(); expect(root().querySelector('#sites-help')).toBeNull();
    expect(root().querySelector('#equipments-company')?.hasAttribute('aria-describedby')).toBe(false);
    expect(root().querySelector('#equipments-site')?.hasAttribute('aria-describedby')).toBe(false);
    component.site.setValue(null); await settle(); request('companies/7').flush(company); await settle();
    expect(root().querySelector('#companies-help')).toBeNull(); expect(root().querySelector('#sites-help')).not.toBeNull();
    component.company.setValue(null); await settle();
    expect(root().querySelector('#companies-help')).not.toBeNull(); expect(root().querySelector('#sites-help')).not.toBeNull();
    http.expectNone(() => true);
  });
  it.each(['company', 'site'])('keeps guidance for an unavailable %s reference', async parent => {
    await open('/equipments?company_id=7&site_id=9'); request('companies').flush(catalog); request('sites').flush(siteCatalog);
    if (parent === 'company') request('companies/7').flush({}, { status: 404, statusText: 'Not found' });
    else { request('companies/7').flush(company); request('sites/9').flush({}, { status: 404, statusText: 'Not found' }); }
    await settle();
    expect(root().querySelector('#companies-help') !== null).toBe(parent === 'company');
    expect(root().querySelector('#sites-help')).not.toBeNull(); expect(root().querySelector('table')).toBeNull(); http.expectNone(() => true);
  });
  it.each([0, 1, 2, 21])('renders French count %s consistently without changing filters or URL context', async total => {
    const path = '/equipments?company_id=7&site_id=9&status=operational&criticality=high&search=Pompe&page=2&page_size=50&tab=keep#context';
    await open(path); request('companies').flush(catalog); request('sites').flush(siteCatalog); parents();
    const req = list(); expect(req.request.params.get('status')).toBe('operational'); expect(req.request.params.get('criticality')).toBe('high');
    expect(req.request.params.get('search')).toBe('Pompe'); expect(req.request.params.get('page')).toBe('2'); expect(req.request.params.get('page_size')).toBe('50');
    req.flush({ ...page, total, page: 2, page_size: 50, pages: total ? 2 : 0, items: total ? [equipment] : [] }); await settle();
    const count = `${total} ${total > 1 ? 'équipements' : 'équipement'}`;
    if (total) {
      expect(root().querySelector('caption')?.textContent).toContain(count);
      expect(root().querySelector('.pagination [role="status"]')?.textContent).toContain(count);
      expect(root().querySelector('tbody a')?.getAttribute('href')).toContain('status=operational');
    } else expect(root().querySelector('.results > [role="status"]')?.textContent?.trim()).toBe(count);
    expect(root().textContent).not.toContain('équipement(s)'); expect(TestBed.inject(Router).url).toBe(path);
    expect(component.status.value).toBe('operational'); expect(component.criticality.value).toBe('high');
    expect(component.search.value).toBe('Pompe'); expect(root().querySelector('#companies-help')).toBeNull(); expect(root().querySelector('#sites-help')).toBeNull();
    http.expectNone(() => true);
  });
  it('renders the five business columns, translated enums and context-preserving detail link', async () => {
    await ready(); expect(root().querySelectorAll('thead th[scope="col"]')).toHaveLength(5);
    expect(root().textContent).toContain('Opérationnel'); expect(root().textContent).toContain('Élevée');
    expect(root().textContent).toContain('Usine 日本 - SITE');
    expect(root().querySelector('tbody a')?.getAttribute('href')).toBe('/equipments/12?company_id=7&site_id=9&page=1&page_size=20');
    const link = root().querySelector<HTMLAnchorElement>('tbody a')!; link.focus(); expect(document.activeElement).toBe(link);
    expect(root().querySelector('.table-scroll')?.getAttribute('tabindex')).toBe('0');
    expect(root().textContent).not.toContain('site_id'); expect(root().textContent).not.toContain('company_id');
  });
  it('loads both catalogs page by page and deduplicates references', async () => {
    await open(); request('companies').flush({ ...catalog, total: 51, pages: 2 }); await settle();
    button('Charger plus d’entreprises').click(); const companies = request('companies');
    expect(companies.request.params.get('page')).toBe('2'); expect(companies.request.params.get('page_size')).toBe('50');
    companies.flush({ ...catalog, items: [company, { ...company, id: 8, name: 'Seconde entreprise' }], total: 51, page: 2, pages: 2 }); await settle();
    expect(component.companyOptions()).toHaveLength(2);
    component.company.setValue(7); await settle(); request('companies/7').flush(company);
    request('sites').flush({ ...siteCatalog, total: 51, pages: 2 }); await settle();
    button('Charger plus de sites').click(); const sites = request('sites');
    expect(sites.request.params.get('page')).toBe('2'); expect(sites.request.params.get('company_id')).toBe('7');
    sites.flush({ ...siteCatalog, items: [site, { ...site, id: 10, name: 'Site suivant' }], total: 51, page: 2, pages: 2 }); await settle();
    expect(component.siteOptions()).toHaveLength(2); expect(component.site.value).toBeNull(); http.expectNone(() => true);
  });
  it('resolves company and site outside their first catalog pages', async () => {
    await open('/equipments?company_id=7&site_id=9');
    request('companies').flush({ ...catalog, items: [], total: 51, pages: 2 });
    request('sites').flush({ ...siteCatalog, items: [], total: 51, pages: 2 }); parents(); list().flush(page); await settle();
    expect(component.companyOptions()).toEqual([company]); expect(component.siteOptions()).toEqual([site]);
    expect(root().querySelector<HTMLSelectElement>('#equipments-site')!.selectedOptions[0].textContent).toContain('Usine 日本');
  });
  it('resolves a site-only URL to its real company and normalizes its context', async () => {
    await open('/equipments?site_id=9'); request('companies').flush(catalog);
    request('sites/9').flush(site); request('companies/7').flush(company); const initial = list();
    await settle(); request('sites').flush(siteCatalog);
    expect(initial.cancelled).toBe(false); initial.flush(page);
    await settle(); expect(url()['company_id']).toBe('7'); expect(component.site.value).toBe(9);
    expect(component.siteOptions()).toContainEqual(site);
  });
  it('blocks a mismatched URL context without equipment data', async () => {
    await open('/equipments?company_id=7&site_id=9'); request('companies').flush(catalog); request('sites').flush(siteCatalog);
    request('companies/7').flush(company); request('sites/9').flush({ ...site, company_id: 8 }); await settle();
    expect(root().textContent).toContain('n’appartient pas'); expect(root().querySelector('table')).toBeNull(); http.expectNone(() => true);
    expect(root().querySelector('#companies-help')).toBeNull(); expect(root().querySelector('#sites-help')).not.toBeNull();
  });
  it.each(['company_id=0&site_id=9', 'company_id=abc&site_id=9', 'site_id=-1', 'site_id=9007199254740992'])('normalizes invalid parent parameters %s without unscoped requests', async params => {
    await open(`/equipments?${params}`); request('companies').flush(catalog); await settle();
    expect(component.facade.state().status).toBe('idle'); expect(url()['site_id']).toBeUndefined();
    expect(root().textContent).toContain('normalisés'); http.expectNone(() => true);
  });
  it('normalizes invalid pagination/enums and retains unrelated URL context', async () => {
    await open('/equipments?page=-2&page_size=101&status=broken&criticality=invalid&search=%20%20&tab=keep#context');
    request('companies').flush(catalog); await settle();
    expect(url()).toEqual({ tab: 'keep', page: '1', page_size: '20' });
    expect(TestBed.inject(Router).url).toContain('#context'); http.expectNone(() => true);
  });
  it('accepts a valid URL page size outside the standard options', async () => {
    await open('/equipments?company_id=7&site_id=9&page_size=1'); request('companies').flush(catalog); request('sites').flush(siteCatalog); parents();
    const req = list(); expect(req.request.params.get('page_size')).toBe('1'); req.flush({ ...page, page_size: 1 }); await settle();
    expect(component.sizes()).toEqual([1, 20, 50, 100]); expect(component.size.value).toBe(1);
  });
  it('searches only on submit and sends exact combined filters with page reset', async () => {
    await ready('/equipments?company_id=7&site_id=9&status=maintenance&criticality=critical&page=2');
    const input = root().querySelector<HTMLInputElement>('#equipments-search')!;
    input.value = '  Pompe type  '; input.dispatchEvent(new Event('input', { bubbles: true })); await settle(); http.expectNone(() => true);
    root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle();
    parents(); const req = list(); expect(req.request.params.get('search')).toBe('Pompe type');
    expect(req.request.params.get('status')).toBe('maintenance'); expect(req.request.params.get('criticality')).toBe('critical');
    expect(req.request.params.get('page')).toBe('1'); expect(req.request.params.has('company_id')).toBe(false); req.flush(page); await settle();
    button('Effacer la recherche').click(); await settle(); const cleared = await reload(); expect(cleared.request.params.has('search')).toBe(false);
  });
  it.each(['status', 'criticality', 'size'] as const)('resets page on %s change and preserves the applied search snapshot', async field => {
    await ready('/equipments?company_id=7&site_id=9&page=2&search=applied'); component.search.setValue('draft');
    if (field === 'status') component.status.setValue('out_of_service');
    if (field === 'criticality') component.criticality.setValue('low');
    if (field === 'size') component.size.setValue(100);
    await settle(); const req = await reload(); expect(req.request.params.get('page')).toBe('1');
    expect(req.request.params.get('search')).toBe('applied');
    expect(req.request.params.get(field === 'size' ? 'page_size' : field)).toBe(field === 'size' ? '100' : field === 'status' ? 'out_of_service' : 'low');
  });
  it('paginates server-side and restores filters on browser-style back navigation', async () => {
    await ready('/equipments?company_id=7&site_id=9&status=operational'); button('Suivant').click(); await settle();
    let req = await reload(); expect(req.request.params.get('page')).toBe('2');
    await harness.navigateByUrl('/equipments?company_id=7&site_id=9&status=operational&page=1&page_size=20'); await settle();
    req = await reload(); expect(req.request.params.get('page')).toBe('1'); expect(component.status.value).toBe('operational');
  });
  it('cancels old equipment and site catalog requests when the company changes', async () => {
    await open('/equipments?company_id=7&site_id=9&search=old&status=maintenance&criticality=high&page=3');
    request('companies').flush(catalog); const oldCatalog = request('sites'); parents(); const oldList = list();
    component.company.setValue(8); expect(oldList.cancelled).toBe(true); expect(oldCatalog.cancelled).toBe(true); await settle();
    expect(root().querySelector('table')).toBeNull(); expect(component.site.value).toBeNull(); expect(component.search.value).toBe('');
    expect(url()).toMatchObject({ company_id: '8', page: '1', status: 'maintenance', criticality: 'high' }); expect(url()['site_id']).toBeUndefined();
    request('companies/8').flush({ ...company, id: 8 }); request('sites').flush({ ...siteCatalog, items: [] }); await settle(); http.expectNone(() => true);
  });
  it('resets page on site change without submitting a draft search', async () => {
    await ready('/equipments?company_id=7&site_id=9&search=applied&page=2'); component.search.setValue('draft'); component.site.setValue(10); await settle();
    request('companies/7').flush(company); request('sites/10').flush({ ...site, id: 10 }); const req = list();
    expect(req.request.params.get('site_id')).toBe('10'); expect(req.request.params.get('page')).toBe('1'); expect(req.request.params.get('search')).toBe('applied');
    req.flush({ ...page, items: [] }); await settle(); expect(root().querySelector('table')).toBeNull();
  });
  it('shows loading, empty, filtered-empty and out-of-range states', async () => {
    await open('/equipments?company_id=7&site_id=9'); request('companies').flush(catalog); request('sites').flush(siteCatalog);
    expect(root().textContent).toContain('Vérification du contexte'); parents(); list().flush({ ...page, items: [], total: 0, pages: 0 }); await settle();
    expect(root().textContent).toContain('Aucun équipement');
    component.status.setValue('maintenance'); await settle(); parents(); list().flush({ ...page, items: [], total: 0, pages: 0 }); await settle();
    expect(root().textContent).toContain('Aucun résultat'); button('Effacer les critères').click(); await settle(); await reload();
    await harness.navigateByUrl('/equipments?company_id=7&site_id=9&page=99'); await settle(); parents(); list().flush({ ...page, page: 99, items: [] }); await settle();
    expect(root().textContent).toContain('Page hors plage'); button('Revenir aux résultats').click(); await settle();
    const recovered = await reload(); expect(recovered.request.params.get('page')).toBe('2');
  });
  it('clears displayed results on error and offers a safe manual retry', async () => {
    await ready(); component.status.setValue('maintenance'); await settle(); parents(); list().flush({}, { status: 500, statusText: 'Error' }); await settle();
    expect(root().querySelector('table')).toBeNull(); expect(root().textContent).toContain('Chargement impossible'); component.facade.retry(); await reload();
    expect(root().querySelector('table')).not.toBeNull();
  });
  it('retries paginated catalogs after transient errors and rejects cross-company sites', async () => {
    await open(); request('companies').flush({}, { status: 500, statusText: 'Error' }); await settle();
    button('Réessayer les entreprises').click(); request('companies').flush(catalog); component.company.setValue(7); await settle(); request('companies/7').flush(company);
    request('sites').flush({}, { status: 500, statusText: 'Error' }); await settle(); button('Réessayer les sites').click();
    request('sites').flush({ ...siteCatalog, items: [{ ...site, company_id: 8 }] }); await settle();
    expect(component.sites().status).toBe('error'); expect(component.siteOptions()).toHaveLength(0); http.expectNone(() => true);
  });
  it('blocks oversized searches and keeps accessible labels on every control', async () => {
    await ready(); component.search.setValue('x'.repeat(101)); component.applySearch(); await settle();
    expect(root().textContent).toContain('La recherche dépasse'); http.expectNone(() => true);
    for (const control of root().querySelectorAll<HTMLInputElement>('input, select')) expect(root().querySelector(`label[for="${control.id}"]`)).not.toBeNull();
  });
  it('cancels pending GETs when leaving the feature', async () => {
    await open('/equipments?company_id=7&site_id=9'); const companies = request('companies'), sites = request('sites'), parent = request('companies/7');
    harness.fixture.destroy(); expect(companies.cancelled).toBe(true); expect(sites.cancelled).toBe(true); expect(parent.cancelled).toBe(true);
  });
});
