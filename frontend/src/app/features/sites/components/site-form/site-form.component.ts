import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, effect, inject, input, output, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { SiteCreate } from '../../models/site-write.model';

export type SiteField = 'company_id' | 'name' | 'code' | 'description';
export type SiteFieldErrors = Partial<Record<SiteField, string>>;
export interface CompanyOption { id: number; label: string }
const requiredText = (maximum: number): ValidatorFn => (control: AbstractControl) => {
  const text = String(control.value).trim();
  return !text ? { required: true } : Array.from(text).length > maximum ? { maxlength: true } : null;
};

@Component({
  selector: 'app-site-form', standalone: true, imports: [ReactiveFormsModule],
  templateUrl: './site-form.component.html', styleUrl: './site-form.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SiteFormComponent {
  readonly initialCompanyId = input<number | null>(null);
  readonly companies = input<readonly CompanyOption[]>([]);
  readonly verifiedCompanyId = input<number | null>(null);
  readonly saving = input(false);
  readonly blocked = input(false);
  readonly fieldErrors = input<SiteFieldErrors>({});
  readonly companyChanged = output<number | null>();
  readonly submitted = output<SiteCreate>();
  readonly cancelled = output<void>();
  readonly edited = output<void>();
  private readonly element = viewChild.required<ElementRef<HTMLFormElement>>('formElement');
  readonly form = new FormGroup({
    company_id: new FormControl<number | null>(null, control => Number.isSafeInteger(control.value) && control.value > 0 ? null : { required: true }),
    name: new FormControl('', { nonNullable: true, validators: [requiredText(150)] }),
    code: new FormControl('', { nonNullable: true, validators: [requiredText(50)] }),
    description: new FormControl<string | null>(null)
  });

  constructor() {
    effect(() => this.form.controls.company_id.setValue(this.initialCompanyId(), { emitEvent: false }));
    this.form.controls.company_id.valueChanges.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe(id => this.companyChanged.emit(id));
    this.form.valueChanges.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe(() => this.edited.emit());
  }

  hasChanges(): boolean {
    const value = this.form.getRawValue();
    return value.company_id !== this.initialCompanyId() || value.name !== '' || value.code !== '' || value.description !== null;
  }
  focusField(field: SiteField): void { this.element().nativeElement.querySelector<HTMLElement>(`#site-${field}`)?.focus(); }
  error(field: SiteField): string {
    const control = this.form.controls[field];
    if (control.touched && (control.hasError('required') || (field === 'company_id' && control.value !== this.verifiedCompanyId()))) {
      return field === 'company_id' ? 'Sélectionnez une entreprise disponible.' : field === 'name' ? 'Le nom est obligatoire.' : 'Le code est obligatoire.';
    }
    if (control.touched && control.hasError('maxlength')) return field === 'name' ? '150 caractères maximum.' : '50 caractères maximum.';
    return this.fieldErrors()[field] ?? '';
  }
  removeDescription(): void {
    this.form.controls.description.setValue(null);
    this.form.controls.description.markAsDirty();
    this.focusField('description');
  }
  submit(): void {
    if (this.saving() || this.blocked()) return;
    this.form.markAllAsTouched();
    const value = this.form.getRawValue();
    if (this.form.invalid || value.company_id !== this.verifiedCompanyId()) {
      const first = value.company_id === null || this.form.controls.company_id.invalid || value.company_id !== this.verifiedCompanyId()
        ? 'company_id' : this.form.controls.name.invalid ? 'name' : 'code';
      this.focusField(first); return;
    }
    this.submitted.emit({ company_id: value.company_id!, name: value.name.trim(), code: value.code.trim(),
      ...(this.form.controls.description.dirty ? { description: value.description } : {}) });
  }
}
