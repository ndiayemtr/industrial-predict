import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SensorFormComponent } from './sensor-form.component';

describe('Typed Sensor creation form', () => {
  let fixture: ComponentFixture<SensorFormComponent>, component: SensorFormComponent;
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [SensorFormComponent] }).compileComponents();
    fixture = TestBed.createComponent(SensorFormComponent); component = fixture.componentInstance;
    fixture.componentRef.setInput('initialParents', { company_id: 7, site_id: 9, equipment_id: 12 });
    fixture.componentRef.setInput('verifiedCompanyId', 7); fixture.componentRef.setInput('verifiedSiteId', 9); fixture.componentRef.setInput('verifiedEquipmentId', 12);
    fixture.detectChanges(); TestBed.tick(); fixture.detectChanges();
  });
  afterEach(() => TestBed.resetTestingModule());
  function fill() { component.form.patchValue({ name: ' Nom 日本 ', code: ' Code ', sensor_type: ' Type ', unit: ' mm/s ' }); }
  it.each([false, true])('preserves headings, field order and readonly values in edit mode %s', editMode => {
    if (editMode) fixture.componentRef.setInput('initialSensor', {
      id: 17, equipment_id: 12, name: 'Capteur', code: 'SEN', sensor_type: 'temperature', unit: '°C',
      status: 'active', description: null, created_at: '', updated_at: ''
    });
    fixture.componentRef.setInput('editMode', editMode); fixture.detectChanges(); TestBed.tick(); fixture.detectChanges();
    const root: HTMLElement = fixture.nativeElement;
    expect([...root.querySelectorAll('fieldset > legend > h2')].map(title => title.textContent))
      .toEqual(['Rattachement industriel', 'Informations du capteur']);
    expect([...root.querySelectorAll('.fields-grid input, .fields-grid select, .fields-grid textarea')].map(control => control.id))
      .toEqual(editMode ? ['sensor-name', 'sensor-code', 'sensor-status', 'sensor-description']
        : ['sensor-name', 'sensor-code', 'sensor-sensor_type', 'sensor-unit', 'sensor-status', 'sensor-description']);
    expect(root.querySelector('.description-field textarea')?.id).toBe('sensor-description');
    if (editMode) {
      expect([...root.querySelectorAll('.fields-grid .readonly-values dd')].map(value => value.textContent)).toEqual(['temperature', '°C']);
      expect(component.form.controls.sensor_type.disabled).toBe(true); expect(component.form.controls.unit.disabled).toBe(true);
    }
    const actions = [...root.querySelectorAll<HTMLButtonElement>('.actions button')];
    expect(actions.map(action => action.textContent?.trim())).toEqual(['Annuler', editMode ? 'Enregistrer les modifications' : 'Créer le capteur']);
    expect(actions.map(action => action.type)).toEqual(['button', 'submit']);
    const cancel = vi.fn(), submit = vi.fn(), update = vi.fn();
    component.cancelled.subscribe(cancel); component.submitted.subscribe(submit); component.updated.subscribe(update);
    actions[0].click(); expect(cancel).toHaveBeenCalledOnce(); expect(submit).not.toHaveBeenCalled(); expect(update).not.toHaveBeenCalled();
    fixture.componentRef.setInput('saving', true); fixture.detectChanges();
    expect(actions.every(action => action.disabled)).toBe(true);
    expect(actions[1].textContent).toBe('Enregistrement en cours…');
    actions[0].click(); expect(cancel).toHaveBeenCalledOnce();
  });
  it('starts active with no description and a clean verified baseline', () => {
    expect(component.form.controls.status.value).toBe('active'); expect(component.form.controls.description.value).toBeNull(); expect(component.hasChanges()).toBe(false);
    expect(fixture.nativeElement.querySelectorAll('label[for]')).toHaveLength(9);
  });
  it.each([['name',150],['code',100],['sensor_type',100],['unit',30]] as const)('validates required Unicode code points for %s with limit %s', (field,limit) => {
    const control = component.form.controls[field];
    for (const value of ['', '   ', '\n\t']) { control.setValue(value); expect(control.hasError('required')).toBe(true); }
    control.setValue('😀'.repeat(limit)); expect(control.valid).toBe(true);
    control.setValue('😀'.repeat(limit+1)); expect(control.hasError('maxlength')).toBe(true);
    control.markAsTouched(); expect(component.error(field)).toBe(`${limit} caractères Unicode maximum.`);
  });
  it('emits a strict payload with trimmed required text and preserves untouched description omission', () => {
    const sent = vi.fn(); component.submitted.subscribe(sent); fill(); component.submit();
    expect(sent).toHaveBeenCalledWith({ equipment_id: 12, name: 'Nom 日本', code: 'Code', sensor_type: 'Type', unit: 'mm/s', status: 'active' });
  });
  it.each(['', null, ' Ligne 1\n日本 '])('preserves explicit description %s', description => {
    const sent = vi.fn(); component.submitted.subscribe(sent); fill(); component.form.controls.description.setValue(description); component.form.controls.description.markAsDirty(); component.submit();
    expect(sent.mock.calls[0][0].description).toBe(description); expect(Object.hasOwn(sent.mock.calls[0][0], 'description')).toBe(true);
  });
  it('maps explicit removal to null and focuses the description', () => {
    fill(); component.form.controls.description.setValue('Texte'); component.removeDescription();
    expect(component.form.controls.description.value).toBeNull(); expect(component.form.controls.description.dirty).toBe(true); expect(document.activeElement?.id).toBe('sensor-description');
  });
  it('rejects unsupported status and focuses the first invalid field', () => {
    const sent = vi.fn(); component.submitted.subscribe(sent); component.submit(); expect(sent).not.toHaveBeenCalled(); expect(document.activeElement?.id).toBe('sensor-name');
    fill(); component.form.controls.status.setValue('ACTIVE' as never); component.submit(); expect(sent).not.toHaveBeenCalled(); expect(document.activeElement?.id).toBe('sensor-status');
  });
  it('clears descendants when company/site changes and never submits unverified references', () => {
    const sent = vi.fn(), company = vi.fn(), site = vi.fn(); component.submitted.subscribe(sent); component.companyChanged.subscribe(company); component.siteChanged.subscribe(site);
    fill(); component.form.controls.company_id.setValue(8); expect(company).toHaveBeenCalledWith(8);
    expect(component.form.getRawValue()).toMatchObject({ site_id: null, equipment_id: null }); component.submit(); expect(sent).not.toHaveBeenCalled();
    component.form.controls.site_id.setValue(10); expect(site).toHaveBeenCalledWith(10); expect(component.form.controls.equipment_id.value).toBeNull();
  });
  it.each(['saving','blocked'])('prevents submit while %s', state => {
    const sent = vi.fn(); component.submitted.subscribe(sent); fill(); fixture.componentRef.setInput(state, true); fixture.detectChanges(); component.submit();
    expect(sent).not.toHaveBeenCalled(); expect(fixture.nativeElement.querySelector('button[type=submit]').disabled).toBe(true);
  });
});
