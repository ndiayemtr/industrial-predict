import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, effect, inject, input, output, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { SiteCreate, SiteUpdate } from '../../models/site-write.model';
import { SiteRead } from '../../../../core/models/reference-data.model';

export type SiteField = 'company_id' | 'name' | 'code' | 'description';
export type SiteFieldErrors = Partial<Record<SiteField, string>>;
export interface CompanyOption { id: number; label: string }
const requiredText = (maximum: number, preserveSpaces = false): ValidatorFn => (control: AbstractControl) => {
  const text = String(control.value).trim();
  return !text ? { required: true } : Array.from(preserveSpaces ? String(control.value) : text).length > maximum ? { maxlength: true } : null;
};

@Component({
  selector: 'app-site-form', standalone: true, imports: [ReactiveFormsModule],
  templateUrl: './site-form.component.html', styleUrl: './site-form.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SiteFormComponent {
  readonly editMode = input(false);
  readonly initialSite = input<SiteRead | null>(null);
  readonly companyLabel = input('Entreprise indisponible');
  readonly initialCompanyId = input<number | null>(null);
  readonly companies = input<readonly CompanyOption[]>([]);
  readonly verifiedCompanyId = input<number | null>(null);
  readonly saving = input(false);
  readonly blocked = input(false);
  readonly fieldErrors = input<SiteFieldErrors>({});
  readonly companyChanged = output<number | null>();
  readonly submitted = output<SiteCreate>();
  readonly updated = output<SiteUpdate>();
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
    effect(() => {
      const site = this.initialSite();
      this.form.reset({ company_id: this.editMode() ? site?.company_id ?? null : this.initialCompanyId(),
        name: site?.name ?? '', code: site?.code ?? '', description: site?.description ?? null }, { emitEvent: false });
      this.form.controls.name.setValidators(requiredText(150, this.editMode()));
      this.form.controls.code.setValidators(requiredText(50, this.editMode()));
      this.form.controls.name.updateValueAndValidity({ emitEvent: false });
      this.form.controls.code.updateValueAndValidity({ emitEvent: false });
      if (this.editMode()) this.form.controls.company_id.disable({ emitEvent: false });
      else this.form.controls.company_id.enable({ emitEvent: false });
    });
    this.form.controls.company_id.valueChanges.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe(id => this.companyChanged.emit(id));
    this.form.valueChanges.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe(() => this.edited.emit());
  }

  hasChanges(): boolean {
    if (this.editMode()) return Object.keys(this.changes()).length > 0;
    const value = this.form.getRawValue();
    return value.company_id !== this.initialCompanyId() || value.name !== '' || value.code !== '' || value.description !== null;
  }
  changes(): SiteUpdate {
    const original = this.initialSite(), value = this.form.getRawValue();
    if (!original) return {};
    const patch: SiteUpdate = {};
    if (value.name !== original.name) patch.name = value.name;
    if (value.code !== original.code) patch.code = value.code;
    if (value.description !== (original.description ?? null)) patch.description = value.description;
    return patch;
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
    if (this.form.invalid || (!this.editMode() && value.company_id !== this.verifiedCompanyId())) {
      const first = !this.editMode() && (value.company_id === null || this.form.controls.company_id.invalid || value.company_id !== this.verifiedCompanyId())
        ? 'company_id' : this.form.controls.name.invalid ? 'name' : 'code';
      this.focusField(first); return;
    }
    if (this.editMode()) { this.updated.emit(this.changes()); return; }
    this.submitted.emit({ company_id: value.company_id!, name: value.name.trim(), code: value.code.trim(),
      ...(this.form.controls.description.dirty ? { description: value.description } : {}) });
  }
}
