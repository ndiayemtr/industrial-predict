import { ChangeDetectionStrategy, Component, DestroyRef, WritableSignal, computed, inject, output, signal } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { AbstractControl, FormControl, FormGroup, ReactiveFormsModule, ValidationErrors, Validators } from '@angular/forms';
import { EMPTY, Observable, Subject, catchError, map, startWith, switchMap, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { Page } from '../../../../core/models/page.model';
import { CompanyRead, EquipmentRead, SiteRead } from '../../../../core/models/reference-data.model';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { DashboardFilters } from '../../models/dashboard-filters.model';

interface ReferenceRequest { parent: number | null; page: number }
interface ReferenceList<T> extends Page<T> {
  status: 'idle' | 'loading' | 'ready' | 'error';
  requestedPage: number;
}
const PAGE_SIZE = 50;
const WEEK = 168 * 60 * 60 * 1000;
const wholeMinute = (instant: number) => Math.floor(instant / 60_000) * 60_000;
const minuteValue = (instant: number) => new Date(instant).toISOString().slice(0, 16);
function hasSubminutePrecision(value: string): boolean {
  const match = /T\d{2}:\d{2}:(\d{2})(?:\.(\d+))?$/.exec(value);
  return !!match && (Number(match[1]) !== 0 || /[1-9]/.test(match[2] ?? ''));
}
function emptyList<T>(): ReferenceList<T> {
  return { items: [], total: 0, page: 0, page_size: PAGE_SIZE, pages: 0, status: 'idle', requestedPage: 1 };
}

// datetime-local is deliberately interpreted as UTC, never as the browser timezone.
function utcDate(value: string): Date | undefined {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?$/.test(value)) return undefined;
  const date = new Date(`${value}Z`);
  if (!Number.isFinite(date.getTime())) return undefined;
  const withSeconds = value.length === 16 ? `${value}:00` : value;
  const [seconds, fraction = ''] = withSeconds.split('.');
  if (date.toISOString() !== `${seconds}.${fraction.padEnd(3, '0')}Z`) return undefined;
  return date;
}

function periodValidator(group: AbstractControl): ValidationErrors | null {
  const start = utcDate(group.get('start_time')?.value ?? '');
  const end = utcDate(group.get('end_time')?.value ?? '');
  if (!start || !end) return { invalidDate: true };
  if (start.getTime() >= end.getTime()) return { invalidPeriod: true };
  if (end.getTime() > Date.now()) return { futureEnd: true };
  return null;
}

