import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbToastrService } from '@nebular/theme';
import { SiteRead } from '../../../../core/models/reference-data.model';
import { SITE_ROUTES } from '../../sites.routes';
import { SiteEditComponent } from './site-edit.component';

const site: SiteRead = { id: 3, company_id: 7, name: ' Usine 日本 ', code: 'US-é', description: '  Texte\n日本  ',
  created_at: '2026-08-31T14:58:20.179290', updated_at: '2026-10-16T13:51:15.910577+02:00' };
const company = { id: 7, name: 'PETROSEN', code: 'PETROSEN', description: null, created_at: '', updated_at: '' };

describe('Site editing page', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: SiteEditComponent;
  const toastr = { success: vi.fn() };
  const root = () => harness.routeNativeElement!;
  const read = (id = 3) => http.expectOne(`/api/v1/sites/${id}`);
  const parent = (id = 7) => http.expectOne(`/api/v1/companies/${id}`);
  const patch = () => http.expectOne(req => req.method === 'PATCH');
  beforeEach(() => {
    toastr.success.mockClear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      { provide: NbToastrService, useValue: toastr }, provideRouter([{ path: 'sites', children: SITE_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    try { http.expectNone(req => req.method === 'POST' || req.method === 'DELETE'); http.verify(); }
    finally { vi.restoreAllMocks(); }
  });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/sites/3/edit') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, SiteEditComponent); await settle();
  }
  async function ready(source = site, url = '/sites/3/edit') {
    await open(url); read().flush(source); parent(source.company_id).flush({ ...company, id: source.company_id }); await settle();
  }
  async function submit() { root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle(); }
  function change(name = 'Nom modifié') { component.editor()!.form.controls.name.setValue(name); }

  it('loads the actual site/company and presents readonly business labels and tracking outside the controls', async () => {
    await open('/sites/3/edit?company_id=99&page=2&page_size=50&search=Usine');
    expect(root().textContent).toContain('Chargement du site'); expect(root().querySelector('form')).toBeNull();
    read().flush(site); await settle(); expect(root().textContent).toContain('Chargement de la référence');
    parent().flush(company); await settle();
    expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(component.editor()!.form.getRawValue()).toEqual({ company_id: 7, name: site.name, code: site.code, description: site.description });
    expect(root().querySelector('select')).toBeNull(); expect(root().querySelector('.company-reference')?.textContent).toContain('PETROSEN');
    expect(root().querySelector('.company-reference')?.textContent?.match(/PETROSEN/g)).toHaveLength(1);
    expect(root().textContent).not.toContain('Identifiant');
    expect(root().querySelector('.tracking-information')?.textContent).toContain('31/08/2026 à 14:58');
    expect(root().querySelector('.tracking-information')?.textContent).toContain('16/10/2026 à 11:51 UTC');
    expect(root().querySelectorAll('.tracking-information input, .tracking-information textarea, .tracking-information select')).toHaveLength(0);
    expect(Object.keys(component.editor()!.form.controls)).toEqual(['company_id', 'name', 'code', 'description']);
    const tracking = root().querySelector('.tracking-information')!;
    expect(tracking.compareDocumentPosition(root().querySelector('.actions')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(root().querySelector('textarea')!.compareDocumentPosition(tracking) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(component.listQuery()).toEqual({ company_id: 99, page: 2, page_size: 50, search: 'Usine' });
    expect(component.canLeave()).toBe(true); http.expectNone(() => true);
  });
  it('does not PATCH unchanged or restored values and does not toast', async () => {
    await ready(); await submit(); expect(root().textContent).toContain('Aucune modification à enregistrer.');
    change(); change(site.name); await submit(); expect(component.editor()!.hasChanges()).toBe(false);
    http.expectNone(() => true); expect(toastr.success).not.toHaveBeenCalled();
  });
  it('PATCHes only raw differences without company_id, dates, trimming or a case change', async () => {
    await ready(); change('  Nouveau 日本  '); component.editor()!.form.controls.company_id.setValue(999);
    await submit(); const req = patch(); expect(req.request.url).toBe('/api/v1/sites/3');
    expect(req.request.body).toEqual({ name: '  Nouveau 日本  ' });
    expect(component.original()).toEqual(site);
  });
  it.each(['DEMO-SITE-001', 'DEMO-SITE-001 (inchangé)'])('excludes untouched code %s when only name and description change', async code => {
    await ready({ ...site, code });
    const input = root().querySelector<HTMLInputElement>('#site-code')!;
    // A touched/dirty control is not a difference if its value is unchanged.
    component.editor()!.form.controls.code.markAsDirty();
    const name = root().querySelector<HTMLInputElement>('#site-name')!;
    name.value = 'Site de démonstration - Modifié'; name.dispatchEvent(new Event('input', { bubbles: true }));
    const description = root().querySelector<HTMLTextAreaElement>('#site-description')!;
    description.value = 'Description mise à jour pour valider le formulaire de modification.';
    description.dispatchEvent(new Event('input', { bubbles: true })); await submit();
    const expected = { name: name.value, description: description.value };
    const req = patch();
    expect(input.value).toBe(code); expect(component.original()?.code).toBe(code);
    expect(req.request.body).toEqual(expected); expect(req.request.serializeBody()).toBe(JSON.stringify(expected));
    expect(Object.keys(req.request.body)).toEqual(['name', 'description']);
  });
  it('transmits a suffix only when it is explicitly entered in the code field, without silently correcting it', async () => {
    await ready({ ...site, code: 'DEMO-SITE-001' });
    const input = root().querySelector<HTMLInputElement>('#site-code')!;
    input.value = 'DEMO-SITE-001 (inchangé)'; input.dispatchEvent(new Event('input', { bubbles: true })); await submit();
    expect(patch().request.body).toEqual({ code: 'DEMO-SITE-001 (inchangé)' });
  });
  it.each([undefined, null, ''])('omits unchanged description %s from PATCH', async description => {
    await ready({ ...site, description } as SiteRead); change(); await submit();
    expect(patch().request.body).toEqual({ name: 'Nom modifié' });
  });
  it.each(['', null, '  Description\n日本  '])('preserves changed description %s exactly', async description => {
    await ready(); component.editor()!.form.controls.description.setValue(description); await submit();
    expect(patch().request.body).toEqual({ description });
  });
  it('sends null after explicit removal and restores keyboard focus without adding dates to PATCH', async () => {
    await ready(); root().querySelector<HTMLButtonElement>('.remove-description')!.click(); await settle();
    expect(document.activeElement?.id).toBe('site-description'); expect(root().querySelector('.remove-description')).toBeNull();
    await submit(); expect(patch().request.body).toEqual({ description: null });
  });
  it('validates blank fields, Unicode limits and raw whitespace length with first invalid focus', async () => {
    await ready(); const form = component.editor()!.form;
    change('  '); await submit(); expect(document.activeElement?.id).toBe('site-name');
    change('日'.repeat(150)); form.controls.code.setValue('é'.repeat(51)); await submit();
    expect(document.activeElement?.id).toBe('site-code');
    change(' ' + '日'.repeat(150)); form.controls.code.setValue('é'.repeat(50)); await submit();
    expect(document.activeElement?.id).toBe('site-name');
    change('日'.repeat(150)); await submit(); expect(patch().request.body).toEqual({ name: '日'.repeat(150), code: 'é'.repeat(50) });
  });
  it('blocks duplicate submission and navigation while saving then navigates before one toast and persistent confirmation', async () => {
    await ready(site, '/sites/3/edit?company_id=7&page=2&page_size=50&search=Usine'); change(); await submit();
    const req = patch(); await submit(); component.save({ name: 'duplicate' }); http.expectNone(() => true);
    expect(component.canLeave()).toBe(false); expect(await TestBed.inject(Router).navigateByUrl('/sites/4/edit')).toBe(false);
    expect(toastr.success).not.toHaveBeenCalled(); req.flush({ ...site, name: 'Nom modifié' }); await settle();
    expect(TestBed.inject(Router).url).toBe('/sites/3?company_id=7&page=2&page_size=50&search=Usine');
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Site modifié avec succès.', '');
    expect(root().textContent).toContain('Site modifié avec succès.');
    read().flush(site); parent().flush(company); await settle(); expect(toastr.success).toHaveBeenCalledTimes(1);
  });
  it.each([false, 'reject'])('keeps a success link and blocks another PATCH if navigation fails: %s', async failure => {
    await ready(); change(); const navigate = vi.spyOn(TestBed.inject(Router), 'navigate');
    if (failure === false) navigate.mockResolvedValue(false); else navigate.mockRejectedValue(new Error('navigation'));
    await submit(); patch().flush(site); await settle();
    expect(component.state()).toBe('success'); expect(root().querySelector('a[href^="/sites/3"]')).not.toBeNull();
    expect(root().textContent).toContain('Site modifié avec succès.'); expect(toastr.success).not.toHaveBeenCalled();
    await submit(); http.expectNone(() => true);
  });
  it.each([404, 409, 422, 0, 500])('retains changes after PATCH failure %s without toast, recreation or automatic retry', async status => {
    await ready(); change(); await submit(); const req = patch();
    if (status === 0) req.error(new ProgressEvent('error'));
    else req.flush({ detail: status === 422 ? [{ loc: ['body', 'code'], msg: 'Invalid' }, { loc: ['body', 'company_id'] }] : 'Conflict' }, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toBe('error'); expect(component.editor()!.form.controls.name.value).toBe('Nom modifié');
    expect(root().querySelector('[role="alert"]')).not.toBeNull(); expect(toastr.success).not.toHaveBeenCalled();
    expect(component.uncertain()).toBe(status === 0 || status >= 500);
    if (status === 409) { expect(component.fieldErrors().code).toBeUndefined(); expect(root().textContent).toContain('cause exacte n’est pas précisée'); }
    if (status === 422) { expect(component.fieldErrors().company_id).toBeUndefined(); expect(document.activeElement?.id).toBe('site-code'); }
    if (status === 404) expect(root().textContent).toContain('aucune recréation automatique');
    if (component.uncertain()) { await submit(); http.expectNone(() => true); component.acknowledgeVerification(); }
    http.expectNone(() => true);
  });
  it.each([404, 0, 500])('handles GET failure %s without an empty editor and retries only network/server', async status => {
    await open(); const req = read();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush(null, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toBe('load-error'); expect(root().querySelector('form')).toBeNull();
    if (status === 404) expect(root().textContent).toContain('Site introuvable (404)');
    component.retryLoad();
    if (status !== 404) { read().flush(site); parent().flush(company); await settle(); expect(component.state()).toBe('idle'); }
    http.expectNone(() => true);
  });
  it.each([404, 0, 500])('keeps company reference error %s explicit and never offers transfer', async status => {
    await open(); read().flush(site); const req = parent();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush(null, { status, statusText: 'Error' });
    await settle(); expect(root().textContent).toContain('Entreprise indisponible'); expect(root().querySelector('select')).toBeNull();
    change(); await submit(); http.expectNone(() => true);
    if (status !== 404) {
      const retry = [...root().querySelectorAll<HTMLButtonElement>('button')].find(el => el.textContent?.includes('Réessayer'))!;
      expect(retry.disabled).toBe(false); retry.click(); await settle(); parent().flush({ ...company, code: 'PTR-001' }); await settle();
      expect(root().textContent).toContain('PETROSEN - PTR-001'); expect(component.editor()!.form.controls.name.value).toBe('Nom modifié');
    }
  });
  it('rejects a mismatching company reference without enabling the PATCH', async () => {
    await open(); read().flush(site); parent().flush({ ...company, id: 99 }); await settle();
    expect(component.company()).toBeNull(); change(); await submit(); http.expectNone(() => true);
  });
  it('cancels obsolete site and company reads and resets tracking and changes for the new id', async () => {
    await open(); const old = read();
    await harness.navigateByUrl('/sites/4/edit', SiteEditComponent); await settle(); expect(old.cancelled).toBe(true);
    read(4).flush({ ...site, id: 4, company_id: 8 }); const oldCompany = parent(8);
    await harness.navigateByUrl('/sites/5/edit', SiteEditComponent); await settle(); expect(oldCompany.cancelled).toBe(true);
    read(5).flush({ ...site, id: 5, name: 'Autre site', created_at: 'invalid' }); parent().flush(company); await settle();
    expect(component.original()?.id).toBe(5); expect(component.editor()!.form.controls.name.value).toBe('Autre site');
    expect(root().textContent).toContain('Non disponible'); expect(component.canLeave()).toBe(true);
  });
  it.each(['0', 'abc', '9007199254740992'])('rejects invalid id %s before HTTP', async id => {
    await open(`/sites/${id}/edit`); expect(component.state()).toBe('load-error'); http.expectNone(() => true);
  });
  it('protects route changes and unload, permits restored values and returns to detail with context on cancellation', async () => {
    await ready(site, '/sites/3/edit?company_id=7&page=2&page_size=50'); change();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    expect(await TestBed.inject(Router).navigateByUrl('/sites/4/edit')).toBe(false);
    const event = new Event('beforeunload', { cancelable: true }); component.protectUnload(event as BeforeUnloadEvent);
    expect(event.defaultPrevented).toBe(true); expect(confirm).toHaveBeenCalledTimes(1);
    change(site.name); expect(component.canLeave()).toBe(true);
    const clean = new Event('beforeunload', { cancelable: true }); component.protectUnload(clean as BeforeUnloadEvent); expect(clean.defaultPrevented).toBe(false);
    change(); confirm.mockReturnValue(true); component.cancel(); await settle();
    expect(TestBed.inject(Router).url).toBe('/sites/3?company_id=7&page=2&page_size=50');
    read().flush(site); parent().flush(company); await settle(); expect(toastr.success).not.toHaveBeenCalled();
  });
});
