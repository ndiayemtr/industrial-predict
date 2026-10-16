import { ComponentFixture, TestBed } from '@angular/core/testing';
import { CompanyFormComponent } from './company-form.component';

describe('CompanyFormComponent', () => {
  let fixture: ComponentFixture<CompanyFormComponent>;
  let component: CompanyFormComponent;
  const element = () => fixture.nativeElement as HTMLElement;

  beforeEach(() => {
    fixture = TestBed.createComponent(CompanyFormComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  function valid() { component.form.patchValue({ name: ' Société énergie ', code: ' Mix-é ' }); }

  it('provides labels, required fields, help, and no business/API dependency', () => {
    expect(element().querySelectorAll('label')).toHaveLength(3);
    expect(element().querySelectorAll('input[required]')).toHaveLength(2);
    expect(element().querySelectorAll('h1')).toHaveLength(0);
    expect(element().querySelector('textarea')?.hasAttribute('maxlength')).toBe(false);
    expect(component.hasChanges()).toBe(false);
  });

  it('rejects blank values, announces local validation and focuses the first invalid field', () => {
    const submit = vi.fn();
    component.submitted.subscribe(submit);
    component.form.controls.name.setValue('   ');
    component.submit();
    fixture.detectChanges();
    expect(submit).not.toHaveBeenCalled();
    expect(element().textContent).toContain('Le nom est obligatoire');
    expect(element().textContent).toContain('Le code est obligatoire');
    expect(document.activeElement).toBe(element().querySelector('#company-name'));
    expect(element().querySelector('#company-name')?.getAttribute('aria-invalid')).toBe('true');
  });

  it('trims name/code, preserves case and omits an untouched description', () => {
    valid();
    const submit = vi.fn();
    component.submitted.subscribe(submit);
    component.submit();
    expect(submit).toHaveBeenCalledExactlyOnceWith({ name: 'Société énergie', code: 'Mix-é' });
  });

  it.each(['', '   ', ' Texte\navec espaces '])('preserves the meaning of an edited description %j', description => {
    valid();
    component.form.controls.description.setValue(description);
    component.form.controls.description.markAsDirty();
    const submit = vi.fn();
    component.submitted.subscribe(submit);
    component.submit();
    expect(submit).toHaveBeenCalledExactlyOnceWith({ name: 'Société énergie', code: 'Mix-é', description: description === '' ? null : description });
  });

  it('counts Unicode code points against SQL limits without an ASCII or UTF-16 restriction', () => {
    component.form.patchValue({ name: '😀'.repeat(150), code: 'é'.repeat(50) });
    expect(component.form.valid).toBe(true);
    component.form.patchValue({ name: '😀'.repeat(151), code: 'é'.repeat(51) });
    component.form.markAllAsTouched();
    expect(component.error('name')).toBe('150 caractères maximum.');
    expect(component.error('code')).toBe('50 caractères maximum.');
  });

  it('disables controls and prevents submissions while saving or blocked', () => {
    valid();
    const submit = vi.fn();
    component.submitted.subscribe(submit);
    fixture.componentRef.setInput('saving', true);
    fixture.detectChanges();
    component.submit();
    expect(element().querySelector('fieldset')?.disabled).toBe(true);
    expect(element().querySelector('form')?.getAttribute('aria-busy')).toBe('true');
    fixture.componentRef.setInput('saving', false);
    fixture.componentRef.setInput('blocked', true);
    fixture.detectChanges();
    component.submit();
    expect(submit).not.toHaveBeenCalled();
  });

  it('renders server field errors as text associated with inputs and emits cancel/edit events', () => {
    fixture.componentRef.setInput('fieldErrors', { code: 'Code déjà utilisé.' });
    fixture.detectChanges();
    expect(element().querySelector('#code-error')?.textContent).toBe('Code déjà utilisé.');
    expect(element().querySelector('#company-code')?.getAttribute('aria-describedby')).toContain('code-error');
    const cancel = vi.fn(), edit = vi.fn();
    component.cancelled.subscribe(cancel);
    component.edited.subscribe(edit);
    element().querySelector<HTMLButtonElement>('button[type="button"]')!.click();
    component.form.controls.name.setValue('New');
    expect(cancel).toHaveBeenCalledOnce();
    expect(edit).toHaveBeenCalledOnce();
    expect(component.hasChanges()).toBe(true);
  });
});
