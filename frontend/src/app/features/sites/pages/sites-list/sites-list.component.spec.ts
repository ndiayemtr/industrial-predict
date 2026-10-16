import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { SITE_ROUTES } from '../../sites.routes';
import { SitesListComponent } from './sites-list.component';

const company = { id: 7, name: 'Entreprise test', code: 'C7', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 3, company_id: 7, name: 'Usine 日本', code: 'SITE-3' };
const catalog = { items: [company], total: 1, page: 1, page_size: 50, pages: 1 };
const page = { items: [site], total: 21, page: 1, page_size: 20, pages: 2 };

describe('Sites list page and URL', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: SitesListComponent;
  const root = () => harness.routeNativeElement!;
  const button = (name: string) => [...root().querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent?.trim() === name)!;
  const list = () => http.expectOne(req => req.url === '/api/v1/sites');
  const companies = () => http.expectOne(req => req.url === '/api/v1/companies');
  const parent = (id = 7) => http.expectOne(`/api/v1/companies/${id}`);
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'sites', children: SITE_ROUTES }, { path: 'other', component: SitesListComponent }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET'); http.verify(); });
  async function settle() {
    harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges();
  }
  async function open(url = '/sites') {
    harness = await RouterTestingHarness.create();
    component = await harness.navigateByUrl(url, SitesListComponent); await settle();
  }
  async function ready(url = '/sites?company_id=7') {
    await open(url); companies().flush(catalog); parent().flush(company); list().flush(page); await settle();
  }
  async function search(text: string) {
    const input = root().querySelector<HTMLInputElement>('#sites-search')!;
    input.value = text; input.dispatchEvent(new Event('input', { bubbles: true }));
    root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle();
  }

  it('loads the company catalog without automatically selecting a company or requesting sites', async () => {
    await open(); companies().flush(catalog); await settle();
    expect(component.company.value).toBeNull(); expect(component.facade.state().status).toBe('idle');
    expect(root().querySelector('#companies-help')?.textContent).toBe('Sélectionnez une entreprise pour afficher ses sites.');
    expect(root().querySelector('#sites-company')?.getAttribute('aria-describedby')).toBe('companies-help companies-count');
    expect(root().textContent).toContain('Sélectionnez une entreprise pour consulter ses sites');
    expect(root().querySelector('table')).toBeNull(); expect(root().querySelectorAll('a')).toHaveLength(0);
    expect(button('Rechercher').disabled).toBe(true); http.expectNone(() => true);
  });

  it('renders semantic fields and a focusable detail link without write actions', async () => {
    await ready();
    expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(root().querySelectorAll('thead th[scope="col"]')).toHaveLength(3);
    expect(root().querySelector('tbody th[scope="row"]')?.textContent).toBe(site.name);
    expect(root().querySelector('caption')?.textContent?.trim()).toBe('21 sites trouvés');
    expect(root().textContent).not.toContain('identifiant');
    expect(root().querySelector('.selected-company')?.textContent).toContain('Entreprise test - C7');
    expect(root().textContent).toContain('Non renseignée'); expect(root().querySelectorAll('a')).toHaveLength(1);
    const detail = root().querySelector<HTMLAnchorElement>('tbody a')!;
    expect(detail.getAttribute('href')).toBe('/sites/3?company_id=7&page=1&page_size=20');
    detail.focus(); expect(document.activeElement).toBe(detail);
    expect(root().textContent).not.toContain('Nouveau site');
    expect(root().querySelector('#companies-help')).toBeNull();
    expect(root().querySelector('#sites-company')?.getAttribute('aria-describedby')).toBe('companies-count');
    expect(root().querySelector('nav.pagination')).not.toBeNull();
    expect(root().textContent?.replace(/\s+/g, ' ')).toContain('21 sites - 2 pages');
  });

  it('restores company guidance on deselection while retaining the catalog information', async () => {
    await ready();
    expect(root().querySelector('#companies-count')?.textContent).toContain('1 / 1 entreprises chargées');
    component.company.setValue(null); await settle();
    expect(root().querySelector('#companies-help')?.textContent).toBe('Sélectionnez une entreprise pour afficher ses sites.');
    expect(root().querySelector('#companies-count')?.textContent).toContain('1 / 1 entreprises chargées');
    http.expectNone(() => true);
  });

  it.each([['PETROSEN', 'PETROSEN', 'PETROSEN'], ['PETROSEN', 'PTR-001', 'PETROSEN - PTR-001']])(
    'shows business company labels for %s / %s while preserving numeric URL and HTTP filters', async (name, code, expected) => {
      await open('/sites?company_id=7&page_size=1');
      const selected = { ...company, name, code };
      companies().flush({ ...catalog, items: [selected] }); parent().flush(selected);
      const req = list(); expect(req.request.params.get('company_id')).toBe('7');
      expect(req.request.params.get('page_size')).toBe('1');
      req.flush({ ...page, total: 1, pages: 1, page_size: 1 }); await settle();
      const select = root().querySelector<HTMLSelectElement>('#sites-company')!;
      expect(select.selectedOptions[0].textContent?.trim()).toBe(expected);
      expect(component.company.value).toBe(7);
      expect(root().querySelector('.selected-company')?.textContent).toBe(`Entreprise : ${expected}`);
      expect(root().querySelector('caption')?.textContent?.trim()).toBe('1 site trouvé');
      expect(root().textContent?.replace(/\s+/g, ' ')).toContain('1 site - 1 page');
      expect(root().querySelector('nav.pagination')?.textContent).toContain('1 site par page');
      expect(root().textContent).not.toContain('identifiant');
      expect(TestBed.inject(Router).url).toBe('/sites?company_id=7&page_size=1');
      http.expectNone(() => true);
    }
  );

  it('does not invent missing backend result totals or page counts', async () => {
    await open('/sites?company_id=7'); companies().flush(catalog); parent().flush(company);
    list().flush({ items: [site], page: 1, page_size: 20 }); await settle();
    expect(root().querySelector('caption')?.textContent?.trim()).toBe('Sites industriels');
    expect(root().querySelector('.results > [role="status"]')?.textContent?.trim()).toBe('');
    expect(root().textContent).not.toContain('undefined');
    expect(root().textContent).not.toContain('NaN');
  });

  it('checks a deep-link company outside the catalog and appends its selected option', async () => {
    await open('/sites?company_id=99&page=2&page_size=50&search=Usine'); companies().flush(catalog);
    parent(99).flush({ ...company, id: 99, name: 'Entreprise externe' });
    const req = list(); expect(req.request.params.get('company_id')).toBe('99');
    expect(req.request.params.get('page')).toBe('2'); expect(req.request.params.get('page_size')).toBe('50');
    expect(req.request.params.get('search')).toBe('Usine'); req.flush({ ...page, page: 2 }); await settle();
    const select = root().querySelector<HTMLSelectElement>('#sites-company')!;
    expect(select.selectedOptions[0].textContent).toContain('Entreprise externe');
  });

  it('loads later company pages without duplicates and retains options after an error', async () => {
    await open(); companies().flush({ ...catalog, total: 51, pages: 2 }); await settle();
    button('Charger davantage d’entreprises').click(); await settle();
    let req = companies(); expect(req.request.params.get('page')).toBe('2');
    req.flush('Error', { status: 500, statusText: 'Error' }); await settle();
    expect(component.catalog().items).toHaveLength(1); component.retryCompanies();
    req = companies(); expect(req.request.params.get('page')).toBe('2');
    req.flush({ ...catalog, items: [company, { ...company, id: 8 }], total: 51, page: 2, pages: 2 }); await settle();
    expect(component.catalog().items.map(item => item.id)).toEqual([7, 8]);
    expect(component.company.value).toBeNull(); http.expectNone(req => req.url === '/api/v1/sites');
  });

  it('uses explicit server search, cancels older responses, and preserves applied context', async () => {
    await ready('/sites?company_id=7&page=2&page_size=50&company_page=3#results');
    component.search.setValue('Draft'); http.expectNone(() => true);
    await search(' First '); parent().flush(company); const old = list();
    expect(old.request.params.get('page')).toBe('1'); expect(old.request.params.get('search')).toBe('First');
    await search('Recent_%'); expect(old.cancelled).toBe(true); parent().flush(company); list().flush(page); await settle();
    expect(TestBed.inject(Router).url).toContain('company_page=3');
    expect(TestBed.inject(Router).url).toContain('#results'); expect(root().textContent).toContain('jokers');
    button('Effacer la recherche').click(); await settle(); parent().flush(company);
    const req = list(); expect(req.request.params.has('search')).toBe(false); req.flush(page); await settle();
  });

  it('resets page and search when company changes, and cancels when it is cleared', async () => {
    await ready('/sites?company_id=7&page=2&search=Usine');
    component.company.setValue(8); await settle(); parent(8).flush({ ...company, id: 8 });
    const req = list(); expect(req.request.params.get('page')).toBe('1'); expect(req.request.params.has('search')).toBe(false);
    component.company.setValue(null); await settle(); expect(req.cancelled).toBe(true);
    expect(component.facade.state().status).toBe('idle'); expect(TestBed.inject(Router).url).not.toContain('company_id');
  });

  it('changes server pages and page size while preserving company and applied search', async () => {
    await ready('/sites?company_id=7&search=Usine');
    button('Suivant').click(); await settle(); parent().flush(company);
    let req = list(); expect(req.request.params.get('page')).toBe('2'); expect(req.request.params.get('search')).toBe('Usine');
    req.flush({ ...page, page: 2 }); await settle();
    component.size.setValue(100); await settle(); parent().flush(company);
    req = list(); expect(req.request.params.get('page')).toBe('1'); expect(req.request.params.get('page_size')).toBe('100');
    req.flush({ ...page, page_size: 100 }); await settle();
  });

  it('normalizes invalid URL parameters without sending invalid filters', async () => {
    await open('/sites?company_id=-1&page=0&page_size=101&search=%20%20'); companies().flush(catalog); await settle();
    expect(component.urlNotice()).toContain('normalisés'); expect(component.company.value).toBeNull();
    expect(TestBed.inject(Router).url).toBe('/sites?page=1&page_size=20'); http.expectNone(() => true);
  });

  it.each([false, true])('distinguishes empty sites and empty search (search=%s)', async filtered => {
    await open(`/sites?company_id=7${filtered ? '&search=Absent' : ''}`); companies().flush(catalog); parent().flush(company);
    list().flush({ ...page, items: [], total: 0, pages: 0 }); await settle();
    expect(root().textContent).toContain(filtered ? 'Aucun résultat' : 'Aucun site pour cette entreprise');
    expect(root().textContent).toContain('0 sites');
    expect(root().querySelector('nav.pagination')).toBeNull();
    expect(root().querySelector('.results')?.textContent).not.toContain('page(s)');
    expect(button('Précédent')).toBeUndefined(); expect(button('Suivant')).toBeUndefined();
    if (filtered) {
      const empty = root().querySelector('app-empty-state')!;
      expect(empty.textContent).toContain('Aucun site ne correspond à cette recherche.');
      empty.querySelector<HTMLButtonElement>('button')!.click(); await settle(); parent().flush(company);
      const req = list(); expect(req.request.params.get('company_id')).toBe('7');
      expect(req.request.params.get('page')).toBe('1'); expect(req.request.params.has('search')).toBe(false);
      req.flush(page); await settle();
      expect(root().querySelector('nav.pagination')).not.toBeNull();
      expect(root().textContent?.replace(/\s+/g, ' ')).toContain('21 sites - 2 pages');
    }
  });

  it('offers manual recovery for an unavailable page rather than displaying an empty database', async () => {
    await open('/sites?company_id=7&page=8'); companies().flush(catalog); parent().flush(company);
    list().flush({ ...page, items: [], page: 8 }); await settle();
    expect(root().querySelector('nav.pagination')).not.toBeNull();
    button('Revenir à une page disponible').click(); await settle(); parent().flush(company);
    const req = list(); expect(req.request.params.get('page')).toBe('2'); req.flush({ ...page, page: 2 }); await settle();
  });

  it('reports a missing company without conflating it with an empty site list', async () => {
    await open('/sites?company_id=7'); companies().flush(catalog);
    parent().flush('Not found', { status: 404, statusText: 'Not found' }); await settle();
    expect(root().textContent).toContain('Cette entreprise n’existe pas'); expect(root().querySelector('app-empty-state')).toBeNull();
    http.expectNone(req => req.url === '/api/v1/sites');
  });

  it('keeps catalog errors separate from a successful deep-linked site list', async () => {
    await open('/sites?company_id=7'); companies().flush('Error', { status: 500, statusText: 'Error' });
    parent().flush(company); list().flush(page); await settle();
    expect(root().textContent).toContain('Entreprises indisponibles'); expect(root().querySelector('table')).not.toBeNull();
  });

  it('keeps labelled controls focusable and does not submit an overlong search', async () => {
    await ready();
    const input = root().querySelector<HTMLInputElement>('#sites-search')!; input.focus();
    expect(document.activeElement).toBe(input); expect(root().querySelector('label[for="sites-search"]')).not.toBeNull();
    await search('x'.repeat(101)); expect(input.getAttribute('aria-invalid')).toBe('true');
    expect(root().querySelector('#sites-search-error')?.textContent).toContain('100 caractères'); http.expectNone(() => true);
  });
});
