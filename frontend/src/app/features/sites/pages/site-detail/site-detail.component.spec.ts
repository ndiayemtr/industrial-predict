import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { SiteRead } from '../../../../core/models/reference-data.model';
import { SITE_ROUTES } from '../../sites.routes';
import { SiteDetailComponent } from './site-detail.component';
import { SitesListComponent } from '../sites-list/sites-list.component';

const site: SiteRead = { id: 3, company_id: 7, name: 'Usine 日本', code: 'SITE-3', description: 'Ligne 1\nLigne 2',
  created_at: '2026-08-31T14:58:20.179290', updated_at: '2026-10-16T13:51:15.910577+02:00' };
const company = { id: 7, name: 'Entreprise test', code: 'C7', description: null, created_at: '', updated_at: '' };
describe('Site read-only detail', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: SiteDetailComponent;
  const root = () => harness.routeNativeElement!;
  const read = (id = 3) => http.expectOne(`/api/v1/sites/${id}`);
  const parent = (id = 7) => http.expectOne(`/api/v1/companies/${id}`);
  const values = () => [...root().querySelectorAll('dl > div')].map(el => [el.querySelector('dt')!.textContent!, el.querySelector('dd')!.textContent!.trim()]);
  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'sites', children: SITE_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.expectNone(req => req.method !== 'GET'); http.verify(); });
  async function settle() {
    harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges();
  }
  async function open(url = '/sites/3') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, SiteDetailComponent); await settle();
  }
  async function loaded(url = '/sites/3') { await open(url); read().flush(site); parent().flush(company); await settle(); }

  it('loads site then its actual company, revealing the site while the reference is pending', async () => {
    await open('/sites/3?company_id=99&page=2&page_size=50&search=Usine');
    expect(root().querySelector('.site-detail')?.getAttribute('aria-busy')).toBe('true');
    expect(root().textContent).toContain('Chargement du site'); http.expectNone(req => req.url.includes('/companies/'));
    read().flush(site); await settle();
    expect(root().textContent).toContain(site.name); expect(root().textContent).toContain('Chargement de la référence entreprise');
    expect(root().textContent).not.toContain(company.name); parent().flush(company); await settle();
    expect(values()).toContainEqual(['Création', '31/08/2026 à 14:58']);
    expect(values()).toContainEqual(['Dernière modification', '16/10/2026 à 11:51 UTC']);
    expect(root().querySelector('.company-reference')?.textContent).toBe('Entreprise test - C7');
    expect(values().map(([label]) => label)).toEqual([
      'Nom', 'Code', 'Entreprise de rattachement', 'Description', 'Création', 'Dernière modification'
    ]);
    expect(values().map(([, value]) => value)).not.toContain('3');
    expect(root().textContent).not.toContain('Identifiant');
    expect(root().textContent).toContain('une autre entreprise que celle du contexte de retour');
    expect(root().querySelectorAll('h1')).toHaveLength(1); expect(root().querySelectorAll('form,input')).toHaveLength(0);
    expect(root().querySelector('.site-edit')?.getAttribute('href')).toBe('/sites/3/edit?company_id=99&page=2&page_size=50&search=Usine');
    expect(root().querySelector('.site-equipments')?.getAttribute('href')).toBe('/equipments?company_id=7&site_id=3&page=1&page_size=20');
    expect(root().textContent).not.toContain('Supprimer');
    const current = component.state(); if (current.status !== 'success') throw Error('Missing site');
    expect(current.data).toEqual(site);
  });

  it.each([
    ['PETROSEN', 'PETROSEN', 'PETROSEN'],
    ['PETROSEN', 'PTR-001', 'PETROSEN - PTR-001']
  ])('shows company name %s and code %s without redundant business labels', async (name, code, expected) => {
    await open('/sites/3?company_id=7&page=2&page_size=50&search=Usine');
    read().flush(site);
    const reference = parent(); expect(reference.request.method).toBe('GET');
    const source = { ...company, name, code };
    reference.flush(source); await settle();
    expect(root().querySelector('.company-reference')?.textContent).toBe(expected);
    expect(component.state()).toMatchObject({ status: 'success', data: { id: 3, company_id: 7 },
      company: { status: 'success', data: source } });
    expect(root().querySelector('.site-back')?.getAttribute('href')).toBe('/sites?company_id=7&page=2&page_size=50&search=Usine');
    http.expectNone(() => true);
  });

  it.each([
    ['2026-10-16T11:51:15.910577Z', '16/10/2026 à 11:51 UTC'],
    ['2026-10-16T13:51:15.910577+02:00', '16/10/2026 à 11:51 UTC'],
    ['2026-10-16T00:15:20.123-03:30', '16/10/2026 à 03:45 UTC'],
    ['2026-10-25T02:30:59.999999', '25/10/2026 à 02:30'],
    ['2026-02-30T12:00:00', 'Non disponible']
  ])('formats timestamp %s only for display', async (timestamp, expected) => {
    await open(); read().flush({ ...site, created_at: timestamp }); parent().flush(company); await settle();
    expect(values()).toContainEqual(['Création', expected]);
    const current = component.state(); if (current.status !== 'success') throw Error('Missing site');
    expect(current.data.created_at).toBe(timestamp);
  });

  it('handles absent description and omitted dates without inventing values', async () => {
    await open(); read().flush({ ...site, description: null, created_at: undefined, updated_at: null }); parent().flush(company); await settle();
    expect(values()).toContainEqual(['Description', 'Non renseignée']);
    expect(values().map(([label]) => label)).not.toContain('Création');
    expect(values().map(([label]) => label)).not.toContain('Dernière modification');
  });

  it.each([0, 404, 422, 500])('handles site failure %s and permits only manual network/server retries', async status => {
    await open(); const req = read();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush('Error', { status, statusText: 'Error' });
    await settle(); expect(component.state()).toMatchObject({ status: 'error', retryable: status === 0 || status >= 500 });
    expect(root().querySelector('app-error-state')).not.toBeNull(); expect(root().querySelector('dl')).toBeNull();
    if (status === 404) expect(root().textContent).toContain('Site introuvable (404)');
    component.retry();
    if (status === 0 || status >= 500) { read().flush(site); parent().flush(company); await settle(); expect(root().querySelector('dl')).not.toBeNull(); }
    else http.expectNone(() => true);
  });

  it.each([0, 404, 500])('keeps site data on company failure %s and retries only the reference', async status => {
    await open(); read().flush(site); const req = parent();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush('Error', { status, statusText: 'Error' });
    await settle(); expect(root().textContent).toContain(site.name); expect(root().textContent).not.toContain('Identifiant');
    expect(component.state()).toMatchObject({ status: 'success', data: { id: 3, company_id: 7 } });
    expect(root().querySelector('.company-reference')).toBeNull(); expect(root().querySelector('app-error-state')).not.toBeNull();
    component.retryCompany();
    if (status === 0 || status >= 500) { parent().flush(company); await settle(); expect(root().textContent).toContain(company.name); }
    http.expectNone(req => req.url === '/api/v1/sites/3');
  });

  it.each(['0', '-1', 'abc', '9007199254740992'])('rejects invalid identifier %s without HTTP', async raw => {
    await open(`/sites/${raw}`); expect(root().textContent).toContain('Identifiant invalide'); http.expectNone(() => true);
  });

  it('cancels obsolete site and company requests on identifier changes and invalid navigation', async () => {
    await open(); const oldSite = read();
    const reused = await harness.navigateByUrl('/sites/4', SiteDetailComponent); await settle();
    expect(reused).toBe(component); expect(oldSite.cancelled).toBe(true);
    read(4).flush({ ...site, id: 4 }); const oldCompany = parent();
    await harness.navigateByUrl('/sites/5'); await settle(); expect(oldCompany.cancelled).toBe(true);
    read(5).flush({ ...site, id: 5, name: 'Site récent', company_id: 9 }); parent(9).flush({ ...company, id: 9, name: 'Entreprise récente' }); await settle();
    expect(root().textContent).toContain('Site récent'); expect(root().textContent).toContain('Entreprise récente');
    await harness.navigateByUrl('/sites/6'); await settle(); const pending = read(6);
    await harness.navigateByUrl('/sites/invalid'); await settle(); expect(pending.cancelled).toBe(true);
  });

  it('cancels the outstanding company lookup on destruction', async () => {
    await open(); read().flush(site); const pending = parent(); harness.fixture.destroy(); expect(pending.cancelled).toBe(true);
  });

  it('bounds return parameters and defaults a direct entry to the actual company', async () => {
    await loaded('/sites/3?company_id=-1&page=0&page_size=101&search=%20%20&returnUrl=https://invalid.example');
    const back = root().querySelector<HTMLAnchorElement>('.site-back')!;
    expect(back.getAttribute('href')).toBe('/sites?company_id=7&page=1&page_size=20');
    back.focus(); expect(document.activeElement).toBe(back); expect(back.tagName).toBe('A');
    expect(back.getAttribute('role')).toBeNull(); expect(back.textContent).toContain('Retour à la liste des sites');
  });

  it('navigates from the list and back with the applied company, search, page and size', async () => {
    harness = await RouterTestingHarness.create();
    await harness.navigateByUrl('/sites?company_id=7&page=2&page_size=50&search=Usine', SitesListComponent);
    http.expectOne(req => req.url === '/api/v1/companies').flush({ items: [company], total: 1, page: 1, page_size: 50, pages: 1 });
    parent().flush(company); http.expectOne(req => req.url === '/api/v1/sites').flush({ items: [site], total: 51, page: 2, page_size: 50, pages: 2 }); await settle();
    root().querySelector<HTMLAnchorElement>('tbody a')!.click(); await settle();
    read().flush(site); parent().flush(company); await settle();
    expect(TestBed.inject(Router).url).toBe('/sites/3?company_id=7&page=2&page_size=50&search=Usine');
    root().querySelector<HTMLAnchorElement>('.site-back')!.click(); await settle();
    http.expectOne(req => req.url === '/api/v1/companies').flush({ items: [company], total: 1, page: 1, page_size: 50, pages: 1 });
    parent().flush(company); const req = http.expectOne(req => req.url === '/api/v1/sites');
    expect(req.request.params.get('company_id')).toBe('7'); expect(req.request.params.get('page')).toBe('2');
    expect(req.request.params.get('page_size')).toBe('50'); expect(req.request.params.get('search')).toBe('Usine');
    req.flush({ items: [site], total: 51, page: 2, page_size: 50, pages: 2 }); await settle();
  });
});
