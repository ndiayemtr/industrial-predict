import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbToastrService } from '@nebular/theme';
import { EQUIPMENT_ROUTES } from '../../equipments.routes';
import { EquipmentCreate } from '../../models/equipment-write.model';
import { EquipmentCreateComponent } from './equipment-create.component';

const company = { id: 7, name: 'Entreprise fictive', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7, name: 'Site fictif', code: 'SITE' };
const equipment = { ...company, id: 87, site_id: 9, name: 'Pompe 日本', code: 'ÉQ-Test', equipment_type: 'Type Libre', status: 'operational', criticality: 'medium' };
const companies = { items: [company], total: 1, page: 1, page_size: 50, pages: 1 };
const sites = { ...companies, items: [site] };

describe('Equipment creation - isolated HTTP writes', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: EquipmentCreateComponent;
  const toastr = { success: vi.fn() };
  const root = () => harness.routeNativeElement!;
  const read = (resource: string) => http.expectOne(req => req.url === `/api/v1/${resource}` && req.method === 'GET');
  const post = () => http.expectOne(req => req.url === '/api/v1/equipments' && req.method === 'POST');
  const editor = () => component.editor()!;
  beforeEach(() => {
    toastr.success.mockClear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      { provide: NbToastrService, useValue: toastr }, provideRouter([{ path: 'equipments', children: EQUIPMENT_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    try {
      http.expectNone(req => req.method === 'PATCH' || req.method === 'DELETE');
      http.expectNone(req => /health-score|rul|predictions|recommendations/.test(req.url)); http.verify();
    } finally { vi.restoreAllMocks(); }
  });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/equipments/new') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, EquipmentCreateComponent); await settle();
  }
  async function ready(url = '/equipments/new?company_id=7&site_id=9') {
    await open(url); read('companies').flush(companies); read('companies/7').flush(company);
    read('sites/9').flush(site); read('sites').flush(sites); await settle();
  }
  function fill() { editor().form.patchValue({ name: ' Pompe 日本 ', code: ' ÉQ-Test ', equipment_type: ' Type Libre ' }); }
  async function submit() { root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle(); }
  async function detail() { read('equipments/87').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); await settle(); }

  it('matches new before detail and never selects catalog defaults or requests equipment automatically', async () => {
    await open(); read('companies').flush(companies); await settle();
    expect(root().querySelector('h1')?.textContent).toBe('Nouvel équipement industriel'); expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(editor().form.controls.company_id.value).toBeNull(); expect(editor().form.controls.site_id.value).toBeNull();
    expect(component.canLeave()).toBe(true); await submit(); expect(document.activeElement?.id).toBe('equipment-company_id'); http.expectNone(() => true);
  });
  it('prefills only after the complete real parent relationship is verified, preserving draft business text', async () => {
    await open('/equipments/new?company_id=7&site_id=9'); read('companies').flush({ ...companies, items: [], total: 51, pages: 2 });
    editor().form.controls.name.setValue('Texte conservé'); expect(editor().form.controls.company_id.value).toBeNull();
    read('companies/7').flush(company); expect(editor().form.controls.site_id.value).toBeNull();
    read('sites').flush({ ...sites, items: [], total: 51, pages: 2 }); read('sites/9').flush(site); await settle();
    expect(editor().form.controls.company_id.value).toBe(7); expect(editor().form.controls.site_id.value).toBe(9);
    expect(editor().form.controls.name.value).toBe('Texte conservé');
    expect(component.references.companyOptions()).toEqual([{ id: 7, label: 'Entreprise fictive - ENT' }]);
    expect(component.references.siteOptions()).toEqual([{ id: 9, label: 'Site fictif - SITE' }]);
  });
  it('does not consider verified context prefill an unsaved modification', async () => {
    await ready(); expect(editor().hasChanges()).toBe(false); expect(component.canLeave()).toBe(true);
  });
  it('resolves site-only context via its actual company without choosing a catalog entry', async () => {
    await open('/equipments/new?site_id=9'); read('companies').flush(companies); read('sites/9').flush(site);
    read('companies/7').flush(company); read('sites').flush(sites); await settle();
    expect(editor().form.controls.company_id.value).toBe(7); expect(editor().form.controls.site_id.value).toBe(9);
    expect(component.listQuery().company_id).toBeUndefined();
  });
  it('verifies company-only context without selecting a site', async () => {
    await open('/equipments/new?company_id=7'); read('companies').flush(companies); read('companies/7').flush(company); read('sites').flush(sites); await settle();
    expect(editor().form.controls.company_id.value).toBe(7); expect(editor().form.controls.site_id.value).toBeNull();
    fill(); await submit(); expect(document.activeElement?.id).toBe('equipment-site_id'); http.expectNone(() => true);
  });
  it.each(['company_id=0&site_id=9', 'company_id=abc&site_id=9', 'site_id=-1', 'site_id=9007199254740992'])('ignores invalid parent context %s without unsafe reads or writes', async query => {
    await open(`/equipments/new?${query}`); read('companies').flush(companies); await settle();
    expect(root().textContent).toContain('contexte de rattachement est invalide'); expect(editor().form.controls.site_id.value).toBeNull(); http.expectNone(() => true);
  });
  it('blocks mismatched company/site context without losing text or posting', async () => {
    await open('/equipments/new?company_id=7&site_id=9'); read('companies').flush(companies); fill();
    read('companies/7').flush(company); read('sites').flush(sites); read('sites/9').flush({ ...site, company_id: 8 }); await settle();
    expect(component.references.state()).toBe('error'); expect(editor().form.controls.company_id.value).toBeNull();
    expect(editor().form.controls.name.value).toBe(' Pompe 日本 '); await submit(); http.expectNone(() => true);
  });
  it('loads catalog pages and retries errors without erasing earlier pages', async () => {
    await open(); read('companies').flush({ ...companies, total: 51, pages: 2 }); component.references.moreCompanies();
    let req = read('companies'); expect(req.request.params.get('page')).toBe('2'); req.flush({}, { status: 500, statusText: 'Error' }); await settle();
    expect(component.references.companyOptions()).toHaveLength(1); component.references.retryCompanies(); req = read('companies');
    expect(req.request.params.get('page')).toBe('2'); req.flush({ ...companies, page: 2, total: 51, pages: 2, items: [company, { ...company, id: 8 }] });
    editor().form.controls.company_id.setValue(7); read('companies/7').flush(company);
    read('sites').flush({ ...sites, total: 51, pages: 2 }); component.references.moreSites(); req = read('sites');
    expect(req.request.params.get('company_id')).toBe('7'); expect(req.request.params.get('page')).toBe('2');
    req.flush({}, { status: 500, statusText: 'Error' }); component.references.retrySites();
    read('sites').flush({ ...sites, page: 2, total: 51, pages: 2, items: [site, { ...site, id: 10 }] }); await settle();
    expect(component.references.siteOptions()).toHaveLength(2); expect(editor().form.controls.site_id.value).toBeNull();
  });
  it('cancels old reference and site catalog requests when a user changes company', async () => {
    await open('/equipments/new?company_id=7&site_id=9'); read('companies').flush(companies); read('companies/7').flush(company);
    const oldCatalog = read('sites'), oldSite = read('sites/9'); fill(); editor().form.controls.company_id.setValue(8); await settle();
    expect(oldCatalog.cancelled).toBe(true); expect(oldSite.cancelled).toBe(true); expect(editor().form.controls.site_id.value).toBeNull();
    read('companies/8').flush({ ...company, id: 8 }); read('sites').flush({ ...sites, items: [], total: 0, pages: 0 }); await settle();
    expect(editor().form.controls.name.value).toBe(' Pompe 日本 '); expect(root().textContent).toContain('Aucun site disponible'); http.expectNone(() => true);
  });
  it('permits an explicit site change only after verifying its real membership', async () => {
    await ready(); fill(); editor().form.controls.site_id.setValue(10); await submit(); http.expectNone(req => req.method === 'POST');
    read('companies/7').flush(company); read('sites/10').flush({ ...site, id: 10 }); await settle(); await submit();
    expect(post().request.body.site_id).toBe(10);
  });
  it.each([0, 404, 500])('blocks an unavailable site %s independently of company catalog success', async status => {
    await open('/equipments/new?company_id=7&site_id=9'); read('companies').flush(companies); read('companies/7').flush(company); read('sites').flush(sites);
    fill(); const req = read('sites/9'); if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' });
    await settle(); expect(component.references.site()).toBeNull(); await submit(); http.expectNone(req => req.method === 'POST');
    expect(editor().form.controls.name.value).toBe(' Pompe 日本 ');
    if (status === 0 || status >= 500) { component.verifyReferences(); read('companies/7').flush(company); read('sites/9').flush(site); await settle(); }
    http.expectNone(() => true);
  });
  it('rejects a cross-company site catalog and a mismatched returned reference identity', async () => {
    await open('/equipments/new?company_id=7&site_id=9'); read('companies').flush(companies); read('companies/7').flush(company);
    read('sites').flush({ ...sites, items: [{ ...site, company_id: 8 }] }); read('sites/9').flush({ ...site, id: 10 }); await settle();
    expect(component.references.sites().status).toBe('error'); expect(component.references.siteOptions()).toHaveLength(0);
    expect(component.references.state()).toBe('error'); await submit(); http.expectNone(() => true);
  });
  it('cancels an obsolete company read and does not reuse a site from another company', async () => {
    await open('/equipments/new?company_id=7'); read('companies').flush(companies); const oldCompany = read('companies/7');
    editor().form.controls.company_id.setValue(8); expect(oldCompany.cancelled).toBe(true);
    read('companies/8').flush({ ...company, id: 8 }); read('sites').flush({ ...sites, items: [], total: 0, pages: 0 }); await settle();
    expect(root().querySelector('a[href^="/sites/new"]')?.getAttribute('href')).toBe('/sites/new?company_id=8');
    editor().form.controls.site_id.setValue(9); read('companies/8').flush({ ...company, id: 8 }); read('sites/9').flush(site); await settle();
    expect(component.references.state()).toBe('error'); await submit(); http.expectNone(req => req.method === 'POST');
  });
  it('sanitizes invalid filter context without changing visible create defaults', async () => {
    await ready('/equipments/new?company_id=7&site_id=9&page=-1&page_size=101&status=invalid&criticality=urgent&search=%20%20&returnUrl=https://example.com');
    expect(component.listQuery()).toEqual({ company_id: 7, site_id: 9, page: 1, page_size: 20, search: undefined, status: undefined, criticality: undefined });
    expect(editor().form.controls.status.value).toBe('operational'); expect(editor().form.controls.criticality.value).toBe('medium');
    expect(component.canLeave()).toBe(true);
  });
  it.each([0, 404, 500])('blocks parent error %s, conserves input and retries only GET transient failures', async status => {
    await open('/equipments/new?company_id=7&site_id=9'); read('companies').flush(companies); fill(); const req = read('companies/7');
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' }); await settle(); await submit();
    expect(component.references.state()).toBe('error'); expect(editor().form.controls.name.value).toBe(' Pompe 日本 '); http.expectNone(req => req.method === 'POST');
    if (status === 0 || status >= 500) { component.verifyReferences(); read('companies/7').flush(company); read('sites/9').flush(site); read('sites').flush(sites); await settle(); }
    http.expectNone(() => true);
  });
  it('posts once with defaults independent of list filters, blocks saving navigation, then notifies after successful detail navigation', async () => {
    await ready('/equipments/new?company_id=7&site_id=9&search=Pompe&status=maintenance&criticality=critical&page=3&page_size=50'); fill(); await submit();
    const req = post(); expect(req.request.body).toEqual({ site_id: 9, name: 'Pompe 日本', code: 'ÉQ-Test', equipment_type: 'Type Libre', status: 'operational', criticality: 'medium' });
    expect(JSON.parse(req.request.serializeBody() as string)).toEqual(req.request.body);
    await submit(); component.save(req.request.body); http.expectNone(() => true); expect(component.canLeave()).toBe(false);
    expect(await TestBed.inject(Router).navigateByUrl('/equipments')).toBe(false); expect(toastr.success).not.toHaveBeenCalled();
    const confirm = vi.spyOn(window, 'confirm'); req.flush(equipment, { status: 201, statusText: 'Created' }); await settle();
    expect(TestBed.inject(Router).url).toBe('/equipments/87?company_id=7&site_id=9&page=3&page_size=50&search=Pompe&status=maintenance&criticality=critical');
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Équipement créé avec succès.', '');
    expect(root().querySelector('.creation-confirmation')?.textContent).toBe('Équipement créé avec succès.');
    await detail(); expect(confirm).not.toHaveBeenCalled(); expect(toastr.success).toHaveBeenCalledTimes(1);
  });
  it('sends changed enums and strips every unrelated property from a structural caller', async () => {
    await ready(); fill(); const body = { ...equipment, company_id: 7, created_at: 'raw', updated_at: 'raw', sensor_count: 4, unknown: 'discard', status: 'out_of_service', criticality: 'high' };
    component.save(body as EquipmentCreate); const req = post();
    expect(req.request.body).toEqual({ site_id: 9, name: 'Pompe 日本', code: 'ÉQ-Test', equipment_type: 'Type Libre', description: null, status: 'out_of_service', criticality: 'high' });
  });
  it.each(['', null, '  Description 日本\n ligne  '])('posts explicit description %s without implicit normalization', async description => {
    await ready(); fill(); editor().form.controls.description.setValue(description); editor().form.controls.description.markAsDirty(); await submit();
    expect(post().request.body.description).toBe(description);
  });
  it.each([409, 422, 401, 403, 404, 0, 500])('handles write error %s without raw server messages, lost input, success toast or auto retry', async status => {
    await ready(); fill(); await submit(); const req = post();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({ detail: '<script>SECRET_SERVER_DETAIL</script>' }, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toBe('error'); expect(editor().form.controls.name.value).toBe(' Pompe 日本 ');
    expect(root().textContent).not.toContain('SECRET_SERVER_DETAIL'); expect(toastr.success).not.toHaveBeenCalled();
    if (status === 409) { expect(component.fieldErrors()).toEqual({}); expect(component.message()).toContain('cause exacte'); }
    if (status === 404) { await submit(); http.expectNone(req => req.method === 'POST'); component.verifyReferences(); read('companies/7').flush(company); read('sites/9').flush(site); await settle(); }
    if (status === 0 || status >= 500) { expect(component.uncertain()).toBe(true); await submit(); http.expectNone(req => req.method === 'POST'); component.acknowledgeVerification(); expect(component.uncertain()).toBe(false); }
    http.expectNone(() => true);
  });
  it('requires an explicit new submit after acknowledging an uncertain POST', async () => {
    await ready(); fill(); await submit(); post().error(new ProgressEvent('error')); await settle();
    component.acknowledgeVerification(); await settle(); http.expectNone(() => true); await submit(); post().flush(equipment); await settle(); await detail();
  });
  it('maps only known body fields in 422 and focuses the first field in form order', async () => {
    await ready(); fill(); await submit(); post().flush({ detail: [
      { loc: ['body', 'code'], msg: '<img src=x>' }, { loc: ['body', 'name'] }, { loc: ['body', 'company_id'] },
      { loc: ['query', 'site_id'] }, { loc: ['body', 'unknown'] }, { loc: ['body', 'description', 0] }, null
    ] }, { status: 422, statusText: 'Invalid' }); await settle();
    expect(Object.keys(component.fieldErrors()).sort()).toEqual(['code', 'name']); expect(document.activeElement?.id).toBe('equipment-name');
    expect(root().textContent).not.toContain('<img'); expect(root().querySelector('#equipment-name')?.getAttribute('aria-invalid')).toBe('true');
    editor().form.controls.name.setValue('Correction'); await settle(); expect(component.fieldErrors()).toEqual({});
  });
  it.each([false, 'reject'])('retains a recovery link after successful POST and failed navigation %s without rewriting', async failure => {
    await ready(); fill(); const navigation = vi.spyOn(TestBed.inject(Router), 'navigate');
    if (failure === false) navigation.mockResolvedValue(false); else navigation.mockRejectedValue(new Error('Navigation error'));
    await submit(); post().flush(equipment); await settle();
    expect(component.state()).toBe('success'); expect(root().querySelector('.created-link')?.getAttribute('href')).toBe('/equipments/87?company_id=7&site_id=9&page=1&page_size=20');
    expect(component.message()).toContain('sans soumettre à nouveau'); expect(toastr.success).not.toHaveBeenCalled(); await submit(); http.expectNone(() => true);
    navigation.mockRestore(); root().querySelector<HTMLAnchorElement>('.created-link')!.click(); await settle();
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Équipement créé avec succès.', ''); await detail();
    expect(root().querySelector('.creation-confirmation')?.textContent).toBe('Équipement créé avec succès.');
  });
  it('preserves the original return context even when creating at another site', async () => {
    await ready('/equipments/new?company_id=7&site_id=9&page=2&page_size=100&search=old&status=maintenance&criticality=low'); fill();
    editor().form.controls.site_id.setValue(10); read('companies/7').flush(company); read('sites/10').flush({ ...site, id: 10 }); await settle();
    expect(component.listQuery()).toMatchObject({ company_id: 7, site_id: 9, page: 2, page_size: 100, search: 'old', status: 'maintenance', criticality: 'low' });
    await submit(); expect(post().request.body.site_id).toBe(10);
  });
  it('protects actual unsaved changes and permits restored values without confirmation', async () => {
    await ready(); const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false); expect(component.canLeave()).toBe(true); expect(confirm).not.toHaveBeenCalled();
    fill(); expect(component.canLeave()).toBe(false); expect(await TestBed.inject(Router).navigateByUrl('/equipments')).toBe(false);
    expect(editor().form.controls.name.value).toBe(' Pompe 日本 '); editor().form.patchValue({ name: '', code: '', equipment_type: '' });
    confirm.mockClear(); expect(component.canLeave()).toBe(true); expect(confirm).not.toHaveBeenCalled();
    fill(); confirm.mockReturnValue(true); expect(component.canLeave()).toBe(true);
  });
  it('protects beforeunload on changes or an outstanding POST and releases after success', async () => {
    await ready(); const event = { preventDefault: vi.fn(), returnValue: undefined as unknown } as unknown as BeforeUnloadEvent;
    component.protectUnload(event); expect(event.preventDefault).not.toHaveBeenCalled(); fill(); component.protectUnload(event); expect(event.preventDefault).toHaveBeenCalled();
    await submit(); const req = post(); expect(component.canLeave()).toBe(false); req.flush(equipment); await settle(); await detail();
    const after = { preventDefault: vi.fn(), returnValue: undefined } as unknown as BeforeUnloadEvent; component.protectUnload(after); expect(after.preventDefault).not.toHaveBeenCalled();
  });
  it('destroys pending reference subscriptions on leaving a clean creation page', async () => {
    await open('/equipments/new?company_id=7&site_id=9'); const oldCatalog = read('companies'), oldCompany = read('companies/7');
    harness.fixture.destroy(); expect(oldCatalog.cancelled).toBe(true); expect(oldCompany.cancelled).toBe(true);
  });
});
