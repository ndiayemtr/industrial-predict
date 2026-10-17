import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbToastrService } from '@nebular/theme';
import { SITE_ROUTES } from '../../sites.routes';
import { SiteCreateComponent } from './site-create.component';
import { SiteCreate } from '../../models/site-write.model';

const company = { id: 7, name: 'PETROSEN', code: 'PETROSEN', description: null, created_at: '', updated_at: '' };
const site = { id: 87, company_id: 7, name: 'Usine 日本', code: 'US-é', description: null, created_at: '2026-10-17T12:00:00', updated_at: '2026-10-17T12:00:00' };
const catalog = { items: [company], total: 1, pages: 1, page: 1, page_size: 50 };

describe('Site creation page', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: SiteCreateComponent;
  const toastr = { success: vi.fn() };
  const root = () => harness.routeNativeElement!;
  const companies = () => http.expectOne(req => req.url === '/api/v1/companies');
  const reference = (id = 7) => http.expectOne(`/api/v1/companies/${id}`);
  const post = () => http.expectOne(req => req.url === '/api/v1/sites' && req.method === 'POST');
  beforeEach(() => {
    toastr.success.mockClear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      { provide: NbToastrService, useValue: toastr }, provideRouter([{ path: 'sites', children: SITE_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.expectNone(req => req.method === 'PATCH' || req.method === 'DELETE'); http.verify(); } finally { vi.restoreAllMocks(); } });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/sites/new') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, SiteCreateComponent); await settle();
  }
  async function ready(url = '/sites/new?company_id=7') { await open(url); companies().flush(catalog); reference().flush(company); await settle(); }
  function fill() { component.editor()!.form.patchValue({ name: ' Usine 日本 ', code: 'US-é' }); }
  async function submit() { root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle(); }

  it('matches new before detail, loads only the catalog, and never selects a company implicitly', async () => {
    await open(); companies().flush(catalog); await settle();
    expect(root().querySelectorAll('h1')).toHaveLength(1); expect(root().querySelector('h1')?.textContent).toBe('Nouveau site industriel');
    expect(component.editor()!.form.controls.company_id.value).toBeNull(); expect(component.canLeave()).toBe(true);
    expect(root().querySelector('#site-company-help')?.textContent).toBe('Choisissez une entreprise pour rattacher le site.');
    expect(root().querySelector('#site-company_id')?.textContent).toContain('PETROSEN');
    await submit(); expect(document.activeElement?.id).toBe('site-company_id'); http.expectNone(() => true);
  });
  it.each(['0', '-1', 'abc', '9007199254740992'])('rejects invalid company context %s without detail GET or POST', async id => {
    await open(`/sites/new?company_id=${id}`); companies().flush(catalog); await settle();
    expect(component.contextNotice).toContain('pas valide'); fill(); await submit();
    expect(component.selectedCompany()).toBeNull(); http.expectNone(() => true);
  });
  it('resolves a company outside the first catalog page before accepting its numeric selection', async () => {
    await open('/sites/new?company_id=99&page=3&page_size=50&search=Usine&returnUrl=https://invalid.example');
    companies().flush(catalog); fill(); await submit(); http.expectNone(req => req.method === 'POST');
    reference(99).flush({ ...company, id: 99, code: 'PTR-001' }); await settle();
    expect(root().querySelector<HTMLSelectElement>('#site-company_id')?.selectedOptions[0].textContent).toBe('PETROSEN - PTR-001');
    expect(component.listQuery()).toEqual({ company_id: 99, page: 3, page_size: 50, search: 'Usine' });
    expect(root().querySelector('#site-company-help')).toBeNull();
    expect(root().textContent).toContain('1 / 1 entreprises chargées');
    await submit(); expect(post().request.body).toEqual({ company_id: 99, name: 'Usine 日本', code: 'US-é' });
  });
  it('blocks nonexistent or mismatching references without losing entered business fields', async () => {
    await open('/sites/new?company_id=7'); companies().flush(catalog); fill();
    reference().flush(null, { status: 404, statusText: 'Not found' }); await settle(); await submit();
    expect(root().textContent).toContain('Cette entreprise n’existe pas');
    expect(root().querySelector('#site-company-help')).not.toBeNull();
    expect(component.editor()!.form.controls.name.value).toBe(' Usine 日本 '); http.expectNone(req => req.method === 'POST');
    component.editor()!.form.controls.company_id.setValue(8); await settle();
    reference(8).flush({ ...company, id: 99 }); await settle(); await submit();
    expect(component.selectedCompany()).toBeNull(); http.expectNone(() => true);
  });
  it('loads company pages without duplicates and retries a failed later page explicitly', async () => {
    await open(); companies().flush({ ...catalog, pages: 2, total: 51 }); await settle(); component.loadMoreCompanies();
    let req = companies(); expect(req.request.params.get('page')).toBe('2');
    req.flush(null, { status: 500, statusText: 'Error' }); await settle();
    expect(component.catalog().items).toEqual([company]); component.retryCatalog(); req = companies();
    expect(req.request.params.get('page')).toBe('2'); req.flush({ ...catalog, page: 2, pages: 2, total: 51, items: [company, { ...company, id: 8 }] }); await settle();
    expect(component.options().map(item => item.id)).toEqual([7, 8]); http.expectNone(() => true);
  });
  it('renders an empty catalog and permits a validated deep-linked company despite catalog failure', async () => {
    await open('/sites/new?company_id=7'); companies().flush(null, { status: 500, statusText: 'Error' });
    reference().flush(company); await settle(); expect(component.selectedCompany()?.id).toBe(7);
    component.retryCatalog(); companies().flush({ ...catalog, items: [], total: 0, pages: 0 }); await settle();
    expect(root().textContent).toContain('Aucune entreprise disponible'); expect(component.options()).toEqual([{ id: 7, label: 'PETROSEN' }]);
  });
  it('cancels obsolete company lookups and keeps names/codes free of numeric identifiers', async () => {
    await open('/sites/new?company_id=7'); companies().flush(catalog); const old = reference();
    component.editor()!.form.controls.company_id.setValue(8); await settle(); expect(old.cancelled).toBe(true);
    reference(8).flush({ ...company, id: 8, code: 'PTR-001' }); await settle();
    expect(component.listQuery()).toEqual({ company_id: 8, page: 1, page_size: 20 });
    expect(root().textContent).not.toContain('identifiant'); expect(component.selectedCompany()?.id).toBe(8);
    component.editor()!.form.controls.company_id.setValue(null); await settle(); expect(component.selectedCompany()).toBeNull(); http.expectNone(() => true);
  });
  it('POSTs once, blocks navigation during saving, then navigates before one success toast and accessible confirmation', async () => {
    await ready('/sites/new?company_id=7&page=3&page_size=50&search=Usine'); fill(); await submit();
    const req = post(); expect(req.request.body).toEqual({ company_id: 7, name: 'Usine 日本', code: 'US-é' });
    await submit(); component.save({ company_id: 7, name: 'Duplicate', code: 'DUP' }); http.expectNone(() => true);
    expect(component.canLeave()).toBe(false); expect(await TestBed.inject(Router).navigateByUrl('/sites')).toBe(false);
    expect(toastr.success).not.toHaveBeenCalled(); const confirm = vi.spyOn(window, 'confirm');
    req.flush(site, { status: 201, statusText: 'Created' }); await settle();
    expect(TestBed.inject(Router).url).toBe('/sites/87?company_id=7&page=3&page_size=50&search=Usine');
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Site créé avec succès.', '');
    expect(root().querySelector('[role="status"]')?.textContent).toBe('Site créé avec succès.');
    http.expectOne('/api/v1/sites/87').flush(site); reference().flush(company); await settle();
    expect(confirm).not.toHaveBeenCalled(); expect(toastr.success).toHaveBeenCalledTimes(1);
  });
  it('retains a created-site link and prevents another POST when navigation is cancelled, without a toast', async () => {
    await ready(); fill(); vi.spyOn(TestBed.inject(Router), 'navigate').mockResolvedValue(false);
    await submit(); post().flush(site); await settle();
    expect(component.state()).toBe('success'); expect(root().textContent).toContain('Site créé avec succès.');
    expect(root().querySelector('a[href^="/sites/87"]')).not.toBeNull(); expect(toastr.success).not.toHaveBeenCalled();
    await submit(); http.expectNone(() => true);
  });
  it.each(['', null, '  Description\n日本  '])('sends explicit description %s without converting it', async description => {
    await ready(); fill(); const control = component.editor()!.form.controls.description;
    control.setValue(description); control.markAsDirty(); await submit();
    expect(post().request.body).toEqual({ company_id: 7, name: 'Usine 日本', code: 'US-é', description });
  });
  it('whitelists the payload even if a caller supplies transport fields from a SiteRead', async () => {
    await ready(); const body = { ...site, created_at: 'raw', extra: 'not writable' };
    component.save(body as SiteCreate); const req = post();
    expect(req.request.body).toEqual({ company_id: 7, name: site.name, code: site.code, description: null });
  });
  it('sends null only after an explicit removal click and hides the now-useless action', async () => {
    await ready(); fill(); expect(root().querySelector('.remove-description')).toBeNull();
    const description = root().querySelector<HTMLTextAreaElement>('#site-description')!;
    description.value = 'Description'; description.dispatchEvent(new Event('input', { bubbles: true })); await settle();
    root().querySelector<HTMLButtonElement>('.remove-description')!.click(); await settle();
    expect(root().querySelector('.remove-description')).toBeNull(); await submit();
    expect(post().request.body).toEqual({ company_id: 7, name: 'Usine 日本', code: 'US-é', description: null });
  });
  it.each([404, 409, 422, 0, 500])('preserves input on save error %s without success notification or automatic POST retry', async status => {
    await ready(); fill(); await submit(); const req = post();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({ detail: 'Must not be exposed' }, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toBe('error'); expect(toastr.success).not.toHaveBeenCalled();
    expect(component.editor()!.form.controls.name.value).toBe(' Usine 日本 '); expect(root().textContent).not.toContain('Must not be exposed');
    expect(root().querySelector('[role="alert"]')).not.toBeNull();
    if (status === 409) { expect(component.fieldErrors()).toEqual({}); expect(component.message()).toContain('cause exacte'); }
    if (status === 404) { expect(component.selectedCompany()).toBeNull(); await submit(); http.expectNone(req => req.method === 'POST'); }
    if (status === 0 || status >= 500) { expect(component.uncertain()).toBe(true); await submit(); component.save({ company_id: 7, name: 'Again', code: 'X' }); }
    http.expectNone(() => true);
  });
  it('maps only recognized 422 body fields and focuses the first field without rendering raw server markup', async () => {
    await ready(); fill(); await submit(); post().flush({ detail: [
      { loc: ['body', 'name'], msg: '<b>Unsafe</b>' }, { loc: ['body', 'description'], msg: 'Invalid' },
      { loc: ['query', 'code'] }, { loc: ['body', 'unknown'] }
    ] }, { status: 422, statusText: 'Validation error' }); await settle();
    expect(component.fieldErrors()).toEqual({ name: 'Cette valeur n’est pas acceptée par le serveur.', description: 'Cette valeur n’est pas acceptée par le serveur.' });
    expect(document.activeElement?.id).toBe('site-name'); expect(root().querySelector('b')).toBeNull();
  });
  it('requires explicit verification before repeating an uncertain POST and retries company reads separately', async () => {
    await ready(); fill(); await submit(); post().error(new ProgressEvent('error')); await settle();
    component.acknowledgeVerification(); await settle(); await submit(); post().flush(null, { status: 404, statusText: 'Not found' }); await settle();
    component.retryCompany(); reference().flush(company); await settle(); expect(component.selectedCompany()?.id).toBe(7);
    http.expectNone(() => true);
  });
  it('lets a user recheck the parent after a generic conflict without assigning the conflict to Code', async () => {
    await ready(); fill(); await submit(); post().flush(null, { status: 409, statusText: 'Conflict' }); await settle();
    expect(component.fieldErrors()).toEqual({}); component.verifyCompany();
    reference().flush(null, { status: 404, statusText: 'Not found' }); await settle(); await submit();
    expect(component.selectedCompany()).toBeNull(); expect(toastr.success).not.toHaveBeenCalled(); http.expectNone(() => true);
  });
  it('guards abandon, beforeunload and cancel using actual changed values, with no success toast', async () => {
    await ready(); expect(component.canLeave()).toBe(true); fill();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    expect(await TestBed.inject(Router).navigateByUrl('/sites')).toBe(false); expect(confirm).toHaveBeenCalled();
    const event = new Event('beforeunload', { cancelable: true }); component.protectUnload(event as BeforeUnloadEvent); expect(event.defaultPrevented).toBe(true);
    confirm.mockReturnValue(true); component.cancel(); await settle();
    companies().flush(catalog); reference().flush(company);
    http.expectOne(req => req.url === '/api/v1/sites').flush({ items: [], total: 0, page: 1, page_size: 20, pages: 0 }); await settle();
    expect(TestBed.inject(Router).url).toBe('/sites?company_id=7&page=1&page_size=20'); expect(toastr.success).not.toHaveBeenCalled();
  });
  it('cancels pending reference requests when the page is destroyed', async () => {
    await open('/sites/new?company_id=7'); const read = reference(), page = companies(); harness.fixture.destroy();
    expect(read.cancelled).toBe(true); expect(page.cancelled).toBe(true);
  });
});
