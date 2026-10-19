import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, effect, inject, input, output, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { EquipmentCriticality, EquipmentStatus } from '../../../../core/models/reference-data.model';
import { EquipmentCreate } from '../../models/equipment-write.model';
import { equipmentCriticalityLabels, equipmentStatusLabels } from '../../models/equipment-labels';

export type EquipmentField = 'company_id' | 'site_id' | 'name' | 'code' | 'equipment_type' | 'status' | 'criticality' | 'description';
export type EquipmentFieldErrors = Partial<Record<EquipmentField, string>>;
export interface EquipmentParentSelection { company_id: number | null; site_id: number | null }
export interface EquipmentParentOption { id: number; label: string }
function textLimit(maximum: number): ValidatorFn {
  return (control: AbstractControl) => !String(control.value).trim() ? { required: true }
    : Array.from(String(control.value).trim()).length > maximum ? { maxlength: true } : null;
}
function requiredId(control: AbstractControl) { return Number.isSafeInteger(control.value) && control.value > 0 ? null : { required: true }; }

@Component({
  selector: 'app-equipment-form', standalone: true, imports: [ReactiveFormsModule],
  templateUrl: './equipment-form.component.html', styleUrl: './equipment-form.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class EquipmentFormComponent {
  readonly initialParents = input<EquipmentParentSelection | null>(null);
  readonly companies = input<readonly EquipmentParentOption[]>([]);
  readonly sites = input<readonly EquipmentParentOption[]>([]);
  readonly verifiedCompanyId = input<number | null>(null);
  readonly verifiedSiteId = input<number | null>(null);
  readonly saving = input(false);
  readonly blocked = input(false);
  readonly fieldErrors = input<EquipmentFieldErrors>({});
  readonly companyChanged = output<number | null>();
  readonly siteChanged = output<number | null>();
  readonly submitted = output<EquipmentCreate>();
  readonly cancelled = output<void>();
  readonly edited = output<void>();
  private readonly element = viewChild.required<ElementRef<HTMLFormElement>>('formElement');
  private baselineParents: EquipmentParentSelection = { company_id: null, site_id: null };
  readonly statusLabels = equipmentStatusLabels();
  readonly criticalityLabels = equipmentCriticalityLabels();
  readonly statuses = Object.keys(this.statusLabels) as EquipmentStatus[];
  readonly criticalities = Object.keys(this.criticalityLabels) as EquipmentCriticality[];
  readonly textFields = [
    { key: 'name', label: 'Nom', limit: 150 },
    { key: 'code', label: 'Code métier', limit: 100 },
    { key: 'equipment_type', label: 'Type d’équipement', limit: 100 }
  ] as const;
  readonly fieldOrder: readonly EquipmentField[] = ['company_id', 'site_id', 'name', 'code', 'equipment_type', 'status', 'criticality', 'description'];
  readonly form = new FormGroup({
    company_id: new FormControl<number | null>(null, requiredId),
    site_id: new FormControl<number | null>(null, requiredId),
    name: new FormControl('', { nonNullable: true, validators: textLimit(150) }),
    code: new FormControl('', { nonNullable: true, validators: textLimit(100) }),
    equipment_type: new FormControl('', { nonNullable: true, validators: textLimit(100) }),
    status: new FormControl<EquipmentStatus>('operational', { nonNullable: true,
      validators: control => Object.hasOwn(this.statusLabels, control.value) ? null : { enum: true } }),
    criticality: new FormControl<EquipmentCriticality>('medium', { nonNullable: true,
      validators: control => Object.hasOwn(this.criticalityLabels, control.value) ? null : { enum: true } }),
    description: new FormControl<string | null>(null)
  });

  constructor() {
    effect(() => {
      const parents = this.initialParents();
      if (parents && !this.form.controls.company_id.dirty && !this.form.controls.site_id.dirty) {
        this.form.patchValue(parents, { emitEvent: false }); this.baselineParents = { ...parents };
      }
    });
    this.form.controls.company_id.valueChanges.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe(id => {
      this.form.controls.site_id.setValue(null, { emitEvent: false }); this.companyChanged.emit(id);
    });
    this.form.controls.site_id.valueChanges.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe(id => this.siteChanged.emit(id));
    this.form.valueChanges.pipe(takeUntilDestroyed(inject(DestroyRef))).subscribe(() => this.edited.emit());
  }
  hasChanges(): boolean {
    const value = this.form.getRawValue();
    return value.company_id !== this.baselineParents.company_id || value.site_id !== this.baselineParents.site_id
      || value.name !== '' || value.code !== '' || value.equipment_type !== '' || value.status !== 'operational'
      || value.criticality !== 'medium' || value.description !== null;
  }
  focusField(field: EquipmentField): void { this.element().nativeElement.querySelector<HTMLElement>(`#equipment-${field}`)?.focus(); }
  error(field: EquipmentField): string {
    const control = this.form.controls[field];
    if (control.touched) {
      if (field === 'company_id' && (control.invalid || control.value !== this.verifiedCompanyId())) return 'Sélectionnez une entreprise disponible.';
      if (field === 'site_id' && (control.invalid || control.value !== this.verifiedSiteId() || this.form.controls.company_id.value !== this.verifiedCompanyId())) return 'Sélectionnez un site vérifié de cette entreprise.';
      if (control.hasError('required')) return 'Ce champ est obligatoire et ne doit pas être blanc.';
      if (control.hasError('maxlength')) return `${field === 'name' ? 150 : 100} caractères Unicode maximum.`;
      if (control.hasError('enum')) return 'Sélectionnez une valeur proposée.';
    }
    return this.fieldErrors()[field] ?? '';
  }
  removeDescription(): void {
    this.form.controls.description.setValue(null); this.form.controls.description.markAsDirty(); this.focusField('description');
  }
  submit(): void {
    if (this.saving() || this.blocked()) return;
    this.form.markAllAsTouched();
    const value = this.form.getRawValue();
    const first = this.fieldOrder.find(field => this.form.controls[field].invalid
      || (field === 'company_id' && value.company_id !== this.verifiedCompanyId())
      || (field === 'site_id' && value.site_id !== this.verifiedSiteId()));
    if (first) { this.focusField(first); return; }
    this.submitted.emit({ site_id: value.site_id!, name: value.name.trim(), code: value.code.trim(),
      equipment_type: value.equipment_type.trim(), status: value.status, criticality: value.criticality,
      ...(this.form.controls.description.dirty ? { description: value.description } : {}) });
  }
}
