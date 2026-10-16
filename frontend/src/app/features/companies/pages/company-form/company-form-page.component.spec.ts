import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { COMPANY_ROUTES } from '../../companies.routes';
import { CompanyFormPageComponent } from './company-form-page.component';

describe('Company creation page', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: CompanyFormPageComponent;
  const root = () => harness.routeNativeElement!;
  const pending = () => http.expectOne(request => request.url === '/api/v1/companies');

  beforeEach(() => {
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'companies', children: COMPANY_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.verify(); } finally { vi.restoreAllMocks(); } });

  async function settle() {
    harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges();
  }
  async function open(url = '/companies/new') {
    harness = await RouterTestingHarness.create();
    component = await harness.navigateByUrl(url, CompanyFormPageComponent);
    await settle();
  }
  function fill() {
    const editor = component.editor()!;
    editor.form.patchValue({ name: ' New Company ', code: 'New-é' });
    editor.form.markAsDirty();
  }
  async function submit() {
    root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await settle();
  }

  it('matches /new before the detail route, has one h1, and issues no initial HTTP request', async () => {
    await open();
    expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(root().querySelector('h1')?.textContent).toBe('Nouvelle entreprise');
    http.expectNone(() => true);
    await submit();
    http.expectNone(() => true);
  });

  it('POSTs once despite duplicate submits, locks navigation while saving, then opens the returned id', async () => {
    await open('/companies/new?page=3&page_size=50&search=Applied');
    fill();
    await submit();
    const request = pending();
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ name: 'New Company', code: 'New-é' });
    await submit();
    component.save({ name: 'Duplicate', code: 'DUP' });
    http.expectNone(() => true);
    expect(root().querySelector('[role="status"]')?.textContent).toContain('Enregistrement');
    expect(component.canLeave()).toBe(false);
    expect(await TestBed.inject(Router).navigateByUrl('/companies')).toBe(false);
    const confirm = vi.spyOn(window, 'confirm');
    request.flush({ id: 87, name: 'New Company', code: 'New-é', description: null,
      created_at: '2026-10-15T12:00:00', updated_at: '2026-10-15T12:00:00' }, { status: 201, statusText: 'Created' });
    await settle();
    expect(TestBed.inject(Router).url).toBe('/companies/87?page=3&page_size=50&search=Applied');
    http.expectOne('/api/v1/companies/87').flush({ id: 87, name: 'New Company', code: 'New-é', description: null,
      created_at: '2026-10-15T12:00:00', updated_at: '2026-10-15T12:00:00' });
    await settle();
    expect(root().querySelector('[role="status"]')?.textContent).toBe('Entreprise créée.');
    expect(confirm).not.toHaveBeenCalled();
  });

  it('maps an actual 409 to Code and keeps values for explicit correction', async () => {
    await open(); fill(); await submit();
    pending().flush({ detail: 'Company with code already exists' }, { status: 409, statusText: 'Conflict' });
    await settle();
    expect(root().querySelector('#code-error')?.textContent).toContain('déjà utilisé');
    expect(component.editor()!.form.controls.name.value).toBe(' New Company ');
    expect(root().querySelector('app-error-state button')).toBeNull();
    component.editor()!.form.controls.code.setValue('Different');
    await settle();
    expect(root().querySelector('#code-error')?.textContent).toBe('');
    await submit(); pending().flush(null, { status: 409, statusText: 'Conflict' });
  });

  it('associates 422 body errors with known fields and summarizes unknown constraints without raw HTML', async () => {
    await open(); fill(); await submit();
    pending().flush({ detail: [
      { loc: ['body', 'name'], msg: '<b>Raw error</b>' },
      { loc: ['body', 'description'], msg: 'Invalid' },
      { loc: ['query', 'code'], msg: 'Other location' }, { loc: ['body', 'unknown'], msg: 'Unknown' }
    ] }, { status: 422, statusText: 'Validation Error' });
    await settle();
    expect(root().querySelector('#name-error')?.textContent).toContain('pas acceptée');
    expect(root().querySelector('#description-error')?.textContent).toContain('pas acceptée');
    expect(root().querySelector('#code-error')?.textContent).toBe('');
    expect(root().querySelector('[role="alert"]')?.textContent).toContain('autre contrainte');
    expect(root().querySelector('b')).toBeNull();
    expect(component.uncertain()).toBe(false);
  });

  it.each([0, 500, 503])('treats status %s as uncertain, never as a code conflict or automatic retry', async status => {
    await open(); fill(); await submit();
    const request = pending();
    if (status === 0) request.error(new ProgressEvent('error'));
    else request.flush('Database error', { status, statusText: 'Server Error' });
    await settle();
    expect(root().querySelector('[role="alert"]')?.textContent).toContain('peut avoir été créée');
    expect(root().querySelector('#code-error')?.textContent).toBe('');
    expect(root().querySelector<HTMLButtonElement>('button[type="submit"]')!.disabled).toBe(true);
    expect(root().querySelector('a[target="_blank"]')?.getAttribute('href')).toBe('/companies?page=1&page_size=20');
    await submit(); component.save({ name: 'Retry', code: 'Retry' });
    http.expectNone(() => true);
    root().querySelector<HTMLButtonElement>('section > button')!.click();
    await settle(); await submit();
    pending().flush(null, { status: 409, statusText: 'Conflict' });
  });

  it.each([400, 403, 404, 422])('keeps unexpected/malformed HTTP %s visible without inventing a duplicate code', async status => {
    await open(); fill(); await submit();
    pending().flush({ detail: 'Refused' }, { status, statusText: 'Error' });
    await settle();
    expect(component.state()).toBe('error');
    expect(root().querySelector('[role="alert"]')).not.toBeNull();
    expect(root().querySelector('#code-error')?.textContent).toBe('');
    expect(component.editor()!.form.controls.code.value).toBe('New-é');
    http.expectNone(() => true);
  });

  it('cancels a pristine form with safe list context and no confirm', async () => {
    await open('/companies/new?page=2&page_size=50&search=Applied&redirect=https://example.com');
    const confirm = vi.spyOn(window, 'confirm');
    component.cancel(); await settle();
    expect(TestBed.inject(Router).url).toBe('/companies?page=2&page_size=50&search=Applied');
    const req = pending(); expect(req.request.method).toBe('GET');
    req.flush({ items: [], total: 0, page: 2, page_size: 50, pages: 0 });
    expect(confirm).not.toHaveBeenCalled();
  });

  it('asks before discarding edits on Cancel or other route navigation and preserves data on refusal', async () => {
    await open(); fill();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    component.cancel(); await settle();
    expect(TestBed.inject(Router).url).toBe('/companies/new');
    expect(component.editor()!.form.controls.code.value).toBe('New-é');
    http.expectNone(() => true);
    confirm.mockReturnValue(true);
    await TestBed.inject(Router).navigateByUrl('/companies/7'); await settle();
    http.expectOne('/api/v1/companies/7').flush({ id: 7, name: 'Test', code: 'TEST', description: null,
      created_at: '2026-10-15T12:00:00', updated_at: '2026-10-15T12:00:00' });
    expect(confirm).toHaveBeenCalledTimes(2);
  });

  it('protects reload/close with Angular-owned beforeunload handling and normalizes invalid context', async () => {
    await open('/companies/new?page=0&page_size=101&search=%20%20');
    expect(component.listQuery).toEqual({ page: 1, page_size: 20 });
    const clean = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(clean); expect(clean.defaultPrevented).toBe(false);
    fill();
    const dirty = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(dirty); expect(dirty.defaultPrevented).toBe(true);
    harness.fixture.destroy();
    const after = new Event('beforeunload', { cancelable: true });
    window.dispatchEvent(after); expect(after.defaultPrevented).toBe(false);
  });
});
