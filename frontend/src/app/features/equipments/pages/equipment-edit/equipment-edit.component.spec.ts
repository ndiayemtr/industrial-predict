import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbToastrService } from '@nebular/theme';
import { EquipmentRead } from '../../../../core/models/reference-data.model';
import { EQUIPMENT_ROUTES } from '../../equipments.routes';
import { EquipmentEditComponent } from './equipment-edit.component';

const equipment: EquipmentRead = { id: 87, site_id: 9, name: ' Pompe 日本 ', code: ' ÉQ-Test ', equipment_type: ' Type Libre ',
  status: 'maintenance', criticality: 'critical', description: '  Texte 日本\n ligne  ',
  created_at: '2026-08-31T14:58:20', updated_at: '2026-10-16T13:51:15+02:00' };
const site = { id: 9, company_id: 7, name: 'Site réel', code: 'SITE', description: null, created_at: '', updated_at: '' };
const company = { ...site, id: 7, name: 'Entreprise réelle', code: 'ENT' };

describe('Equipment edit - isolated HTTP writes and real parent chain', () => {
  let http: HttpTestingController;
  let harness: RouterTestingHarness;
  let component: EquipmentEditComponent;
  const toastr = { success: vi.fn() };
  const root = () => harness.routeNativeElement!;
  const read = (resource: string) => http.expectOne(req => req.url === `/api/v1/${resource}` && req.method === 'GET');
  const patch = () => http.expectOne(req => req.url === '/api/v1/equipments/87' && req.method === 'PATCH');
  const editor = () => component.editor()!;
  beforeEach(() => {
    toastr.success.mockClear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      { provide: NbToastrService, useValue: toastr }, provideRouter([{ path: 'equipments', children: EQUIPMENT_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => {
    try {
      http.expectNone(req => req.method === 'POST' || req.method === 'DELETE');
      http.expectNone(req => /health-score|rul|predictions|recommendations|sensors|measurements|maintenances/.test(req.url));
      http.verify();
    } finally { vi.restoreAllMocks(); }
  });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/equipments/87/edit') {
    harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, EquipmentEditComponent); await settle();
  }
  async function ready(url = '/equipments/87/edit', original = equipment) {
    await open(url); read('equipments/87').flush(original); read('sites/9').flush(site); read('companies/7').flush(company); await settle();
  }
  async function submit() { root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle(); }
  async function detail() { read('equipments/87').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); await settle(); }

  it('loads the real chain independently of list context, with read-only parents and dates outside FormGroup', async () => {
    await ready('/equipments/87/edit?company_id=99&site_id=88&status=operational&criticality=low&search=Pompe&page=3&page_size=50');
    expect(editor().form.getRawValue()).toMatchObject({ name: equipment.name, code: equipment.code, equipment_type: equipment.equipment_type,
      description: equipment.description, status: 'maintenance', criticality: 'critical' });
    expect(root().querySelector('#equipment-company_id')).toBeNull(); expect(root().querySelector('#equipment-site_id')).toBeNull();
    expect(editor().form.controls.company_id.disabled).toBe(true); expect(editor().form.controls.site_id.disabled).toBe(true);
    expect(root().querySelector('.readonly-parents')?.textContent).toContain('Entreprise réelle - ENT');
    expect(root().querySelector('.readonly-parents')?.textContent).toContain('Site réel - SITE');
    const tracking = root().querySelector('.tracking-information')!;
    const fields = root().querySelector('form fieldset')!;
    const actions = root().querySelector('form .actions')!;
    expect(fields.compareDocumentPosition(tracking) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tracking.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tracking.querySelector('input,select,textarea,button,[formControlName]')).toBeNull();
    expect(root().querySelector('.tracking-information')?.textContent).toContain('31/08/2026 à 14:58');
    expect(root().querySelector('.tracking-information')?.textContent).toContain('16/10/2026 à 11:51 UTC');
    expect(editor().form.contains('created_at')).toBe(false); expect(editor().form.contains('updated_at')).toBe(false);
    expect(root().querySelectorAll('h1')).toHaveLength(1);
    expect(component.listQuery()).toMatchObject({ company_id: 99, site_id: 88, search: 'Pompe', page: 3, page_size: 50, status: 'operational', criticality: 'low' });
    http.expectNone(() => true);
  });
  it('does not PATCH unchanged or restored values, including description and enums', async () => {
    await ready(); await submit(); expect(component.notice()).toContain('Aucune modification');
    editor().form.patchValue({ name: 'Changed', status: 'operational', criticality: 'low', description: '' });
    editor().form.patchValue({ name: equipment.name, status: equipment.status, criticality: equipment.criticality, description: equipment.description });
    await submit(); expect(component.canLeave()).toBe(true); http.expectNone(() => true);
  });
  it('sends only raw changed business fields, never parent IDs or dates, even after structural parent tampering', async () => {
    await ready(); editor().form.patchValue({ name: '  Pompe Éditée 日本  ', status: 'out_of_service', criticality: 'high', company_id: 999, site_id: 555 });
    await submit(); const req = patch();
    expect(req.request.body).toEqual({ name: '  Pompe Éditée 日本  ', status: 'out_of_service', criticality: 'high' });
    expect(JSON.parse(req.request.serializeBody() as string)).toEqual(req.request.body);
  });
  it.each(['', null, ' Texte\nUnicode 日本 '])('distinguishes explicit description %s from unchanged omission', async description => {
    await ready(); editor().form.controls.description.setValue(description); await submit();
    expect(patch().request.body).toEqual({ description });
  });
  it('omits unchanged null description and accepts a manual empty string as a change', async () => {
    await ready('/equipments/87/edit', { ...equipment, description: null });
    editor().form.controls.code.setValue(' Nouveau code '); await submit(); const req = patch(); expect(req.request.body).toEqual({ code: ' Nouveau code ' });
    req.flush({}, { status: 409, statusText: 'Conflict' }); await settle();
    editor().form.controls.code.setValue(equipment.code); editor().form.controls.description.setValue(''); await submit(); expect(patch().request.body).toEqual({ description: '' });
  });
  it('preserves unchanged legacy text rather than normalizing or resubmitting it', async () => {
    const legacy = { ...equipment, name: ' '.repeat(160), code: '😀'.repeat(110), equipment_type: ' '.repeat(110) };
    await ready('/equipments/87/edit', legacy); editor().form.controls.status.setValue('operational'); await submit();
    expect(patch().request.body).toEqual({ status: 'operational' });
  });
  it('blocks double submission and saving navigation, then confirms and notifies once after navigation', async () => {
    await ready('/equipments/87/edit?company_id=99&site_id=88&page=3&page_size=50&search=Pompe&status=operational&criticality=low');
    editor().form.controls.name.setValue('Nouveau nom'); await submit(); const req = patch();
    await submit(); component.save(); http.expectNone(() => true); expect(component.canLeave()).toBe(false);
    expect(await TestBed.inject(Router).navigateByUrl('/equipments')).toBe(false);
    expect(root().querySelector('fieldset')?.disabled).toBe(true); expect(toastr.success).not.toHaveBeenCalled();
    req.flush({ ...equipment, name: 'Nouveau nom' }); await settle();
    expect(TestBed.inject(Router).url).toBe('/equipments/87?company_id=99&site_id=88&page=3&page_size=50&search=Pompe&status=operational&criticality=low');
    expect(root().querySelector('.update-confirmation')?.textContent).toBe('Équipement modifié avec succès.');
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Équipement modifié avec succès.', '');
    await detail(); expect(root().querySelector('.update-confirmation')?.getAttribute('role')).toBe('status');
    expect(toastr.success).toHaveBeenCalledTimes(1);
  });
  it.each(['false', 'reject'])('recovers navigation %s after PATCH without another write or premature toast', async outcome => {
    await ready(); editor().form.controls.name.setValue('Updated');
    const navigation = vi.spyOn(TestBed.inject(Router), 'navigate');
    if (outcome === 'false') navigation.mockResolvedValue(false); else navigation.mockRejectedValue(new Error('Navigation failed'));
    await submit(); patch().flush({ ...equipment, name: 'Updated' }); await settle();
    expect(component.state()).toBe('success'); expect(component.message()).toContain('lien de récupération');
    expect(root().querySelector('fieldset')?.disabled).toBe(true); expect(toastr.success).not.toHaveBeenCalled();
    await submit(); http.expectNone(() => true); navigation.mockRestore();
    root().querySelector<HTMLAnchorElement>('a[href^="/equipments/87?"]')!.click(); await settle(); await detail();
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Équipement modifié avec succès.', '');
    expect(root().querySelector('.update-confirmation')).not.toBeNull();
  });
  it.each([0, 404, 409, 422, 401, 403, 500, 503])('retains draft after PATCH error %s without auto retry or unsafe server detail', async status => {
    await ready(); editor().form.controls.name.setValue('Draft'); await submit(); const req = patch();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({ detail: '<script>PRIVATE_SERVER_DETAIL</script>' }, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toBe('error'); expect(editor().form.controls.name.value).toBe('Draft');
    expect(root().textContent).not.toContain('PRIVATE_SERVER_DETAIL'); expect(toastr.success).not.toHaveBeenCalled();
    if (status === 409) { expect(component.fieldErrors()).toEqual({}); expect(component.message()).toContain('cause exacte'); }
    if (status === 404) expect(component.message()).toContain('aucune recréation automatique');
    if (status === 0 || status >= 500) {
      expect(component.uncertain()).toBe(true); await submit(); component.save(); http.expectNone(() => true);
      component.acknowledgeVerification(); await settle(); http.expectNone(() => true); await submit(); expect(patch().request.body).toEqual({ name: 'Draft' });
    }
    http.expectNone(() => true);
  });
  it('maps only allowed 422 body fields, focuses the first invalid field and keeps safe local messages', async () => {
    await ready(); editor().form.controls.name.setValue('Draft'); await submit();
    patch().flush({ detail: [
      { loc: ['body', 'code'], msg: '<b>RAW_ERROR</b>' }, { loc: ['body', 'name'], msg: 'RAW_ERROR' },
      { loc: ['body', 'site_id'], msg: 'RAW_ERROR' }, { loc: ['body', 'company_id'], msg: 'RAW_ERROR' },
      { loc: ['query', 'status'], msg: 'RAW_ERROR' }, { loc: ['body', 'unknown'], msg: 'RAW_ERROR' }
    ] }, { status: 422, statusText: 'Invalid' }); await settle();
    expect(Object.keys(component.fieldErrors()).sort()).toEqual(['code', 'name']);
    expect(root().textContent).not.toContain('RAW_ERROR'); expect(document.activeElement?.id).toBe('equipment-name');
    expect(root().querySelector('#equipment-name')?.getAttribute('aria-invalid')).toBe('true');
  });
  it.each(['0', '-1', 'abc', '1.2', '1e2', '9007199254740992'])('rejects invalid route id %s before HTTP', async id => {
    await open(`/equipments/${id}/edit`); expect(component.state()).toBe('load-error'); expect(root().textContent).toContain('Identifiant invalide');
    component.retryLoad(); expect(component.editor()).toBeUndefined(); http.expectNone(() => true);
  });
  it.each([0, 404, 500])('handles GET Equipment error %s and retries only transient GET failures', async status => {
    await open(); const req = read('equipments/87');
    if (!status) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' }); await settle();
    expect(component.state()).toBe('load-error'); component.retryLoad();
    if (status === 0 || status >= 500) { read('equipments/87').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); await settle(); }
    else expect(root().textContent).toContain('404');
    http.expectNone(() => true);
  });
  it.each(['site', 'company'])('blocks unavailable %s and preserves edits across reference-only recovery', async scope => {
    await open(); read('equipments/87').flush(equipment); await settle(); editor().form.controls.name.setValue('Draft');
    if (scope === 'site') read('sites/9').flush({}, { status: 500, statusText: 'Error' });
    else { read('sites/9').flush(site); read('companies/7').flush({}, { status: 500, statusText: 'Error' }); }
    await settle(); expect(component.referenceState()).toBe('error'); await submit(); component.save(); http.expectNone(() => true);
    component.retryReferences(); read('sites/9').flush(site); read('companies/7').flush(company); await settle();
    expect(editor().form.controls.name.value).toBe('Draft'); await submit(); expect(patch().request.body).toEqual({ name: 'Draft' });
  });
  it.each(['site', 'company'])('does not accept a mismatched %s reference or fall back to URL context', async scope => {
    await open('/equipments/87/edit?company_id=99&site_id=88'); read('equipments/87').flush(equipment);
    if (scope === 'site') read('sites/9').flush({ ...site, id: 88 });
    else { read('sites/9').flush(site); read('companies/7').flush({ ...company, id: 99 }); }
    await settle(); expect(component.referenceState()).toBe('error'); expect(component.referenceError().retryable).toBe(false);
    component.retryReferences(); http.expectNone(() => true);
  });
  it.each(['site', 'company'])('blocks a missing %s without offering a transfer or automatic retry', async scope => {
    await open(); read('equipments/87').flush(equipment);
    if (scope === 'site') read('sites/9').flush({}, { status: 404, statusText: 'Not found' });
    else { read('sites/9').flush(site); read('companies/7').flush({}, { status: 404, statusText: 'Not found' }); }
    await settle(); expect(component.referenceState()).toBe('error'); expect(component.referenceError().retryable).toBe(false);
    expect(root().querySelector('#equipment-site_id')).toBeNull(); component.retryReferences(); component.save(); http.expectNone(() => true);
  });
  it('rejects an Equipment response for another identifier', async () => {
    await open(); read('equipments/87').flush({ ...equipment, id: 88 }); await settle();
    expect(component.state()).toBe('load-error'); expect(component.original()).toBeNull(); http.expectNone(() => true);
  });
  it('cancels an obsolete company read and resets the form for the next real equipment', async () => {
    await open(); read('equipments/87').flush(equipment); read('sites/9').flush(site); const old = read('companies/7');
    component = await harness.navigateByUrl('/equipments/88/edit', EquipmentEditComponent); await settle(); expect(old.cancelled).toBe(true);
    read('equipments/88').flush({ ...equipment, id: 88, name: 'Next' }); read('sites/9').flush(site); read('companies/7').flush(company); await settle();
    expect(editor().form.controls.name.value).toBe('Next'); expect(editor().hasChanges()).toBe(false);
  });
  it('does not notify a different equipment when a previous navigation settles late', async () => {
    await ready(); editor().form.controls.name.setValue('Draft');
    let finish!: (value: boolean) => void;
    const navigation = vi.spyOn(TestBed.inject(Router), 'navigate').mockImplementation(() => new Promise<boolean>(resolve => { finish = resolve; }));
    await submit(); patch().flush({ ...equipment, name: 'Draft' }); await settle();
    component = await harness.navigateByUrl('/equipments/88/edit', EquipmentEditComponent); await settle();
    read('equipments/88').flush({ ...equipment, id: 88 }); read('sites/9').flush(site); read('companies/7').flush(company); await settle();
    finish(true); await settle(); expect(toastr.success).not.toHaveBeenCalled(); expect(component.original()?.id).toBe(88);
    navigation.mockRestore();
  });
  it('cancels stale equipment and parent reads when the identifier changes', async () => {
    await open(); const old = read('equipments/87');
    component = await harness.navigateByUrl('/equipments/88/edit', EquipmentEditComponent); await settle(); expect(old.cancelled).toBe(true);
    read('equipments/88').flush({ ...equipment, id: 88 }); const oldSite = read('sites/9');
    component = await harness.navigateByUrl('/equipments/89/edit', EquipmentEditComponent); await settle(); expect(oldSite.cancelled).toBe(true);
    read('equipments/89').flush({ ...equipment, id: 89 }); read('sites/9').flush(site); read('companies/7').flush(company); await settle();
    expect(component.original()?.id).toBe(89); expect(editor().hasChanges()).toBe(false);
  });
  it('cancels a pending PATCH on destruction without a toast or follow-up request', async () => {
    await ready(); editor().form.controls.name.setValue('Draft'); await submit(); const req = patch();
    harness.fixture.destroy(); expect(req.cancelled).toBe(true); expect(toastr.success).not.toHaveBeenCalled(); http.expectNone(() => true);
  });
  it('guards cancel/navigation, permits restored values and protects beforeunload', async () => {
    await ready(); const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    expect(component.canLeave()).toBe(true); expect(confirm).not.toHaveBeenCalled();
    editor().form.controls.name.setValue('Draft');
    const event = { preventDefault: vi.fn(), returnValue: undefined as unknown } as unknown as BeforeUnloadEvent;
    component.protectUnload(event); expect(event.preventDefault).toHaveBeenCalled();
    component.cancel(); await settle(); expect(TestBed.inject(Router).url).toBe('/equipments/87/edit');
    expect(editor().form.controls.name.value).toBe('Draft'); confirm.mockClear(); editor().form.controls.name.setValue(equipment.name);
    expect(component.canLeave()).toBe(true); expect(confirm).not.toHaveBeenCalled();
    editor().form.controls.name.setValue('Draft'); confirm.mockReturnValue(true); component.cancel(); await settle(); await detail();
    expect(TestBed.inject(Router).url).toBe('/equipments/87?page=1&page_size=20'); expect(toastr.success).not.toHaveBeenCalled();
  });
  it('validates raw changed text with Unicode limits and focuses the first invalid field', async () => {
    await ready(); editor().form.controls.name.setValue(' '.repeat(2) + '😀'.repeat(149)); await submit();
    expect(editor().form.controls.name.hasError('maxlength')).toBe(true); expect(document.activeElement?.id).toBe('equipment-name');
    editor().form.controls.name.setValue('😀'.repeat(150)); await submit(); expect(patch().request.body).toEqual({ name: '😀'.repeat(150) });
  });
  it('sanitizes return parameters without using them as real parent data', async () => {
    await ready('/equipments/87/edit?company_id=-1&site_id=bad&page=0&page_size=101&search=%20%20&status=bad&criticality=urgent&returnUrl=https://example.com');
    expect(component.listQuery()).toEqual({ company_id: undefined, site_id: undefined, page: 1, page_size: 20, search: undefined, status: undefined, criticality: undefined });
    expect(component.company()?.id).toBe(7); expect(component.site()?.id).toBe(9);
  });
});
