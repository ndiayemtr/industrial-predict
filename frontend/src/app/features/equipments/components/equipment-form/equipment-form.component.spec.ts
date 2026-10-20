import { ComponentFixture, TestBed } from '@angular/core/testing';
import { EquipmentFormComponent } from './equipment-form.component';
import { EquipmentRead } from '../../../../core/models/reference-data.model';

describe('EquipmentForm creation contract', () => {
  let fixture: ComponentFixture<EquipmentFormComponent>;
  let component: EquipmentFormComponent;
  const root = () => fixture.nativeElement as HTMLElement;
  beforeEach(() => {
    fixture = TestBed.createComponent(EquipmentFormComponent); component = fixture.componentInstance;
    fixture.detectChanges(); TestBed.tick(); fixture.detectChanges();
  });
  function parents() {
    fixture.componentRef.setInput('initialParents', { company_id: 7, site_id: 9 });
    fixture.componentRef.setInput('verifiedCompanyId', 7); fixture.componentRef.setInput('verifiedSiteId', 9);
    fixture.componentRef.setInput('companies', [{ id: 7, label: 'Entreprise' }]); fixture.componentRef.setInput('sites', [{ id: 9, label: 'Site' }]);
    fixture.detectChanges(); TestBed.tick(); fixture.detectChanges();
  }
  function fill() { parents(); component.form.patchValue({ name: ' Pompe 日本 ', code: ' Code-É ', equipment_type: ' Type Libre ' }); }

  it('starts without parents, with visible backend defaults and accessible required controls', () => {
    expect(component.form.controls.company_id.value).toBeNull(); expect(component.form.controls.site_id.value).toBeNull();
    expect(component.form.controls.status.value).toBe('operational'); expect(component.form.controls.criticality.value).toBe('medium');
    expect(component.hasChanges()).toBe(false); component.submit(); fixture.detectChanges();
    expect(document.activeElement?.id).toBe('equipment-company_id');
    expect(root().querySelector('#equipment-company_id')?.getAttribute('aria-invalid')).toBe('true');
    for (const control of root().querySelectorAll('input,select,textarea')) expect(root().querySelector(`label[for="${control.id}"]`)).not.toBeNull();
    expect(root().querySelector('#equipment-name')?.hasAttribute('maxlength')).toBe(false);
  });
  it.each([['name', 150], ['code', 100], ['equipment_type', 100]] as const)('counts Unicode code points and trims %s with limit %s', (field, limit) => {
    fill(); const emitted = vi.fn(); component.submitted.subscribe(emitted);
    component.form.controls[field].setValue('  ' + '😀'.repeat(limit) + '  '); component.submit();
    expect(emitted).toHaveBeenCalledOnce(); expect(emitted.mock.calls[0][0][field]).toBe('😀'.repeat(limit));
    emitted.mockClear(); component.form.controls[field].setValue('😀'.repeat(limit + 1)); component.submit(); fixture.detectChanges();
    expect(emitted).not.toHaveBeenCalled(); expect(document.activeElement?.id).toBe(`equipment-${field}`);
    expect(component.error(field)).toContain(`${limit} caractères Unicode`);
  });
  it.each(['name', 'code', 'equipment_type'] as const)('rejects whitespace-only %s and focuses it', field => {
    fill(); component.form.controls[field].setValue(' \t\n '); const emitted = vi.fn(); component.submitted.subscribe(emitted); component.submit();
    expect(emitted).not.toHaveBeenCalled(); expect(document.activeElement?.id).toBe(`equipment-${field}`);
  });
  it('emits exactly writable fields, preserves case and free type, and omits untouched description', () => {
    fill(); const emitted = vi.fn(); component.submitted.subscribe(emitted); component.submit();
    expect(emitted).toHaveBeenCalledExactlyOnceWith({ site_id: 9, name: 'Pompe 日本', code: 'Code-É', equipment_type: 'Type Libre', status: 'operational', criticality: 'medium' });
  });
  it.each(['', null, '  Texte 日本\n Ligne  '])('keeps explicit description %s distinct from omission', description => {
    fill(); component.form.controls.description.setValue(description); component.form.controls.description.markAsDirty();
    const emitted = vi.fn(); component.submitted.subscribe(emitted); component.submit(); expect(emitted.mock.calls[0][0].description).toBe(description);
    expect(Object.hasOwn(emitted.mock.calls[0][0], 'description')).toBe(true);
  });
  it('removes description explicitly as null and keeps the textarea focus', () => {
    fill(); component.form.controls.description.setValue('Description'); component.removeDescription();
    expect(component.form.controls.description.value).toBeNull(); expect(component.form.controls.description.dirty).toBe(true);
    expect(document.activeElement?.id).toBe('equipment-description');
  });
  it.each(['status', 'criticality'] as const)('rejects unknown %s rather than silently defaulting it', field => {
    fill(); component.form.controls[field].setValue('unknown' as never); const emitted = vi.fn(); component.submitted.subscribe(emitted); component.submit();
    expect(emitted).not.toHaveBeenCalled(); expect(document.activeElement?.id).toBe(`equipment-${field}`);
  });
  it('blocks an unverified site and resets it on company change without clearing business fields', () => {
    fill(); const changed = vi.fn(), emitted = vi.fn(); component.companyChanged.subscribe(changed); component.submitted.subscribe(emitted);
    component.form.controls.site_id.setValue(10); component.submit(); expect(emitted).not.toHaveBeenCalled(); expect(document.activeElement?.id).toBe('equipment-site_id');
    component.form.controls.company_id.setValue(8); expect(changed).toHaveBeenCalledWith(8); expect(component.form.controls.site_id.value).toBeNull();
    expect(component.form.controls.name.value).toBe(' Pompe 日本 ');
  });
  it('does not erase typed business fields when verified URL parents arrive', () => {
    component.form.controls.name.setValue('Saisie conservée'); parents();
    expect(component.form.controls.name.value).toBe('Saisie conservée'); expect(component.form.controls.site_id.value).toBe(9);
  });
  it('detects actual changes including enums and restores a clean state on original values', () => {
    parents(); expect(component.hasChanges()).toBe(false);
    component.form.controls.criticality.setValue('high'); expect(component.hasChanges()).toBe(true);
    component.form.controls.criticality.setValue('medium'); expect(component.hasChanges()).toBe(false);
    component.form.controls.site_id.setValue(10); expect(component.hasChanges()).toBe(true);
    component.form.controls.site_id.setValue(9); expect(component.hasChanges()).toBe(false);
  });
  it.each(['saving', 'blocked'])('disables controls and ignores submission when %s', input => {
    fill(); fixture.componentRef.setInput(input, true); fixture.detectChanges(); const emitted = vi.fn(); component.submitted.subscribe(emitted); component.submit();
    expect(root().querySelector('fieldset')?.disabled).toBe(true); expect(emitted).not.toHaveBeenCalled();
  });
});

