import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbToastrService } from '@nebular/theme';
import { SENSOR_ROUTES } from '../../sensors.routes';
import { SensorCreateComponent } from './sensor-create.component';
const company = { id: 7, name: 'Entreprise test', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7, name: 'Site test' };
const equipment = { ...company, id: 12, site_id: 9, name: 'Pompe', equipment_type: 'pump', status: 'operational', criticality: 'medium' };
const sensor = { ...company, id: 17, equipment_id: 12, name: 'Capteur', code: 'SEN', sensor_type: 'temperature', unit: '°C', status: 'active' };
const catalog = { items: [company], total: 1, page: 1, page_size: 50, pages: 1 };
const context = 'company_id=7&site_id=9&equipment_id=12';
describe('Sensor creation with isolated HTTP', () => {
  let http: HttpTestingController, harness: RouterTestingHarness, component: SensorCreateComponent;
  const toastr = { success: vi.fn() };
  const root = () => harness.routeNativeElement!;
  const read = (path: string) => http.expectOne(req => req.url === '/api/v1/' + path && req.method === 'GET');
  const post = () => http.expectOne(req => req.url === '/api/v1/sensors' && req.method === 'POST');
  const editor = () => component.editor()!;
  beforeEach(() => {
    toastr.success.mockClear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      { provide: NbToastrService, useValue: toastr }, provideRouter([{ path: 'sensors', children: SENSOR_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try { http.expectNone(req => req.method === 'DELETE' || req.method === 'PATCH' || /measurements|predictions/.test(req.url)); http.verify(); }
    finally { TestBed.resetTestingModule(); vi.restoreAllMocks(); } });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/sensors/new') { harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, SensorCreateComponent); await settle(); }
  function parents() { read('companies/7').flush(company); read('sites/9').flush(site); read('equipments/12').flush(equipment); }
  function catalogs() { read('sites').flush({ ...catalog, items: [site] }); read('equipments').flush({ ...catalog, items: [equipment] }); }
  async function ready(url = '/sensors/new?' + context) { await open(url); read('companies').flush(catalog); parents(); catalogs(); await settle(); }
  function fill() { editor().form.patchValue({ name: ' Capteur 日本 ', code: ' SEN ', sensor_type: ' temperature ', unit: ' °C ' }); }
  async function submit() { editor().submit(); await settle(); }
  async function detail() { read('sensors/17').flush(sensor); read('equipments/12').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); await settle(); }

  it.each(['', '?company_id=7', '?site_id=9', '?equipment_id=12', '?company_id=0&site_id=9&equipment_id=12', '?company_id=7&site_id=9&equipment_id=abc'])('leaves all parents unselected with incomplete context %s', async query => {
    await open('/sensors/new' + query); read('companies').flush(catalog); await settle();
    expect(editor().form.getRawValue()).toMatchObject({ company_id: null, site_id: null, equipment_id: null, status: 'active' });
    expect(editor().form.controls.site_id.disabled).toBe(true); expect(editor().form.controls.equipment_id.disabled).toBe(true);
    fill(); await submit(); http.expectNone(() => true); expect(document.activeElement?.id).toBe('sensor-company_id');
  });
  it('prefills only the fully verified chain and keeps business drafts untouched', async () => {
    await open('/sensors/new?' + context); read('companies').flush({ ...catalog, items: [], pages: 2, total: 51 });
    editor().form.controls.name.setValue('Brouillon'); read('companies/7').flush(company); read('sites/9').flush(site);
    expect(editor().form.controls.equipment_id.value).toBeNull(); read('equipments/12').flush(equipment); catalogs(); await settle();
    expect(editor().form.getRawValue()).toMatchObject({ company_id: 7, site_id: 9, equipment_id: 12, name: 'Brouillon' });
    expect(component.references.companyOptions()).toEqual([{ id: 7, label: 'Entreprise test - ENT' }]);
  });
  it('does not count verified prefill as an unsaved change', async () => { await ready(); expect(editor().hasChanges()).toBe(false); expect(component.canLeave()).toBe(true); });
  it.each(['site', 'equipment', 'companyIdentity', 'siteIdentity', 'equipmentIdentity'])('blocks contradictory %s context without replacing parents', async stage => {
    await open('/sensors/new?' + context); read('companies').flush(catalog);
    read('companies/7').flush(stage === 'companyIdentity' ? { ...company, id: 8 } : company);
    if (stage !== 'companyIdentity') {
      read('sites/9').flush(stage === 'siteIdentity' ? { ...site, id: 10 } : stage === 'site' ? { ...site, company_id: 8 } : site);
      if (stage !== 'siteIdentity') read('equipments/12').flush(stage === 'equipmentIdentity' ? { ...equipment, id: 13 } : stage === 'equipment' ? { ...equipment, site_id: 10 } : equipment);
      read('sites').flush({ ...catalog, items: [site] });
    }
    await settle(); expect(component.references.state()).toBe('error'); fill(); await submit();
    expect(editor().form.controls.company_id.value).toBeNull(); http.expectNone(() => true);
  });
  it('requires explicit sequential choices and resets descendants when a parent changes', async () => {
    await open(); read('companies').flush(catalog); await settle();
    editor().form.controls.company_id.setValue(7); read('companies/7').flush(company); read('sites').flush({ ...catalog, items: [site] }); await settle();
    expect(editor().form.controls.site_id.enabled).toBe(true); expect(editor().form.controls.site_id.value).toBeNull();
    editor().form.controls.site_id.setValue(9); read('companies/7').flush(company); read('sites/9').flush(site); read('equipments').flush({ ...catalog, items: [equipment] }); await settle();
    expect(editor().form.controls.equipment_id.enabled).toBe(true); expect(editor().form.controls.equipment_id.value).toBeNull();
    editor().form.controls.equipment_id.setValue(12); parents(); await settle(); fill();
    editor().form.controls.company_id.setValue(null); await settle();
    expect(editor().form.getRawValue()).toMatchObject({ site_id: null, equipment_id: null, name: ' Capteur 日本 ' }); await submit(); http.expectNone(() => true);
  });
  it('cancels obsolete reference and catalog requests on parent change', async () => {
    await open('/sensors/new?' + context); read('companies').flush(catalog); const oldCompany = read('companies/7');
    editor().form.controls.company_id.setValue(8); expect(oldCompany.cancelled).toBe(true);
    read('companies/8').flush({ ...company, id: 8 }); const oldSites = read('sites'); await settle();
    editor().form.controls.company_id.setValue(7); read('companies/7').flush(company); expect(oldSites.cancelled).toBe(true);
    read('sites').flush({ ...catalog, items: [site] }); await settle(); expect(component.references.company()?.id).toBe(7);
  });
  it('loads all catalogs by pages, deduplicates and retains items after a retryable page failure', async () => {
    await open('/sensors/new?' + context); read('companies').flush({ ...catalog, total: 51, pages: 2 }); parents();
    read('sites').flush({ ...catalog, items: [site], total: 51, pages: 2 }); read('equipments').flush({ ...catalog, items: [equipment], total: 51, pages: 2 }); await settle();
    component.references.moreCompanies(); let req = read('companies'); expect(req.request.params.get('page')).toBe('2'); req.flush({ ...catalog, items: [company, { ...company, id: 8 }], page: 2, total: 51, pages: 2 });
    component.references.moreSites(); req = read('sites'); expect(req.request.params.get('company_id')).toBe('7'); req.flush({ ...catalog, items: [site, { ...site, id: 10 }], page: 2, total: 51, pages: 2 });
    component.references.moreEquipments(); req = read('equipments'); expect(req.request.params.get('site_id')).toBe('9'); req.flush({}, { status: 500, statusText: 'Error' });
    expect(component.references.equipments().items).toEqual([equipment]); component.references.retryEquipments(); req = read('equipments'); expect(req.request.params.get('page')).toBe('2');
    req.flush({ ...catalog, items: [equipment, { ...equipment, id: 13 }], page: 2, total: 51, pages: 2 }); await settle();
    expect(component.references.companyOptions()).toHaveLength(2); expect(component.references.siteOptions()).toHaveLength(2); expect(component.references.equipmentOptions()).toHaveLength(2);
  });
  it.each([undefined, '', null, '  Ligne 1\n日本  '])('serializes description %s separately from parent UI values', async description => {
    await ready(); fill(); if (description !== undefined) { editor().form.controls.description.setValue(description); editor().form.controls.description.markAsDirty(); }
    await submit(); const req = post(); expect(req.request.body).toEqual({ equipment_id: 12, name: 'Capteur 日本', code: 'SEN', sensor_type: 'temperature', unit: '°C', status: 'active', ...(description !== undefined ? { description } : {}) });
    req.flush(sensor, { status: 201, statusText: 'Created' }); await settle(); await detail();
    expect(root().querySelectorAll('.creation-confirmation')).toHaveLength(1); expect(toastr.success).toHaveBeenCalledTimes(1);
  });
  it.each(['°C', 'mm/s', 'bar'])('preserves the unit %s and explicit inactive status', async unit => {
    await ready(); fill(); editor().form.patchValue({ unit, status: 'inactive' }); await submit(); const req = post(); expect(req.request.body.unit).toBe(unit); expect(req.request.body.status).toBe('inactive');
    req.flush({}, { status: 409, statusText: 'Conflict' }); await settle();
  });
  it.each([0, 404, 409, 422, 500])('keeps user entries on HTTP %s, blocks uncertain retries and does not classify every 409 as Code', async status => {
    await ready(); fill(); await submit(); const req = post();
    if (status === 0) req.error(new ProgressEvent('error')); else req.flush({ detail: [{ loc: ['body', 'unit'], msg: '<script>unsafe</script>' }] }, { status, statusText: 'Error' });
    await settle(); expect(editor().form.controls.name.value).toBe(' Capteur 日本 '); expect(component.state()).toBe('error');
    expect(component.uncertain()).toBe(status === 0 || status >= 500);
    if (status === 409) expect(component.fieldErrors()['code']).toBeUndefined();
    if (status === 422) { expect(component.fieldErrors()['unit']).toBeTruthy(); expect(root().textContent).not.toContain('<script>'); }
    if (status === 404) expect(component.references.state()).toBe('error');
    if (status === 0 || status >= 500) { await submit(); http.expectNone(() => true); component.acknowledgeVerification(); await settle(); await submit(); post().flush({}, { status: 409, statusText: 'Conflict' }); }
  });
  it('blocks double submission and abandonment during the write', async () => {
    await ready(); fill(); await submit(); await submit(); const req = post(); expect(component.canLeave()).toBe(false);
    const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
    req.flush({}, { status: 409, statusText: 'Conflict' }); await settle(); http.expectNone(() => true);
  });
  it.each([false, 'throw'])('keeps success and a recovery link if navigation returns %s, without reposting', async result => {
    await ready(); fill(); const router = TestBed.inject(Router), spy = vi.spyOn(router, 'navigate');
    if (result === false) spy.mockResolvedValue(false); else spy.mockRejectedValue(new Error('Navigation failed'));
    await submit(); post().flush(sensor, { status: 201, statusText: 'Created' }); await settle();
    expect(component.state()).toBe('success'); expect(root().querySelector('.created-link')?.getAttribute('href')).toBe('/sensors/17?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20');
    await submit(); http.expectNone(() => true); expect(component.canLeave()).toBe(true); expect(toastr.success).not.toHaveBeenCalled();
    spy.mockResolvedValue(true); component.recover(new MouseEvent('click', { cancelable: true })); await settle(); expect(toastr.success).toHaveBeenCalledTimes(1);
    component.recover(new MouseEvent('click', { cancelable: true })); await settle(); expect(toastr.success).toHaveBeenCalledTimes(1); http.expectNone(() => true);
  });
  it('rejects an invalid success identity as an uncertain write', async () => {
    await ready(); fill(); await submit(); post().flush({ ...sensor, id: 0 }, { status: 201, statusText: 'Created' }); await settle();
    expect(component.created()).toBeNull(); expect(component.uncertain()).toBe(true); expect(toastr.success).not.toHaveBeenCalled(); http.expectNone(() => true);
  });
  it('keeps the original return snapshot for cancellation and guards unsaved changes', async () => {
    await ready('/sensors/new?' + context + '&return_company_id=8&return_site_id=10&return_equipment_id=13&return_page=3&return_page_size=50&return_search=OLD&return_status=inactive');
    fill(); const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    component.cancel(); await settle(); expect(confirm).toHaveBeenCalledTimes(1); expect(root().querySelector('app-sensor-form')).not.toBeNull();
    expect(component.listQuery()).toEqual({ company_id: 8, site_id: 10, equipment_id: 13, page: 3, page_size: 50, search: 'OLD', status: 'inactive' });
    confirm.mockReturnValue(true); expect(component.canLeave()).toBe(true);
  });
  it.each([0, 404, 500])('handles a failed actual Equipment reference %s and retries reads only when transient', async status => {
    await open('/sensors/new?' + context); read('companies').flush(catalog); read('companies/7').flush(company); read('sites/9').flush(site);
    const req = read('equipments/12'); if (status === 0) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' });
    read('sites').flush({ ...catalog, items: [site] }); await settle(); fill(); await submit();
    expect(component.references.state()).toBe('error'); expect(component.references.canRetry()).toBe(status === 0 || status >= 500);
    expect(editor().form.controls.equipment_id.value).toBeNull(); http.expectNone(() => true);
    if (status === 0 || status >= 500) { component.verifyReferences(); parents(); read('equipments').flush({ ...catalog, items: [equipment] }); await settle(); expect(editor().form.controls.equipment_id.value).toBe(12); }
  });
  it('revalidates a stale parent after POST 404 before allowing another write', async () => {
    await ready(); fill(); await submit(); post().flush({}, { status: 404, statusText: 'Not found' }); await settle();
    await submit(); http.expectNone(() => true); component.verifyReferences(); parents(); await settle(); await submit();
    post().flush({}, { status: 409, statusText: 'Conflict' }); await settle();
  });
  it('cancels to the preserved list context without a dirty confirmation for pristine prefill', async () => {
    await ready('/sensors/new?' + context + '&page=2&page_size=50&status=inactive&search=TEMP');
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false); component.cancel(); await settle();
    read('companies').flush(catalog); read('equipments/12').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); await settle(); catalogs();
    const req = read('sensors'); expect(req.request.params.get('page')).toBe('2'); expect(req.request.params.get('search')).toBe('TEMP');
    req.flush({ items: [], total: 0, page: 2, page_size: 50, pages: 0 }); await settle(); expect(confirm).not.toHaveBeenCalled();
  });
  it('uses a coherent new list context after creation from a different return scope', async () => {
    await ready('/sensors/new?' + context + '&return_company_id=8&return_site_id=10&return_equipment_id=13&return_page=4&return_search=OLD');
    fill(); await submit(); post().flush(sensor, { status: 201, statusText: 'Created' }); await settle(); await detail();
    expect(TestBed.inject(Router).url).toBe('/sensors/17?company_id=7&site_id=9&equipment_id=12&page=1&page_size=20');
  });
  it('retains a matching return snapshot after success', async () => {
    await ready('/sensors/new?' + context + '&return_company_id=7&return_site_id=9&return_equipment_id=12&return_page=3&return_page_size=50&return_search=OLD&return_status=inactive');
    fill(); await submit(); post().flush(sensor, { status: 201, statusText: 'Created' }); await settle(); await detail();
    expect(TestBed.inject(Router).url).toBe('/sensors/17?company_id=7&site_id=9&equipment_id=12&page=3&page_size=50&search=OLD&status=inactive');
  });
  it('cancels pending parent reads on destruction', async () => {
    await open('/sensors/new?' + context); read('companies').flush(catalog); const pending = read('companies/7'); harness.fixture.destroy(); expect(pending.cancelled).toBe(true);
  });
  it('warns on beforeunload only for actual edits', async () => {
    await ready(); let event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(false);
    fill(); event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
  });
});
