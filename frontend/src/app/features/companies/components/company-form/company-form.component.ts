import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, effect, inject, input, output, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { CompanyCreate } from '../../models/company-write.model';
import { CompanyRead } from '../../../../core/models/reference-data.model';

export type CompanyField = 'name' | 'code' | 'description';
export type CompanyFieldErrors = Partial<Record<CompanyField, string>>;

// UX validation follows the SQL character limits; it is not a security boundary.
const requiredText = (maximum: number): ValidatorFn => (control: AbstractControl) => {
  const text = String(control.value).trim();
  return !text ? { required: true } : Array.from(text).length > maximum ? { maxlength: true } : null;
};

@Component({
  selector: 'app-company-form', standalone: true, imports: [ReactiveFormsModule],
  templateUrl: './company-form.component.html', styleUrl: './company-form.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CompanyFormComponent {
  readonly initialCompany = input<CompanyRead | null>(null);
  readonly editMode = input(false);
  readonly saving = input(false);
  readonly blocked = input(false);
  readonly fieldErrors = input<CompanyFieldErrors>({});
  readonly submitted = output<CompanyCreate>();
  readonly cancelled = output<void>();
  readonly edited = output<void>();
  private readonly formElement = viewChild.required<ElementRef<HTMLFormElement>>('formElement');
  readonly form = new FormGroup({
    name: new FormControl('', { nonNullable: true, validators: [requiredText(150)] }),
    code: new FormControl('', { nonNullable: true, validators: [requiredText(50)] }),
    description: new FormControl('', { nonNullable: true })
  });

  constructor() {
    effect(() => {
      const company = this.initialCompany();
      this.form.reset({ name: company?.name ?? '', code: company?.code ?? '', description: company?.description ?? '' }, { emitEvent: false });
    });
    this.form.valueChanges.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe(() => this.edited.emit());
  }

  hasChanges(): boolean {
    const value = this.form.getRawValue(), original = this.initialCompany();
    return value.name !== (original?.name ?? '') || value.code !== (original?.code ?? '')
      || value.description !== (original?.description ?? '');
  }

  focusField(field: CompanyField): void {
    this.formElement().nativeElement.querySelector<HTMLElement>(`#company-${field}`)?.focus();
  }

  error(field: CompanyField): string {
    const control = this.form.controls[field];
    if (control.touched && control.hasError('required')) return field === 'name' ? 'Le nom est obligatoire.' : 'Le code est obligatoire.';
    if (control.touched && control.hasError('maxlength')) return field === 'name' ? '150 caractères maximum.' : '50 caractères maximum.';
    return this.fieldErrors()[field] ?? '';
  }

  submit(): void {
    if (this.saving() || this.blocked()) return;
    this.form.markAllAsTouched();
    if (this.form.invalid) {
      const field = this.form.controls.name.invalid ? 'name' : 'code';
      this.formElement().nativeElement.querySelector<HTMLElement>(`#company-${field}`)?.focus();
      return;
    }
    const value = this.form.getRawValue();
    this.submitted.emit({ name: value.name.trim(), code: value.code.trim(),
      ...(this.form.controls.description.dirty ? { description: value.description === '' ? null : value.description } : {}) });
  }
}