describe('EquipmentForm raw differential editing contract', () => {
  let fixture: ComponentFixture<EquipmentFormComponent>;
  let component: EquipmentFormComponent;
  const original: EquipmentRead = { id: 87, site_id: 9, name: ' Pompe 日本 ', code: ' Code É ', equipment_type: ' Type libre ',
    status: 'maintenance', criticality: 'high', description: ' Texte\n日本 ', created_at: '', updated_at: '' };
  beforeEach(() => {
    fixture = TestBed.createComponent(EquipmentFormComponent); component = fixture.componentInstance;
    fixture.componentRef.setInput('editMode', true); fixture.componentRef.setInput('initialEquipment', original);
    fixture.componentRef.setInput('companyLabel', 'Entreprise réelle'); fixture.componentRef.setInput('siteLabel', 'Site réel');
    fixture.detectChanges(); TestBed.tick(); fixture.detectChanges();
  });
  it('keeps parents read-only and separates editing output from creation', () => {
    const updated = vi.fn(), created = vi.fn(); component.updated.subscribe(updated); component.submitted.subscribe(created);
    expect(fixture.nativeElement.querySelector('#equipment-company_id')).toBeNull();
    expect(fixture.nativeElement.querySelector('#equipment-site_id')).toBeNull();
    expect(component.changes()).toEqual({}); expect(component.hasChanges()).toBe(false);
    component.form.controls.name.setValue('  Nouvelle pompe 日本  '); component.submit();
    expect(updated).toHaveBeenCalledExactlyOnceWith({ name: '  Nouvelle pompe 日本  ' }); expect(created).not.toHaveBeenCalled();
  });
  it.each([['name', 150], ['code', 100], ['equipment_type', 100]] as const)('counts raw Unicode and spaces for changed %s', (field, maximum) => {
    const emitted = vi.fn(); component.updated.subscribe(emitted);
    component.form.controls[field].setValue('😀'.repeat(maximum)); component.submit(); expect(emitted).toHaveBeenCalledTimes(1);
    emitted.mockClear(); component.form.controls[field].setValue('😀'.repeat(maximum) + ' '); component.submit();
    expect(emitted).not.toHaveBeenCalled(); expect(document.activeElement?.id).toBe(`equipment-${field}`);
    component.form.controls[field].setValue(' \t\n '); component.submit(); expect(component.form.controls[field].hasError('required')).toBe(true);
  });
  it('uses value comparison rather than dirty flags for all editable fields', () => {
    component.form.patchValue({ name: 'Other', code: 'Other', equipment_type: 'Other', status: 'operational', criticality: 'low', description: '' });
    expect(Object.keys(component.changes())).toHaveLength(6);
    component.form.patchValue(original); expect(component.changes()).toEqual({}); expect(component.hasChanges()).toBe(false);
  });
  it('removes description as null and treats restoration as clean', () => {
    component.removeDescription(); expect(component.changes()).toEqual({ description: null });
    component.form.controls.description.setValue(original.description); expect(component.hasChanges()).toBe(false);
    component.form.controls.description.setValue(''); expect(component.changes()).toEqual({ description: '' });
  });
  it.each(['status', 'criticality'] as const)('validates edited %s without inventing a transition rule', field => {
    const updated = vi.fn(); component.updated.subscribe(updated);
    component.form.controls[field].setValue('invalid' as never); component.submit(); expect(updated).not.toHaveBeenCalled();
    expect(document.activeElement?.id).toBe(`equipment-${field}`);
  });
  it('resets to a newly loaded record without carrying the previous draft forward', () => {
    component.form.controls.name.setValue('Draft');
    fixture.componentRef.setInput('initialEquipment', { ...original, id: 88, name: 'Autre équipement' });
    fixture.detectChanges(); TestBed.tick(); fixture.detectChanges();
    expect(component.form.controls.name.value).toBe('Autre équipement'); expect(component.hasChanges()).toBe(false);
  });
});
