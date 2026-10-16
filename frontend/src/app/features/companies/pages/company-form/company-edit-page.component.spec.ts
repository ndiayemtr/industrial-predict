import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { NbToastrService } from '@nebular/theme';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { CompanyRead } from '../../../../core/models/reference-data.model';
import { COMPANY_ROUTES } from '../../companies.routes';
import { CompanyFormPageComponent } from './company-form-page.component';

const company: CompanyRead = { id: 7, name: ' Original ', code: 'TEST-7', description: 'Texte\noriginal',
  created_at: '2026-10-01T12:00:00', updated_at: '2026-10-02T13:00:00' };

describe('Company editing using the existing form page', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let page: CompanyFormPageComponent;
  const root = () => harness.routeNativeElement!;
  const request = (id = 7) => http.expectOne(`/api/v1/companies/${id}`);
  const toastr = { success: vi.fn() };
  beforeEach(() => {
    toastr.success.mockClear();
    TestBed.configureTestingModule({ providers: [{ provide: NbToastrService, useValue: toastr }, provideHttpClient(), provideHttpClientTesting(),
      provideRouter([{ path: 'companies', children: COMPANY_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.verify(); } finally { vi.restoreAllMocks(); } });

  async function settle() {
    harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges();
  }
  async function open(url = '/companies/7/edit?page=3&page_size=50&search=Applied') {
    harness = await RouterTestingHarness.create();
    page = await harness.navigateByUrl(url, CompanyFormPageComponent);
    await settle();
  }
  async function loaded(value = company) { await open(); request().flush(value); await settle(); }
  async function submit() {
    root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await settle();
    expect(toastr.success).not.toHaveBeenCalled();
  }
  async function failSave(status: number, body: object | null = null) {
    page.editor()!.form.controls.code.setValue('Changed'); await submit();
    const req = request(); expect(req.request.method).toBe('PATCH');
    if (status === 0) req.error(new ProgressEvent('error'));
    else req.flush(body, { status, statusText: 'Error' });
    await settle();
    expect(toastr.success).not.toHaveBeenCalled();
  }

  it('loads one GET before revealing the prefilled reusable form and preserves a single h1', async () => {
    await open();
    expect(page.state()).toBe('loading');
    expect(root().querySelector('form')).toBeNull();
    expect(root().querySelector('[aria-busy]')?.getAttribute('aria-busy')).toBe('true');
    const get = request(); expect(get.request.method).toBe('GET'); get.flush(company); await settle();
    expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(root().querySelector('h1')?.textContent).toBe('Modifier l’entreprise');
    expect(page.editor()!.form.getRawValue()).toEqual({ name: ' Original ', code: 'TEST-7', description: 'Texte\noriginal' });
    expect(page.editor()!.hasChanges()).toBe(false);
    expect(page.state()).toBe('idle');
    http.expectNone(() => true);
  });

  it.each(['0', '-1', 'abc', '1.5', '9007199254740992'])('blocks invalid identifier %s without HTTP', async id => {
    await open(`/companies/${id}/edit`);
    expect(page.state()).toBe('load-error');
    expect(root().textContent).toContain('Identifiant invalide');
    page.retryLoad(); page.save({ name: 'Test', code: 'TEST' });
    http.expectNone(() => true);
  });

  it.each([404, 422, 403])('distinguishes non-retryable GET %s and never exposes a blank edit form', async status => {
    await open(); request().flush(null, { status, statusText: 'Error' }); await settle();
    expect(root().textContent).toContain(status === 404 ? 'Entreprise introuvable' : 'Chargement impossible');
    expect(root().querySelector('form')).toBeNull();
    expect(root().querySelector('button')).toBeNull();
    expect(root().querySelector('a')?.getAttribute('href')).toBe('/companies?page=3&page_size=50&search=Applied');
    page.retryLoad(); http.expectNone(() => true);
  });

  it.each([0, 500])('retries only the GET after load failure %s', async status => {
    await open(); const req = request();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush(null, { status, statusText: 'Error' });
    await settle(); root().querySelector<HTMLButtonElement>('button')!.click(); await settle();
    const retry = request(); expect(retry.request.method).toBe('GET'); retry.flush(company); await settle();
    expect(page.state()).toBe('idle');
  });

  it('sends no PATCH for unchanged or reverted fields, including a nullable description', async () => {
    await loaded({ ...company, description: null });
    await submit();
    expect(root().textContent).toContain('Aucune modification à enregistrer');
    page.editor()!.form.controls.name.setValue('Temporary');
    page.editor()!.form.controls.name.setValue(company.name);
    page.editor()!.form.controls.description.setValue('');
    page.editor()!.form.controls.description.markAsDirty();
    await submit(); http.expectNone(() => true);
    expect(toastr.success).not.toHaveBeenCalled();
  });

  it('patches only the changed code, preserving untouched whitespace and nulls, and blocks double submits', async () => {
    await loaded({ ...company, description: null });
    page.editor()!.form.controls.code.setValue(' Mixed-é '); await submit();
    const patch = request();
    expect(patch.request.method).toBe('PATCH');
    expect(patch.request.body).toEqual({ code: 'Mixed-é' });
    await submit(); page.save({ name: 'Other', code: 'Other' });
    expect(page.canLeave()).toBe(false);
    expect(await TestBed.inject(Router).navigateByUrl('/companies/8/edit')).toBe(false);
    http.expectNone(() => true);
    expect(toastr.success).not.toHaveBeenCalled();
    patch.flush({ ...company, code: 'Mixed-é' }); await settle();
    expect(TestBed.inject(Router).url).toBe('/companies/7?page=3&page_size=50&search=Applied');
    request().flush({ ...company, code: 'Mixed-é' }); await settle();
    expect(root().querySelector('[role="status"]')?.textContent).toBe('Entreprise modifiée.');
    expect(root().textContent).toContain('Mixed-é');
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Entreprise modifiée avec succès.', '');
  });

  it('never notifies for a pending PATCH cancelled when the page is destroyed', async () => {
    await loaded(); page.editor()!.form.controls.code.setValue('Changed'); await submit();
    const patch = request();
    expect(toastr.success).not.toHaveBeenCalled();
    harness.fixture.destroy();
    expect(patch.cancelled).toBe(true);
    expect(() => patch.flush(company)).toThrow();
    expect(toastr.success).not.toHaveBeenCalled();
  });

  it.each(['', '   ', 'Texte\nmodifié'])('sends only a deliberate description update %j', async description => {
    await loaded(); page.editor()!.form.controls.description.setValue(description); await submit();
    const patch = request();
    expect(patch.request.body).toEqual({ description: description === '' ? null : description });
    patch.flush(null, { status: 409, statusText: 'Conflict' }); await settle();
  });

  it('trims a changed name without changing the untouched code or description', async () => {
    await loaded(); page.editor()!.form.controls.name.setValue(' Nouveau nom '); await submit();
    const patch = request(); expect(patch.request.body).toEqual({ name: 'Nouveau nom' });
    patch.flush(null, { status: 409, statusText: 'Conflict' }); await settle();
  });

  it('blocks empty or overlong names/codes with accessible focus and no null name/code writes', async () => {
    await loaded(); page.editor()!.form.controls.name.setValue('   '); await submit();
    expect(document.activeElement).toBe(root().querySelector('#company-name'));
    expect(root().textContent).toContain('Le nom est obligatoire');
    page.editor()!.form.controls.name.setValue('😀'.repeat(151)); await submit();
    expect(root().textContent).toContain('150 caractères maximum');
    http.expectNone(() => true);
  });

  it('maps an actual PATCH 409 to Code, keeps edits and focuses the field', async () => {
    await loaded(); await failSave(409, { detail: 'Conflict' });
    expect(root().querySelector('#code-error')?.textContent).toContain('déjà utilisé');
    expect(document.activeElement).toBe(root().querySelector('#company-code'));
    expect(page.editor()!.form.controls.code.value).toBe('Changed');
    expect(page.state()).toBe('error'); http.expectNone(() => true);
  });

  it('maps PATCH 422 to known fields and preserves user input', async () => {
    await loaded(); await failSave(422, { detail: [{ loc: ['body', 'description'], msg: '<b>Error</b>' }, { loc: ['body', 'unknown'] }] });
    expect(root().querySelector('#description-error')?.textContent).toContain('pas acceptée');
    expect(document.activeElement).toBe(root().querySelector('#company-description'));
    expect(root().querySelector('b')).toBeNull();
    expect(page.editor()!.form.controls.code.value).toBe('Changed');
  });

  it('treats PATCH 404 as disappearance with retained input and no recreation', async () => {
    await loaded(); await failSave(404);
    expect(root().querySelector('[role="alert"]')?.textContent).toContain('n’existe plus');
    expect(page.editor()!.form.controls.code.value).toBe('Changed');
    expect(page.uncertain()).toBe(false); http.expectNone(() => true);
  });

  it.each([0, 500])('blocks uncertain PATCH %s until explicit verification, without retrying or reloading over edits', async status => {
    await loaded(); await failSave(status);
    expect(page.uncertain()).toBe(true);
    expect(root().textContent).toContain('peut avoir été modifiée');
    expect(root().querySelector('a[target="_blank"]')?.getAttribute('href')).toBe('/companies/7?page=3&page_size=50&search=Applied');
    await submit(); page.retryLoad(); http.expectNone(() => true);
    page.acknowledgeVerification(); await settle(); await submit();
    const retry = request(); expect(retry.request.method).toBe('PATCH'); expect(retry.request.body).toEqual({ code: 'Changed' });
    retry.flush(null, { status: 409, statusText: 'Conflict' }); await settle();
  });

  it('cancels a clean form to the detail with context and asks before discarding a real edit', async () => {
    await loaded(); const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    page.editor()!.form.controls.description.setValue('Changed'); page.cancel(); await settle();
    expect(TestBed.inject(Router).url).toContain('/companies/7/edit');
    expect(confirm).toHaveBeenCalledOnce();
    page.editor()!.form.controls.description.setValue(company.description!);
    page.cancel(); await settle();
    expect(TestBed.inject(Router).url).toBe('/companies/7?page=3&page_size=50&search=Applied');
    request().flush(company); await settle();
    expect(confirm).toHaveBeenCalledOnce();
  });

  it('protects dirty identifier changes, then cancels obsolete GETs when navigation is accepted', async () => {
    await loaded(); page.editor()!.form.controls.code.setValue('Dirty');
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    expect(await TestBed.inject(Router).navigateByUrl('/companies/8/edit')).toBe(false);
    http.expectNone(() => true);
    confirm.mockReturnValue(true);
    await harness.navigateByUrl('/companies/8/edit', CompanyFormPageComponent); await settle();
    const old = request(8);
    await harness.navigateByUrl('/companies/9/edit', CompanyFormPageComponent); await settle();
    expect(old.cancelled).toBe(true);
    request(9).flush({ ...company, id: 9, name: 'Third company' }); await settle();
    expect(page.editor()!.form.controls.name.value).toBe('Third company');
    expect(page.editor()!.hasChanges()).toBe(false);
    expect(toastr.success).not.toHaveBeenCalled();
  });
});
