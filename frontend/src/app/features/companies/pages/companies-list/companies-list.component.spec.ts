import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { Page } from '../../../../core/models/page.model';
import { CompanyRead } from '../../../../core/models/reference-data.model';
import { COMPANY_ROUTES } from '../../companies.routes';
import { CompaniesListComponent } from './companies-list.component';

// Test data is never imported by the application.
const company: CompanyRead = { id: 7, name: 'Entreprise test', code: 'TEST-7', description: null,
  created_at: '2026-10-01T12:00:00', updated_at: '2026-10-01T12:00:00' };
const page: Page<CompanyRead> = { items: [company], total: 21, page: 1, page_size: 20, pages: 2 };

describe('Companies list page and URL integration', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: CompaniesListComponent;
  const root = () => harness.routeNativeElement!;
  const searchInput = () => root().querySelector<HTMLInputElement>('#company-search')!;
  const button = (label: string) => [...root().querySelectorAll<HTMLButtonElement>('button')]
    .find(item => item.textContent?.trim() === label)!;
  const pending = () => http.expectOne(request => request.url === '/api/v1/companies');

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'companies', children: COMPANY_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  async function settle() {
    harness.fixture.detectChanges();
    TestBed.tick();
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
  }

  async function open(url = '/companies') {
    harness = await RouterTestingHarness.create();
    component = await harness.navigateByUrl(url, CompaniesListComponent);
    harness.fixture.detectChanges();
  }

  async function submit(search: string) {
    searchInput().value = search;
    searchInput().dispatchEvent(new Event('input', { bubbles: true }));
    root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await settle();
  }

  it('loads exactly one server page and renders accessible, keyboard-focusable company names', async () => {
    await open();
    const req = pending();
    expect(req.request.params.get('page')).toBe('1');
    expect(req.request.params.get('page_size')).toBe('20');
    expect(root().querySelector('[aria-busy]')?.getAttribute('aria-busy')).toBe('true');
    expect(root().querySelector('[role="status"]')?.textContent).toContain('Chargement des entreprises');
    req.flush(page);
    await settle();
    expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(root().querySelector('table caption')?.textContent).toContain('21 au total');
    expect(root().querySelectorAll('thead th[scope="col"]')).toHaveLength(3);
    const name = root().querySelector<HTMLElement>('tbody th[scope="row"]')!;
    expect(name.tabIndex).toBe(0);
    name.focus();
    expect(document.activeElement).toBe(name);
    expect(name.getAttribute('aria-describedby')).toBe('company-detail-unavailable');
    expect(root().textContent).toContain('Entreprise test');
    expect(root().textContent).toContain('TEST-7');
    expect(root().textContent).toContain('Non renseignée');
    expect(root().querySelectorAll('a')).toHaveLength(0);
    expect(root().querySelectorAll('button[type="submit"]')).toHaveLength(1);
    expect(root().querySelector('[aria-busy]')?.getAttribute('aria-busy')).toBe('false');
    http.expectNone(() => true);
  });

  it('submits server search explicitly, resets page 1 and cancels successive obsolete searches', async () => {
    await open('/companies?page=2&page_size=50#anchor');
    pending().flush({ ...page, page: 2, page_size: 50 });
    await settle();
    searchInput().value = 'First';
    searchInput().dispatchEvent(new Event('input', { bubbles: true }));
    http.expectNone(() => true);
    await submit('First');
    const old = pending();
    expect(old.request.params.get('page')).toBe('1');
    expect(old.request.params.get('page_size')).toBe('50');
    await submit('Énergie & ports');
    expect(old.cancelled).toBe(true);
    const latest = pending();
    expect(latest.request.params.get('search')).toBe('Énergie & ports');
    latest.flush(page);
    await settle();
    expect(TestBed.inject(Router).url).toContain('page=1');
    expect(TestBed.inject(Router).url).toContain('#anchor');
    expect(component.facade.query()?.search).toBe('Énergie & ports');
  });

  it('keeps query-only navigation on the same component and paginates through the API', async () => {
    await open('/companies?search=Test');
    pending().flush(page);
    await settle();
    button('Suivant').click();
    await settle();
    const next = pending();
    expect(next.request.params.get('page')).toBe('2');
    expect(next.request.params.get('search')).toBe('Test');
    next.flush({ ...page, page: 2 });
    await settle();
    expect(harness.routeDebugElement!.componentInstance).toBe(component);
    expect(button('Suivant').disabled).toBe(true);
    button('Précédent').click();
    await settle();
    const previous = pending();
    expect(previous.request.params.get('page')).toBe('1');
    previous.flush(page);
    await settle();
  });

  it.each(['', 'Absent'])('distinguishes empty database and empty search %s', async search => {
    await open(search ? '/companies?search=Absent' : '/companies');
    pending().flush({ ...page, items: [], total: 0, pages: 0 });
    await settle();
    expect(root().querySelector('app-empty-state h2')?.textContent).toBe(search ? 'Aucun résultat' : 'Aucune entreprise');
    expect(root().querySelector('table')).toBeNull();
    expect(button('Suivant').disabled).toBe(true);
  });

  it('clears search without an empty search parameter', async () => {
    await open('/companies?search=Absent&page=2');
    pending().flush({ ...page, items: [], total: 0, pages: 0 });
    await settle();
    button('Effacer la recherche').click();
    await settle();
    const req = pending();
    expect(req.request.params.has('search')).toBe(false);
    expect(req.request.params.get('page')).toBe('1');
    req.flush(page);
    await settle();
    expect(searchInput().value).toBe('');
  });

  it('shows errors and retries applied parameters rather than an edited search', async () => {
    await open('/companies?search=Applied');
    pending().flush('Internal Server Error', { status: 500, statusText: 'Server Error' });
    await settle();
    expect(root().querySelector('[role="alert"]')).not.toBeNull();
    expect(root().querySelector('app-empty-state')).toBeNull();
    searchInput().value = 'Edited';
    searchInput().dispatchEvent(new Event('input', { bubbles: true }));
    button('Réessayer').click();
    await settle();
    const req = pending();
    expect(req.request.params.get('search')).toBe('Applied');
    req.flush(page);
    await settle();
    expect(searchInput().value).toBe('Edited');
  });

  it('normalizes invalid URL parameters once before issuing a valid GET', async () => {
    await open('/companies?page=0&page_size=101&search=%20%20');
    await settle();
    const req = pending();
    expect(req.request.params.get('page')).toBe('1');
    expect(req.request.params.get('page_size')).toBe('20');
    expect(req.request.params.has('search')).toBe(false);
    req.flush(page);
    await settle();
    expect(root().textContent).toContain('normalisés');
    expect(TestBed.inject(Router).url).not.toContain('search=');
  });

  it('proposes a bounded manual recovery for an empty page with a nonzero total', async () => {
    await open('/companies?page=9');
    pending().flush({ ...page, page: 9, items: [] });
    await settle();
    expect(root().querySelector('app-empty-state')).toBeNull();
    http.expectNone(() => true);
    button('Revenir à une page disponible').click();
    await settle();
    const req = pending();
    expect(req.request.params.get('page')).toBe('2');
    req.flush({ ...page, page: 2 });
    await settle();
  });

  it('blocks overlong search, preserves focus on search completion and does not reload on unrelated parameters', async () => {
    await open();
    pending().flush(page);
    await settle();
    component.search.setValue('x'.repeat(101));
    component.applySearch();
    await settle();
    expect(searchInput().getAttribute('aria-invalid')).toBe('true');
    http.expectNone(() => true);
    button('Rechercher').focus();
    await submit('Test');
    pending().flush(page);
    await settle();
    expect(document.activeElement).toBe(button('Rechercher'));
    await harness.navigateByUrl('/companies?page=1&page_size=20&search=Test&source=test', CompaniesListComponent);
    await settle();
    http.expectNone(() => true);
  });
});
