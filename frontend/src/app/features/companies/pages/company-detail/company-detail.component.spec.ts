import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { CompanyRead } from '../../../../core/models/reference-data.model';
import { COMPANY_ROUTES } from '../../companies.routes';
import { CompaniesListComponent } from '../companies-list/companies-list.component';
import { CompanyDetailComponent } from './company-detail.component';

const company: CompanyRead = { id: 7, name: 'Entreprise test', code: 'TEST-7', description: null,
  created_at: '2026-10-01T12:00:00', updated_at: '2026-10-02T13:00:00' };

describe('Company detail page', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: CompanyDetailComponent;
  const root = () => harness.routeNativeElement!;
  const read = (id = 7) => http.expectOne(`/api/v1/companies/${id}`);

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

  async function open(url = '/companies/7') {
    harness = await RouterTestingHarness.create();
    component = await harness.navigateByUrl(url, CompanyDetailComponent);
    harness.fixture.detectChanges();
  }

  it('loads one GET and renders all real fields, nullable description and unconverted timestamps', async () => {
    await open();
    expect(root().querySelector('[aria-busy]')?.getAttribute('aria-busy')).toBe('true');
    expect(root().querySelector('[role="status"]')?.textContent).toContain('Chargement de l’entreprise');
    const request = read();
    expect(request.request.method).toBe('GET');
    expect(request.request.params.keys()).toEqual([]);
    request.flush(company);
    await settle();
    expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(root().querySelectorAll('dt')).toHaveLength(6);
    expect([...root().querySelectorAll('dd')].map(el => el.textContent)).toEqual([
      company.name, company.code, '7', 'Non renseigné', company.created_at, company.updated_at
    ]);
    expect(root().textContent).toContain('Sans fuseau explicite');
    expect(root().querySelector('[aria-busy]')?.getAttribute('aria-busy')).toBe('false');
    expect(root().querySelector('button')).toBeNull();
    http.expectNone(() => true);
  });

  it('keeps full text, line breaks and explicit timezone strings without interpreting HTML', async () => {
    await open();
    const description = '<script>alert(1)</script>\n' + 'Long texte '.repeat(100);
    read().flush({ ...company, description, updated_at: '2026-10-02T13:00:00+02:00' });
    await settle();
    expect(root().querySelector('.description dd')?.textContent).toBe(description);
    expect(root().querySelector('script')).toBeNull();
    expect(root().textContent).toContain('2026-10-02T13:00:00+02:00');
  });

  it('shows explicit missing values without assuming UTC for absent timestamps', async () => {
    await open();
    // Defensive rendering of an incomplete response, not a change to CompanyRead.
    read().flush({ ...company, description: '   ', created_at: null, updated_at: '' });
    await settle();
    expect([...root().querySelectorAll('dd')].filter(el => el.textContent === 'Non renseigné')).toHaveLength(3);
    expect(root().textContent).not.toContain('Invalid Date');
  });

  it.each(['0', '-1', 'abc', '1.5', '9007199254740992'])('blocks invalid identifier %s without an HTTP request', async id => {
    await open(`/companies/${id}`);
    expect(root().querySelector('[role="alert"]')?.textContent).toContain('Identifiant invalide');
    expect(root().querySelector('button')).toBeNull();
    component.retry();
    http.expectNone(() => true);
  });

  it.each([400, 404, 422, 403])('distinguishes non-retryable HTTP %s from network/server errors', async status => {
    await open();
    read().flush({ detail: 'Backend detail must not be shown' }, { status, statusText: 'Error' });
    await settle();
    expect(root().querySelector('[role="alert"]')).not.toBeNull();
    expect(root().textContent).toContain(status === 404 ? 'Entreprise introuvable' : 'Chargement impossible');
    expect(root().textContent).not.toContain('Backend detail must not be shown');
    expect(root().querySelector('button')).toBeNull();
    component.retry();
    http.expectNone(() => true);
  });

  it.each([0, 500, 503])('allows one explicit retry for error %s and keeps focus on completion', async status => {
    await open('/companies/7?page=2&search=Test');
    const request = read();
    if (status === 0) request.error(new ProgressEvent('error'));
    else request.flush(null, { status, statusText: 'Server Error' });
    await settle();
    const retry = root().querySelector<HTMLButtonElement>('button')!;
    expect(retry.textContent?.trim()).toBe('Réessayer');
    retry.click();
    await settle();
    expect(root().querySelector('[aria-busy]')?.getAttribute('aria-busy')).toBe('true');
    const back = root().querySelector<HTMLAnchorElement>('a')!;
    back.focus();
    read().flush(company);
    await settle();
    expect(document.activeElement).toBe(back);
    http.expectNone(() => true);
  });

  it('cancels an obsolete identifier request and reuses the same page for later identifiers', async () => {
    await open();
    const old = read();
    expect(await harness.navigateByUrl('/companies/8', CompanyDetailComponent)).toBe(component);
    await settle();
    expect(old.cancelled).toBe(true);
    read(8).flush({ ...company, id: 8, name: 'Second entreprise' });
    await settle();
    expect(root().textContent).toContain('Second entreprise');
    await harness.navigateByUrl('/companies/9', CompanyDetailComponent);
    await settle();
    read(9).flush({ ...company, id: 9 });
    await settle();
    expect(root().querySelectorAll('dd')[2].textContent).toBe('9');
  });

  it('cancels even when an identifier becomes invalid and cancels on page destruction', async () => {
    await open();
    const old = read();
    await harness.navigateByUrl('/companies/invalid', CompanyDetailComponent);
    await settle();
    expect(old.cancelled).toBe(true);
    http.expectNone(() => true);
    await harness.navigateByUrl('/companies/8', CompanyDetailComponent);
    await settle();
    const pending = read(8);
    TestBed.resetTestingModule();
    expect(pending.cancelled).toBe(true);
  });

  it('returns through an internal RouterLink with applied search/page context and no extra detail GET', async () => {
    await open('/companies/7?page=3&page_size=50&search=%C3%89nergie%20%26%20ports&redirect=https://example.com');
    read().flush(company);
    await settle();
    const link = root().querySelector<HTMLAnchorElement>('a')!;
    expect(link.getAttribute('href')).toBe('/companies?page=3&page_size=50&search=%C3%89nergie%20%26%20ports');
    expect(link.tabIndex).toBe(0);
    expect(link.classList.contains('company-back')).toBe(true);
    expect(link.querySelector('span')?.textContent).toBe('Retour à la liste des entreprises');
    expect(link.querySelector('svg')?.getAttribute('aria-hidden')).toBe('true');
    expect(link.querySelector('svg')?.getAttribute('focusable')).toBe('false');
    expect(link.getAttribute('role')).toBeNull();
    link.focus();
    expect(document.activeElement).toBe(link);
    await harness.navigateByUrl('/companies/7?page=3&page_size=50&search=Test', CompanyDetailComponent);
    await settle();
    http.expectNone(() => true);
    root().querySelector<HTMLAnchorElement>('a')!.click();
    await settle();
    expect(harness.routeDebugElement!.componentInstance).toBeInstanceOf(CompaniesListComponent);
    const request = http.expectOne(req => req.url === '/api/v1/companies');
    expect(request.request.params.get('page')).toBe('3');
    expect(request.request.params.get('page_size')).toBe('50');
    expect(request.request.params.get('search')).toBe('Test');
    request.flush({ items: [company], total: 101, page: 3, page_size: 50, pages: 3 });
    await settle();
    expect(TestBed.inject(Router).url).toBe('/companies?page=3&page_size=50&search=Test');
  });

  it('bounds invalid return parameters without sending them to the detail endpoint', async () => {
    await open('/companies/7?page=0&page_size=101&search=' + 'x'.repeat(101));
    read().flush(company);
    await settle();
    expect(root().querySelector('a')?.getAttribute('href')).toBe('/companies?page=1&page_size=20');
  });
});
