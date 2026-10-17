import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SiteFormComponent } from './site-form.component';

describe('Site creation form', () => {
  let fixture: ComponentFixture<SiteFormComponent>;
  let form: SiteFormComponent;
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [SiteFormComponent] });
    fixture = TestBed.createComponent(SiteFormComponent); form = fixture.componentInstance;
    fixture.componentRef.setInput('initialCompanyId', 7); fixture.componentRef.setInput('verifiedCompanyId', 7);
    fixture.componentRef.setInput('companies', [{ id: 7, label: 'PETROSEN' }]); fixture.detectChanges();
  });
  function fill() { form.form.patchValue({ name: ' Usine 日本 😀 ', code: ' Énergie-é ' }); }
  it('hides company guidance for a verified prefill, restores it on clearing, and keeps error descriptions connected', () => {
    const help = () => fixture.nativeElement.querySelector('#site-company-help');
    const select = fixture.nativeElement.querySelector('#site-company_id');
    expect(help()).toBeNull(); expect(select.getAttribute('aria-describedby')).toBe('site-company_id-error');
    form.form.controls.company_id.setValue(null); fixture.detectChanges();
    expect(help()?.textContent).toBe('Choisissez une entreprise pour rattacher le site.');
    expect(select.getAttribute('aria-describedby')).toBe('site-company-help site-company_id-error');
    form.form.controls.company_id.setValue(7); fixture.detectChanges(); expect(help()).toBeNull();
    fixture.componentRef.setInput('verifiedCompanyId', null); fixture.detectChanges();
    expect(help()).not.toBeNull(); form.submit(); fixture.detectChanges();
    expect(form.error('company_id')).toContain('entreprise disponible');
  });
  it('shows removal only for supplied text, emits null on removal, and preserves manual clearing as an empty string', () => {
    fill(); const root: HTMLElement = fixture.nativeElement;
    const button = () => root.querySelector<HTMLButtonElement>('.remove-description');
    expect(button()).toBeNull();
    const description = root.querySelector<HTMLTextAreaElement>('#site-description')!;
    description.value = 'Description 日本'; description.dispatchEvent(new Event('input', { bubbles: true })); fixture.detectChanges();
    expect(button()).not.toBeNull(); button()!.click(); fixture.detectChanges();
    expect(description.value).toBe(''); expect(button()).toBeNull();
    expect(document.activeElement).toBe(description);
    const emit = vi.spyOn(form.submitted, 'emit'); form.submit();
    expect(emit).toHaveBeenLastCalledWith({ company_id: 7, name: 'Usine 日本 😀', code: 'Énergie-é', description: null });
    description.value = 'Texte'; description.dispatchEvent(new Event('input', { bubbles: true })); fixture.detectChanges();
    description.value = ''; description.dispatchEvent(new Event('input', { bubbles: true })); fixture.detectChanges();
    expect(button()).toBeNull(); form.submit();
    expect(emit).toHaveBeenLastCalledWith({ company_id: 7, name: 'Usine 日本 😀', code: 'Énergie-é', description: '' });
  });
  it('initializes only the explicit company and focuses the first invalid business field', () => {
    expect(form.form.controls.company_id.value).toBe(7); expect(form.hasChanges()).toBe(false);
    form.submit(); fixture.detectChanges();
    expect(document.activeElement).toBe(fixture.nativeElement.querySelector('#site-name'));
    expect(form.error('name')).toBe('Le nom est obligatoire.');
    form.form.controls.name.setValue('   '); expect(form.form.controls.name.invalid).toBe(true);
    form.form.controls.name.setValue('Usine'); form.submit();
    expect(document.activeElement).toBe(fixture.nativeElement.querySelector('#site-code'));
  });
  it('requires a verified company and focuses its accessible select before other fields', () => {
    fill(); fixture.componentRef.setInput('verifiedCompanyId', null); fixture.detectChanges();
    const emit = vi.spyOn(form.submitted, 'emit'); form.submit(); fixture.detectChanges();
    expect(emit).not.toHaveBeenCalled(); expect(document.activeElement?.id).toBe('site-company_id');
    expect(form.error('company_id')).toContain('entreprise disponible');
    expect(fixture.nativeElement.querySelector('#site-company_id').getAttribute('aria-invalid')).toBe('true');
  });
  it.each([['name', 150], ['code', 50]] as const)('counts Unicode code points for %s SQL limit %s', (field, limit) => {
    fill(); form.form.controls[field].setValue('😀'.repeat(limit)); expect(form.form.controls[field].valid).toBe(true);
    form.form.controls[field].setValue('😀'.repeat(limit + 1)); expect(form.form.controls[field].hasError('maxlength')).toBe(true);
    form.submit(); expect(document.activeElement?.id).toBe(`site-${field}`);
  });
  it('serializes Unicode, trims only name/code and omits untouched description and technical fields', () => {
    fill(); const emit = vi.spyOn(form.submitted, 'emit'); form.submit();
    expect(emit).toHaveBeenCalledExactlyOnceWith({ company_id: 7, name: 'Usine 日本 😀', code: 'Énergie-é' });
    expect(Object.keys(form.form.controls)).toEqual(['company_id', 'name', 'code', 'description']);
    expect(fixture.nativeElement.textContent).not.toContain('identifiant');
  });
  it.each(['', '  Texte\n日本  ', null])('preserves an explicitly edited description %s', description => {
    fill(); form.form.controls.description.setValue(description); form.form.controls.description.markAsDirty();
    const emit = vi.spyOn(form.submitted, 'emit'); form.submit();
    expect(emit).toHaveBeenCalledWith({ company_id: 7, name: 'Usine 日本 😀', code: 'Énergie-é', description });
  });
  it('offers an explicit null removal without imposing an invented description length', () => {
    fill(); form.form.controls.description.setValue('😀'.repeat(10000)); expect(form.form.controls.description.valid).toBe(true);
    form.removeDescription(); expect(form.form.controls.description.value).toBeNull();
    expect(form.form.controls.description.dirty).toBe(true);
  });
  it.each(['saving', 'blocked'] as const)('blocks submission while %s', flag => {
    fill(); fixture.componentRef.setInput(flag, true); fixture.detectChanges();
    const emit = vi.spyOn(form.submitted, 'emit'); form.submit(); expect(emit).not.toHaveBeenCalled();
    expect(fixture.nativeElement.querySelector('fieldset').disabled).toBe(true);
  });
});
