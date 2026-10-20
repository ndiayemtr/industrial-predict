import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbToastrService } from '@nebular/theme';
import { SensorRead } from '../../models/sensor.model';
import { SENSOR_ROUTES } from '../../sensors.routes';
import { SensorEditComponent } from './sensor-edit.component';

const sensor: SensorRead = { id: 17, equipment_id: 12, name: ' Capteur 日本 ', code: ' SEN ', sensor_type: 'temperature', unit: '°C',
  status: 'active', description: ' Texte\n日本 ', created_at: '2026-08-31T14:58:20', updated_at: '2026-10-16T13:51:15+02:00' };
const company = { id: 7, name: 'Entreprise réelle', code: 'ENT', description: null, created_at: '', updated_at: '' };
const site = { ...company, id: 9, company_id: 7, name: 'Site réel' };
const equipment = { ...company, id: 12, site_id: 9, name: 'Pompe', equipment_type: 'pump', status: 'operational', criticality: 'medium' };
const context = 'company_id=99&site_id=88&equipment_id=77&page=3&page_size=50&search=Pompe&status=inactive';

describe('Sensor edit with isolated HTTP and real parents', () => {
  let http: HttpTestingController, harness: RouterTestingHarness, component: SensorEditComponent;
  const toastr = { success: vi.fn() };
  const root = () => harness.routeNativeElement!;
  const editor = () => component.editor()!;
  const read = (path: string) => http.expectOne(req => req.url === '/api/v1/' + path && req.method === 'GET');
  const patch = () => http.expectOne(req => req.url === '/api/v1/sensors/17' && req.method === 'PATCH');
  beforeEach(() => {
    toastr.success.mockClear();
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      { provide: NbToastrService, useValue: toastr }, provideRouter([{ path: 'sensors', children: SENSOR_ROUTES }])] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { try {
    http.expectNone(req => req.method === 'DELETE' || req.method === 'POST' || /measurements|predictions/.test(req.url)); http.verify();
  } finally { TestBed.resetTestingModule(); vi.restoreAllMocks(); } });
  async function settle() { harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges(); }
  async function open(url = '/sensors/17/edit') { harness = await RouterTestingHarness.create(); component = await harness.navigateByUrl(url, SensorEditComponent); await settle(); }
  function parents() { read('equipments/12').flush(equipment); read('sites/9').flush(site); read('companies/7').flush(company); }
  async function ready(url = '/sensors/17/edit', initial = sensor) { await open(url); read('sensors/17').flush(initial); parents(); await settle(); }
  async function submit() { root().querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); await settle(); }
  async function detail() { read('sensors/17').flush(sensor); parents(); await settle(); }

  it('shows actual immutable references, type, unit and tracking before actions, independent of return context', async () => {
    await ready('/sensors/17/edit?' + context);
    expect(editor().form.getRawValue()).toMatchObject({ name: sensor.name, code: sensor.code, description: sensor.description });
    for (const key of ['company_id', 'site_id', 'equipment_id', 'sensor_type', 'unit'] as const) {
      expect(root().querySelector('#sensor-' + key)).toBeNull(); expect(editor().form.controls[key].disabled).toBe(true);
    }
    expect(root().textContent).toContain('Entreprise réelle - ENT'); expect(root().textContent).toContain('Site réel - ENT');
    expect(root().textContent).toContain('Pompe - ENT'); expect(root().textContent).toContain('temperature'); expect(root().textContent).toContain('°C');
    const tracking = root().querySelector('.tracking-information')!, actions = root().querySelector('.actions')!;
    expect(tracking.compareDocumentPosition(actions) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(tracking.querySelector('input,select,textarea,button')).toBeNull();
    expect(tracking.textContent).toContain('31/08/2026 à 14:58'); expect(tracking.textContent).toContain('16/10/2026 à 11:51 UTC');
    expect(editor().form.contains('created_at')).toBe(false); expect(editor().form.contains('updated_at')).toBe(false);
    expect(component.listQuery()).toMatchObject({ company_id: 99, site_id: 88, equipment_id: 77, page: 3, page_size: 50, search: 'Pompe', status: 'inactive' });
  });
  it('omits all unchanged and restored values, including code, description and status', async () => {
    await ready(); await submit(); expect(component.notice()).toContain('Aucune modification');
    editor().form.patchValue({ name: 'Changed', code: 'Other', status: 'inactive', description: '' });
    editor().form.patchValue({ name: sensor.name, code: sensor.code, status: sensor.status, description: sensor.description });
    await submit(); expect(editor().hasChanges()).toBe(false); expect(component.canLeave()).toBe(true); http.expectNone(() => true);
  });
  it.each(['name', 'code', 'status'] as const)('sends only the changed %s and preserves raw text', async field => {
    await ready(); const value = field === 'status' ? 'inactive' : ' Nouveau 日本 ';
    editor().form.controls[field].setValue(value as never); await submit(); const req = patch();
    expect(req.request.body).toEqual({ [field]: value }); expect(JSON.parse(req.request.serializeBody() as string)).toEqual(req.request.body);
  });
  it('ignores structural tampering with every immutable form field', async () => {
    await ready(); editor().form.patchValue({ company_id: 99, site_id: 88, equipment_id: 77, sensor_type: 'changed', unit: 'other', name: 'Nouveau' });
    await submit(); expect(patch().request.body).toEqual({ name: 'Nouveau' });
  });
  it.each(['', null, ' Texte\n日本 '])('preserves explicit description %s', async description => {
    await ready(); editor().form.controls.description.setValue(description === sensor.description ? description + 'x' : description);
    await submit(); expect(patch().request.body).toEqual({ description: description === sensor.description ? description + 'x' : description });
  });
  it('omits unchanged null description and differentiates manual empty text from explicit removal', async () => {
    await ready('/sensors/17/edit', { ...sensor, description: null });
    editor().form.controls.code.setValue('Libre'); await submit(); const req = patch(); expect(req.request.body).toEqual({ code: 'Libre' });
    req.flush({}, { status: 409, statusText: 'Conflict' }); await settle();
    editor().form.controls.code.setValue(sensor.code); editor().form.controls.description.setValue(''); await submit();
    const empty = patch(); expect(empty.request.body).toEqual({ description: '' }); empty.flush({}, { status: 422, statusText: 'Invalid' }); await settle();
    editor().removeDescription(); await submit(); expect(editor().hasChanges()).toBe(false); http.expectNone(() => true);
  });
  it('maps explicit removal of an existing description to null', async () => { await ready(); editor().removeDescription(); await submit(); expect(patch().request.body).toEqual({ description: null }); });
  it('preserves legacy unchanged text while validating actual changed text without trimming', async () => {
    await ready('/sensors/17/edit', { ...sensor, name: ' '.repeat(160), code: '😀'.repeat(110) });
    editor().form.controls.status.setValue('inactive'); await submit(); expect(patch().request.body).toEqual({ status: 'inactive' });
  });
  it.each(['name', 'code'] as const)('validates changed %s Unicode length and required text', async field => {
    await ready(); const control = editor().form.controls[field], limit = field === 'name' ? 150 : 100;
    for (const value of ['', '  ', ' ' + '😀'.repeat(limit)]) {
      control.setValue(value); await submit(); expect(control.invalid).toBe(true); http.expectNone(() => true); expect(document.activeElement?.id).toBe('sensor-' + field);
    }
    control.setValue('😀'.repeat(limit)); await submit(); expect(patch().request.body).toEqual({ [field]: '😀'.repeat(limit) });
  });
  it('blocks double submission and navigation while saving, then returns to the real detail with one confirmation', async () => {
    await ready('/sensors/17/edit?' + context); editor().form.controls.code.setValue('LIBRE'); await submit(); const req = patch();
    await submit(); component.save(); http.expectNone(() => true); expect(component.canLeave()).toBe(false);
    const unload = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(unload); expect(unload.defaultPrevented).toBe(true);
    expect(await TestBed.inject(Router).navigateByUrl('/sensors')).toBe(false); expect(root().querySelector('fieldset')!.disabled).toBe(true);
    req.flush({ ...sensor, code: 'LIBRE' }, { status: 200, statusText: 'OK' }); await settle();
    expect(TestBed.inject(Router).url).toBe('/sensors/17?' + context); expect(root().textContent).toContain('Capteur modifié avec succès.');
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Capteur modifié avec succès.', ''); await detail(); expect(toastr.success).toHaveBeenCalledTimes(1);
  });
  it.each(['false', 'reject'])('recovers navigation %s without another PATCH', async outcome => {
    await ready(); editor().form.controls.name.setValue('Nouveau');
    const navigation = vi.spyOn(TestBed.inject(Router), 'navigate');
    if (outcome === 'false') navigation.mockResolvedValue(false); else navigation.mockRejectedValue(new Error('Navigation'));
    await submit(); patch().flush({ ...sensor, name: 'Nouveau' }); await settle();
    expect(component.state()).toBe('success'); expect(component.message()).toContain('récupération'); expect(toastr.success).not.toHaveBeenCalled();
    await submit(); http.expectNone(() => true); navigation.mockRestore();
    root().querySelector<HTMLAnchorElement>('a[href^="/sensors/17?"]')!.click(); await settle(); await detail();
    expect(toastr.success).toHaveBeenCalledExactlyOnceWith('Capteur modifié avec succès.', '');
  });
  it.each([0, 404, 409, 422, 401, 403, 500, 503])('preserves input after PATCH error %s without retry or leaking server messages', async status => {
    await ready(); editor().form.controls.code.setValue('CONFLICT'); await submit(); const req = patch();
    if (!status) req.error(new ProgressEvent('error')); else req.flush({ detail: '<script>PRIVATE_DETAIL</script>' }, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toBe('error'); expect(editor().form.controls.code.value).toBe('CONFLICT'); expect(root().textContent).not.toContain('PRIVATE_DETAIL');
    if (status === 409) { expect(component.fieldErrors()).toEqual({}); expect(component.message()).toContain('conflit'); }
    if (status === 404) expect(component.message()).toContain('aucune recréation automatique');
    if (!status || status >= 500) {
      expect(component.uncertain()).toBe(true); await submit(); component.save(); http.expectNone(() => true);
      component.acknowledgeVerification(); await settle(); http.expectNone(() => true); await submit(); expect(patch().request.body).toEqual({ code: 'CONFLICT' });
    }
    expect(toastr.success).not.toHaveBeenCalled(); http.expectNone(() => true);
  });
  it('maps only recognized body 422 errors, ignores immutable fields and focuses the first invalid control', async () => {
    await ready(); editor().form.controls.code.setValue('Nouveau'); await submit();
    patch().flush({ detail: ['name', 'code', 'equipment_id', 'sensor_type', 'unit', 'company_id', 'site_id', 'id', 'created_at'].map(key => ({ loc: ['body', key], msg: 'PRIVATE' }))
      .concat([{ loc: ['query', 'status'], msg: 'PRIVATE' }]) }, { status: 422, statusText: 'Invalid' }); await settle();
    expect(Object.keys(component.fieldErrors()).sort()).toEqual(['code', 'name']); expect(document.activeElement?.id).toBe('sensor-name');
    expect(root().querySelector('#sensor-name')!.getAttribute('aria-invalid')).toBe('true'); expect(root().textContent).not.toContain('PRIVATE');
  });
  it.each(['0', '-1', 'abc', '1.2', '1e2', '9007199254740992'])('rejects invalid id %s without HTTP', async id => {
    await open('/sensors/' + id + '/edit'); expect(component.state()).toBe('load-error'); component.retryLoad(); expect(component.editor()).toBeUndefined(); http.expectNone(() => true);
  });
  it.each([0, 404, 403, 500])('handles Sensor GET %s and retries only transient reads', async status => {
    await open(); const req = read('sensors/17'); if (!status) req.error(new ProgressEvent('error')); else req.flush({}, { status, statusText: 'Error' });
    await settle(); expect(component.state()).toBe('load-error'); component.retryLoad();
    if (!status || status >= 500) { read('sensors/17').flush(sensor); parents(); await settle(); }
    http.expectNone(() => true);
  });
  it('rejects a Sensor response with a different id', async () => { await open(); read('sensors/17').flush({ ...sensor, id: 18 }); await settle(); expect(component.original()).toBeNull(); expect(component.state()).toBe('load-error'); });
  it.each(['equipment', 'site', 'company'] as const)('preserves draft while retrying unavailable %s references only', async scope => {
    await open(); read('sensors/17').flush(sensor); await settle(); editor().form.controls.name.setValue('Brouillon');
    if (scope !== 'equipment') read('equipments/12').flush(equipment); if (scope === 'company') read('sites/9').flush(site);
    read(scope === 'equipment' ? 'equipments/12' : scope === 'site' ? 'sites/9' : 'companies/7').flush({}, { status: 500, statusText: 'Error' });
    await settle(); component.save(); await submit(); http.expectNone(() => true); component.retryReferences(); parents(); await settle();
    expect(editor().form.controls.name.value).toBe('Brouillon'); await submit(); expect(patch().request.body).toEqual({ name: 'Brouillon' });
  });
  it.each(['equipment', 'site', 'company'] as const)('rejects incoherent %s without URL fallback', async scope => {
    await open('/sensors/17/edit?' + context); read('sensors/17').flush(sensor);
    if (scope !== 'equipment') read('equipments/12').flush(equipment); if (scope === 'company') read('sites/9').flush(site);
    read(scope === 'equipment' ? 'equipments/12' : scope === 'site' ? 'sites/9' : 'companies/7').flush({ ...(scope === 'equipment' ? equipment : scope === 'site' ? site : company), id: 999 });
    await settle(); expect(component.referenceState()).toBe('error'); expect(component.original()?.id).toBe(17); component.retryReferences(); component.save(); http.expectNone(() => true);
  });
  it.each([404, 403])('blocks absent or inaccessible parent (%s)', async status => {
    await open(); read('sensors/17').flush(sensor); read('equipments/12').flush({}, { status, statusText: 'Error' }); await settle();
    expect(component.referenceError().retryable).toBe(false); expect(root().querySelector('button[type="submit"]')!.hasAttribute('disabled')).toBe(true);
    component.save(); component.retryReferences(); http.expectNone(() => true);
  });
  it.each([0, -1, 1.5, 9007199254740992])('rejects invalid parent foreign key %s locally', async id => {
    await open(); read('sensors/17').flush({ ...sensor, equipment_id: id }); await settle(); expect(component.referenceState()).toBe('error'); component.save(); http.expectNone(() => true);
  });
  it('cancels stale Sensor and parent reads when the route id changes', async () => {
    await open(); const old = read('sensors/17'); component = await harness.navigateByUrl('/sensors/18/edit', SensorEditComponent); await settle(); expect(old.cancelled).toBe(true);
    read('sensors/18').flush({ ...sensor, id: 18 }); const parent = read('equipments/12');
    component = await harness.navigateByUrl('/sensors/19/edit', SensorEditComponent); await settle(); expect(parent.cancelled).toBe(true);
    read('sensors/19').flush({ ...sensor, id: 19 }); parents(); await settle(); expect(editor().hasChanges()).toBe(false);
  });
  it('cancels pending PATCH on destruction without follow-up or toast', async () => {
    await ready(); editor().form.controls.name.setValue('Draft'); await submit(); const req = patch(); harness.fixture.destroy(); expect(req.cancelled).toBe(true); expect(toastr.success).not.toHaveBeenCalled();
  });
  it('treats an incoherent 200 response as an uncertain write', async () => {
    await ready(); editor().form.controls.name.setValue('Draft'); await submit(); patch().flush({ ...sensor, equipment_id: 99 }); await settle();
    expect(component.uncertain()).toBe(true); expect(component.saved()).toBeNull(); expect(editor().form.controls.name.value).toBe('Draft'); expect(toastr.success).not.toHaveBeenCalled();
  });
  it('guards cancel and beforeunload, permits restored values and retains return context after confirmed abandonment', async () => {
    await ready('/sensors/17/edit?' + context); const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    expect(component.canLeave()).toBe(true); editor().form.controls.name.setValue('Draft');
    const event = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(event); expect(event.defaultPrevented).toBe(true);
    component.cancel(); await settle(); expect(TestBed.inject(Router).url).toContain('/edit?'); expect(confirm).toHaveBeenCalled();
    editor().form.controls.name.setValue(sensor.name); expect(component.canLeave()).toBe(true);
    const clean = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(clean); expect(clean.defaultPrevented).toBe(false);
    editor().form.controls.name.setValue('Draft'); confirm.mockReturnValue(true); component.cancel(); await settle(); await detail();
    expect(TestBed.inject(Router).url).toBe('/sensors/17?' + context); expect(toastr.success).not.toHaveBeenCalled();
  });
  it('sanitizes URL parameters without accepting an external returnUrl', async () => {
    await ready('/sensors/17/edit?company_id=-1&site_id=bad&equipment_id=0&page=0&page_size=101&search=%20%20&status=ACTIVE&returnUrl=https://example.com');
    expect(component.listQuery()).toEqual({ company_id: undefined, site_id: undefined, equipment_id: undefined, page: 1, page_size: 20, search: undefined, status: undefined });
    expect(component.equipment()?.id).toBe(12);
  });
  it.each(['route', 'destroy'])('ignores a delayed navigation resolution after %s', async outcome => {
    await ready(); editor().form.controls.name.setValue('Nouveau');
    let finish!: (value: boolean) => void;
    vi.spyOn(TestBed.inject(Router), 'navigate').mockImplementation(() => new Promise<boolean>(resolve => { finish = resolve; }));
    await submit(); patch().flush({ ...sensor, name: 'Nouveau' }); await settle();
    if (outcome === 'route') {
      component = await harness.navigateByUrl('/sensors/18/edit', SensorEditComponent); await settle();
      read('sensors/18').flush({ ...sensor, id: 18 }); parents(); await settle();
    } else harness.fixture.destroy();
    finish(true); await Promise.resolve(); expect(toastr.success).not.toHaveBeenCalled();
  });
  it.each(['site', 'company'])('rejects an invalid %s foreign key without requesting an invalid URL', async scope => {
    await open(); read('sensors/17').flush(sensor);
    read('equipments/12').flush(scope === 'site' ? { ...equipment, site_id: 0 } : equipment);
    if (scope === 'company') read('sites/9').flush({ ...site, company_id: 0 });
    await settle(); expect(component.referenceState()).toBe('error'); component.save(); http.expectNone(() => true);
  });

});
