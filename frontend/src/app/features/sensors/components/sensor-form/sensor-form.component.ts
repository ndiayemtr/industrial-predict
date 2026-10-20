import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, effect, inject, input, output, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, ValidatorFn } from '@angular/forms';
import { SensorStatus } from '../../models/sensor.model';
import { SensorCreate } from '../../models/sensor-write.model';

export interface SensorParents { company_id: number | null; site_id: number | null; equipment_id: number | null }
export interface SensorParentOption { id: number; label: string }
export type SensorField = keyof SensorParents | 'name' | 'code' | 'sensor_type' | 'unit' | 'status' | 'description';
export type SensorFieldErrors = Partial<Record<SensorField, string>>;
const requiredId = (control: AbstractControl) => Number.isSafeInteger(control.value) && control.value > 0 ? null : { required: true };
const textLimit = (limit: number): ValidatorFn => control => !String(control.value).trim() ? { required: true }
  : Array.from(String(control.value).trim()).length > limit ? { maxlength: true } : null;

@Component({
  selector: 'app-sensor-form', standalone: true, imports: [ReactiveFormsModule],
  templateUrl: './sensor-form.component.html', styleUrl: './sensor-form.component.scss', changeDetection: ChangeDetectionStrategy.OnPush
})
export class SensorFormComponent {
  readonly initialParents = input<SensorParents | null>(null);
  readonly companies = input<readonly SensorParentOption[]>([]);
  readonly sites = input<readonly SensorParentOption[]>([]);
  readonly equipments = input<readonly SensorParentOption[]>([]);
  readonly verifiedCompanyId = input<number | null>(null);
  readonly verifiedSiteId = input<number | null>(null);
  readonly verifiedEquipmentId = input<number | null>(null);
  readonly saving = input(false);
  readonly blocked = input(false);
  readonly fieldErrors = input<SensorFieldErrors>({});
  readonly companyChanged = output<number | null>();
  readonly siteChanged = output<number | null>();
  readonly equipmentChanged = output<number | null>();
  readonly submitted = output<SensorCreate>();
  readonly cancelled = output<void>();
  readonly edited = output<void>();
  private readonly element = viewChild.required<ElementRef<HTMLFormElement>>('formElement');
  private baseline: SensorParents = { company_id: null, site_id: null, equipment_id: null };
  readonly statusLabels = { active: 'Actif', inactive: 'Inactif' } as const;
  readonly statuses: SensorStatus[] = ['active', 'inactive'];
  readonly textFields = [ { key: 'name', label: 'Nom', limit: 150 }, { key: 'code', label: 'Code métier', limit: 100 },
    { key: 'sensor_type', label: 'Type de capteur', limit: 100 }, { key: 'unit', label: 'Unité', limit: 30 } ] as const;
  readonly parentFields = [ { key: 'company_id', label: 'Entreprise' }, { key: 'site_id', label: 'Site industriel' },
    { key: 'equipment_id', label: 'Équipement industriel' } ] as const;
  readonly fieldOrder: readonly SensorField[] = ['company_id', 'site_id', 'equipment_id', 'name', 'code', 'sensor_type', 'unit', 'status', 'description'];
  readonly form = new FormGroup({
    company_id: new FormControl<number | null>(null, requiredId), site_id: new FormControl<number | null>(null, requiredId),
    equipment_id: new FormControl<number | null>(null, requiredId),
    name: new FormControl('', { nonNullable: true, validators: textLimit(150) }),
    code: new FormControl('', { nonNullable: true, validators: textLimit(100) }),
    sensor_type: new FormControl('', { nonNullable: true, validators: textLimit(100) }),
    unit: new FormControl('', { nonNullable: true, validators: textLimit(30) }),
    status: new FormControl<SensorStatus>('active', { nonNullable: true,
      validators: control => ['active', 'inactive'].includes(control.value) ? null : { enum: true } }),
    description: new FormControl<string | null>(null)
  });
  constructor() {
    const destroy = inject(DestroyRef);
    effect(() => {
      const parents = this.initialParents();
      if (parents && this.parentFields.every(field => !this.form.controls[field.key].dirty)) {
        this.form.patchValue(parents, { emitEvent: false }); this.baseline = { ...parents };
      }
    });
    effect(() => {
      const controls = this.form.controls;
      if (this.verifiedCompanyId() !== null && controls.company_id.value === this.verifiedCompanyId()) controls.site_id.enable({ emitEvent: false });
      else controls.site_id.disable({ emitEvent: false });
      if (this.verifiedSiteId() !== null && controls.site_id.value === this.verifiedSiteId()
        && controls.company_id.value === this.verifiedCompanyId()) controls.equipment_id.enable({ emitEvent: false });
      else controls.equipment_id.disable({ emitEvent: false });
    });
    this.form.controls.company_id.valueChanges.pipe(takeUntilDestroyed(destroy)).subscribe(id => {
      this.form.controls.site_id.setValue(null, { emitEvent: false }); this.form.controls.equipment_id.setValue(null, { emitEvent: false }); this.companyChanged.emit(id);
    });
    this.form.controls.site_id.valueChanges.pipe(takeUntilDestroyed(destroy)).subscribe(id => {
      this.form.controls.equipment_id.setValue(null, { emitEvent: false }); this.siteChanged.emit(id);
    });
    this.form.controls.equipment_id.valueChanges.pipe(takeUntilDestroyed(destroy)).subscribe(id => this.equipmentChanged.emit(id));
    this.form.valueChanges.pipe(takeUntilDestroyed(destroy)).subscribe(() => this.edited.emit());
  }
  options(field: keyof SensorParents): readonly SensorParentOption[] { return field === 'company_id' ? this.companies() : field === 'site_id' ? this.sites() : this.equipments(); }
  verified(field: keyof SensorParents): number | null { return field === 'company_id' ? this.verifiedCompanyId() : field === 'site_id' ? this.verifiedSiteId() : this.verifiedEquipmentId(); }
  hasChanges(): boolean {
    const value = this.form.getRawValue();
    return this.parentFields.some(field => value[field.key] !== this.baseline[field.key])
      || this.textFields.some(field => value[field.key] !== '') || value.status !== 'active' || this.form.controls.description.dirty;
  }
  focusField(field: SensorField): void { this.element().nativeElement.querySelector<HTMLElement>(`#sensor-${field}`)?.focus(); }
  error(field: SensorField): string {
    const control = this.form.controls[field];
    if (control.touched) {
      if (this.parentFields.some(parent => parent.key === field) && (control.value === null || control.value !== this.verified(field as keyof SensorParents)))
        return 'Sélectionnez une référence disponible et vérifiée dans ce rattachement.';
      if (control.hasError('required')) return 'Ce champ est obligatoire et ne doit pas être blanc.';
      if (control.hasError('maxlength')) return `${this.textFields.find(item => item.key === field)?.limit} caractères Unicode maximum.`;
      if (control.hasError('enum')) return 'Sélectionnez une valeur proposée.';
    }
    return this.fieldErrors()[field] ?? '';
  }
  removeDescription(): void { this.form.controls.description.setValue(null); this.form.controls.description.markAsDirty(); this.focusField('description'); }
  submit(): void {
    if (this.saving() || this.blocked()) return;
    this.form.markAllAsTouched(); const value = this.form.getRawValue();
    const first = this.fieldOrder.find(field => this.form.controls[field].invalid ||
      (this.parentFields.some(parent => parent.key === field) && (value[field as keyof SensorParents] === null || value[field as keyof SensorParents] !== this.verified(field as keyof SensorParents))));
    if (first) { this.focusField(first); return; }
    this.submitted.emit({ equipment_id: value.equipment_id!, name: value.name.trim(), code: value.code.trim(),
      sensor_type: value.sensor_type.trim(), unit: value.unit.trim(), status: value.status,
      ...(this.form.controls.description.dirty ? { description: value.description } : {}) });
  }
}