@Component({
  selector: 'app-dashboard-filters',
  standalone: true,
  imports: [ReactiveFormsModule, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './dashboard-filters.component.html',
  styleUrl: './dashboard-filters.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DashboardFiltersComponent {
  private readonly api = inject(ReferenceDataApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly initialEnd = wholeMinute(Date.now());
  private readonly precisionRequested = signal(false);
  readonly precisionConversionPending = signal(false);
  readonly precisionNotice = signal('');
  readonly filtersApplied = output<DashboardFilters>();
  readonly form = new FormGroup({
    company_id: new FormControl<number | null>(null, [Validators.required, Validators.min(1)]),
    site_id: new FormControl<number | null>({ value: null, disabled: true }),
    equipment_id: new FormControl<number | null>({ value: null, disabled: true }),
    start_time: new FormControl(minuteValue(this.initialEnd - WEEK), { nonNullable: true }),
    end_time: new FormControl(minuteValue(this.initialEnd), { nonNullable: true })
  }, { validators: periodValidator });
  readonly companies = signal(emptyList<CompanyRead>());
  readonly sites = signal(emptyList<SiteRead>());
  readonly equipments = signal(emptyList<EquipmentRead>());
  private readonly companyRequests = new Subject<ReferenceRequest>();
  private readonly siteRequests = new Subject<ReferenceRequest>();
  private readonly equipmentRequests = new Subject<ReferenceRequest>();
  private readonly values = toSignal(this.form.valueChanges.pipe(
    map(() => this.form.getRawValue()), startWith(this.form.getRawValue())
  ), { requireSync: true });
  // Loading precise values activates the native precise control without rewriting them.
  readonly advancedPrecision = computed(() => this.precisionRequested()
    || hasSubminutePrecision(this.values().start_time) || hasSubminutePrecision(this.values().end_time));
  readonly canApply = computed(() => {
    const value = this.values();
    const company = this.companies();
    const sites = this.sites();
    const equipments = this.equipments();
    return !this.precisionConversionPending() && this.form.valid && company.status === 'ready'
      && company.items.some((item) => item.id === value.company_id)
      && (value.company_id == null || sites.status === 'ready')
      && (value.site_id == null || sites.items.some((item) => item.id === value.site_id && item.company_id === value.company_id))
      && (value.site_id == null || equipments.status === 'ready')
      && (value.equipment_id == null || equipments.items.some((item) => item.id === value.equipment_id && item.site_id === value.site_id));
  });

  constructor() {
    this.form.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      if (hasSubminutePrecision(this.form.controls.start_time.value) || hasSubminutePrecision(this.form.controls.end_time.value)) {
        this.precisionRequested.set(true);
      }
    });
    this.connect(this.companyRequests, this.companies, this.form.controls.company_id,
      (_, page) => this.api.getCompanies({ page, page_size: PAGE_SIZE }));
    this.connect(this.siteRequests, this.sites, this.form.controls.site_id,
      (id, page) => this.api.getSites(id, { page, page_size: PAGE_SIZE }));
    this.connect(this.equipmentRequests, this.equipments, this.form.controls.equipment_id,
      (id, page) => this.api.getEquipments(id, { page, page_size: PAGE_SIZE }));
    this.form.controls.company_id.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((id) => {
      this.form.controls.site_id.setValue(null, { emitEvent: false });
      this.form.controls.equipment_id.setValue(null, { emitEvent: false });
      this.equipmentRequests.next({ parent: null, page: 1 });
      this.siteRequests.next({ parent: id, page: 1 });
    });
    this.form.controls.site_id.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((id) => {
      this.form.controls.equipment_id.setValue(null, { emitEvent: false });
      this.equipmentRequests.next({ parent: id, page: 1 });
    });
    this.companyRequests.next({ parent: 0, page: 1 });
  }

  loadCompanies(page: number): void { this.companyRequests.next({ parent: 0, page }); }
  loadSites(page: number): void { this.siteRequests.next({ parent: this.form.controls.company_id.value, page }); }
  loadEquipments(page: number): void { this.equipmentRequests.next({ parent: this.form.controls.site_id.value, page }); }

  changePrecision(event: Event): void {
    const checkbox = event.target as HTMLInputElement;
    this.precisionNotice.set('');
    if (checkbox.checked) {
      this.precisionRequested.set(true);
      this.precisionConversionPending.set(false);
    } else if (hasSubminutePrecision(this.form.controls.start_time.value)
      || hasSubminutePrecision(this.form.controls.end_time.value)) {
      this.precisionConversionPending.set(true);
      checkbox.checked = true;
    } else {
      this.useMinutePrecision();
    }
  }

  canConvertToMinutes(): boolean {
    return !!utcDate(this.form.controls.start_time.value) && !!utcDate(this.form.controls.end_time.value);
  }

  confirmMinutePrecision(): void {
    if (!this.precisionConversionPending() || !this.canConvertToMinutes()) return;
    this.form.controls.start_time.markAsDirty();
    this.form.controls.end_time.markAsDirty();
    this.useMinutePrecision();
    this.precisionNotice.set('Les deux bornes ont été ramenées à la minute inférieure. Vérifiez la période avant de l’appliquer.');
  }

  keepAdvancedPrecision(): void {
    this.precisionRequested.set(true);
    this.precisionConversionPending.set(false);
    this.precisionNotice.set('Précision avancée conservée. Les dates sont inchangées.');
  }

  private useMinutePrecision(): void {
    for (const control of [this.form.controls.start_time, this.form.controls.end_time]) {
      if (utcDate(control.value)) control.setValue(control.value.slice(0, 16));
    }
    this.precisionRequested.set(false);
    this.precisionConversionPending.set(false);
  }

  applyFilters(): void {
    if (this.precisionConversionPending()) return;
    // Finalize the untouched initial preset at application time; preserve custom dates.
    if (this.form.controls.start_time.pristine && this.form.controls.end_time.pristine
      && this.form.controls.start_time.value === minuteValue(this.initialEnd - WEEK)
      && this.form.controls.end_time.value === minuteValue(this.initialEnd)) {
      const precise = this.advancedPrecision();
      const end = precise ? Date.now() : wholeMinute(Date.now());
      const value = (instant: number) => precise ? new Date(instant).toISOString().slice(0, -1) : minuteValue(instant);
      this.form.patchValue({ start_time: value(end - WEEK), end_time: value(end) });
    }
    // Revalidate against the current clock on submission; no timer changes the chosen period.
    this.form.updateValueAndValidity();
    this.form.markAllAsTouched();
    if (!this.canApply()) return;
    const value = this.form.getRawValue();
    const start = utcDate(value.start_time);
    const end = utcDate(value.end_time);
    if (value.company_id == null || !start || !end) return;
    this.filtersApplied.emit({
      company_id: value.company_id, start_time: start.toISOString(), end_time: end.toISOString(),
      ...(value.site_id != null ? { site_id: value.site_id } : {}),
      ...(value.equipment_id != null ? { equipment_id: value.equipment_id } : {})
    });
  }

  private connect<T extends { id: number }>(
    requests: Subject<ReferenceRequest>, state: WritableSignal<ReferenceList<T>>,
    control: FormControl<number | null>, fetch: (parent: number, page: number) => Observable<Page<T>>
  ): void {
    requests.pipe(switchMap((request) => {
      control.disable({ emitEvent: false });
      if (request.parent == null) { state.set(emptyList<T>()); return EMPTY; }
      const previous = request.page > 1 ? state() : emptyList<T>();
      state.set({ ...previous, status: 'loading', requestedPage: request.page });
      return fetch(request.parent, request.page).pipe(tap((response) => {
        const items = [...new Map([...previous.items, ...response.items].map((item) => [item.id, item])).values()];
        state.set({ ...response, items, status: 'ready', requestedPage: request.page });
        control.enable({ emitEvent: false });
      }), catchError(() => {
        state.set({ ...previous, status: 'error', requestedPage: request.page });
        if (previous.items.length) control.enable({ emitEvent: false });
        return EMPTY;
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }
}
