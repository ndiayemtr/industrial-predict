import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, WritableSignal, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { EMPTY, Observable, Subject, catchError, merge, switchMap, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { Page } from '../../../../core/models/page.model';
import { CompanyRead, EquipmentRead, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { SensorRead } from '../../../sensors/models/sensor.model';
import { SensorsApiService } from '../../../sensors/data-access/sensors-api.service';
import { MeasurementQuality } from '../../models/measurement.model';
import { formatMeasurementUtc, validateMeasurementPeriod } from '../../utils/measurement-time';
import { restoreMeasurementBound, serializeMeasurementBound } from '../../utils/measurement-period-draft';
import { MeasurementsQuery } from '../../models/measurements-state.model';
import { MeasurementsListFacade } from '../../measurements-list.facade';

type Catalog<T> = Page<T> & { scope: number | null; status: 'idle' | 'loading' | 'ready' | 'error'; requestedPage: number; retryable: boolean };
type CatalogRequest = { scope: number | null; page: number } | null;
const catalog = <T>(): Catalog<T> => ({ items: [], total: 0, page: 0, page_size: 50, pages: 0,
  scope: null, status: 'idle', requestedPage: 1, retryable: false });
const positive = (raw: string | null, fallback?: number, maximum = Number.MAX_SAFE_INTEGER) =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= maximum ? Number(raw) : fallback;
const keys = ['company_id', 'site_id', 'equipment_id', 'sensor_id', 'page', 'page_size', 'quality', 'start_time', 'end_time'] as const;
const same = (a: Readonly<MeasurementsQuery> | null, b: MeasurementsQuery) => a !== null && keys.every(key => a[key] === b[key]);

@Component({
  selector: 'app-measurements-list', standalone: true,
  imports: [ReactiveFormsModule, PageHeaderComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent],
  providers: [MeasurementsListFacade], templateUrl: './measurements-list.component.html',
  styleUrl: './measurements-list.component.scss', changeDetection: ChangeDetectionStrategy.OnPush
})
export class MeasurementsListComponent {
  readonly facade = inject(MeasurementsListFacade);
  private readonly sensorsApi = inject(SensorsApiService);
  private readonly sensorRequests = new Subject<CatalogRequest>();
  readonly sensors = signal(catalog<SensorRead>());
  readonly sensor = new FormControl<number | null>({ value: null, disabled: true });
  readonly start = this.boundForm();
  readonly end = this.boundForm();
  private startBaseline = restoreMeasurementBound();
  private endBaseline = restoreMeasurementBound();
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly periodError = signal('');
  readonly formatTime = formatMeasurementUtc;
  private readonly references = inject(ReferenceDataApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly companyRequests = new Subject<CatalogRequest>();
  private readonly siteRequests = new Subject<CatalogRequest>();
  private readonly equipmentRequests = new Subject<CatalogRequest>();
  readonly companies = signal(catalog<CompanyRead>());
  readonly sites = signal(catalog<SiteRead>());
  readonly equipments = signal(catalog<EquipmentRead>());
  readonly company = new FormControl<number | null>(null);
  readonly site = new FormControl<number | null>({ value: null, disabled: true });
  readonly equipment = new FormControl<number | null>({ value: null, disabled: true });
  readonly quality = new FormControl<MeasurementQuality | ''>('', { nonNullable: true });
  readonly size = new FormControl(20, { nonNullable: true });
  readonly urlNotice = signal('');
  readonly referenceLabel = businessReferenceLabel;
  readonly qualityLabels: Record<MeasurementQuality,string> = { good: 'Bonne', suspect: 'Suspecte', bad: 'Mauvaise', missing: 'Manquante', estimated: 'Estimée' };
  readonly qualities = Object.keys(this.qualityLabels) as MeasurementQuality[];
  readonly sensorOptions = computed(() => this.options(this.sensors().items, this.facade.sensor()).filter(item => item.equipment_id === this.sensors().scope));
  readonly companyOptions = computed(() => this.options(this.companies().items, this.facade.company()));
  readonly siteOptions = computed(() => this.options(this.sites().items, this.facade.site()).filter(item => item.company_id === this.sites().scope));
  readonly equipmentOptions = computed(() => this.options(this.equipments().items, this.facade.equipment()).filter(item => item.site_id === this.equipments().scope));
  readonly busy = computed(() => this.facade.state().status === 'loading');
  readonly canFilter = computed(() => this.facade.equipment() !== null && this.facade.site() !== null && this.facade.company() !== null && this.facade.sensor() !== null);
  readonly page = computed(() => this.facade.query()?.page ?? 1);
  readonly pageSize = computed(() => this.facade.query()?.page_size ?? 20);
  readonly sizes = computed(() => [...new Set([20, 50, 100, this.pageSize()])].sort((a, b) => a - b));
  readonly filtered = computed(() => !!(this.facade.query()?.start_time || this.facade.query()?.end_time || this.facade.query()?.quality));
  readonly canNext = computed(() => { const state = this.facade.state(); return state.status === 'success' && this.page() < state.data.pages; });

  constructor() {
    this.connectCatalog(this.sensorRequests, this.sensors, (scope, page) => this.sensorsApi.list({ equipment_id: scope!, page, page_size: 50 }).pipe(tap(data => {
      if (data.items.some(item => item.equipment_id !== scope)) throw new Error('Incoherent sensor catalog');
    })));
    this.sensor.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => this.changeParent('sensor_id', id));
    this.connectCatalog(this.companyRequests, this.companies, (_, page) => this.references.getCompanies({ page, page_size: 50 }));
    this.connectCatalog(this.siteRequests, this.sites, (scope, page) => this.references.getSites(scope!, { page, page_size: 50 }).pipe(tap(data => {
      if (data.items.some(item => item.company_id !== scope)) throw new Error('Incoherent site catalog');
    })));
    this.connectCatalog(this.equipmentRequests, this.equipments, (scope, page) => this.references.getEquipments(scope!, { page, page_size: 50 }).pipe(tap(data => {
      if (data.items.some(item => item.site_id !== scope)) throw new Error('Incoherent equipment catalog');
    })));
    this.companyRequests.next({ scope: null, page: 1 });
    this.company.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => this.changeParent('company_id', id));
    this.site.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => this.changeParent('site_id', id));
    this.equipment.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => this.changeParent('equipment_id', id));
    merge(this.quality.valueChanges, this.size.valueChanges).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      const query = this.facade.query() ?? { company_id: this.company.value ?? undefined, site_id: this.site.value ?? undefined,
        equipment_id: this.equipment.value ?? undefined, sensor_id: this.sensor.value ?? undefined,
        start_time: this.route.snapshot.queryParamMap.get('start_time') ?? undefined, end_time: this.route.snapshot.queryParamMap.get('end_time') ?? undefined, page: 1, page_size: this.size.value };
      this.urlNotice.set('');
      void this.navigate({ ...query, quality: this.quality.value || undefined, page_size: this.size.value, page: 1 });
    });
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const companyId = positive(params.get('company_id')), siteId = positive(params.get('site_id')), equipmentId = positive(params.get('equipment_id')), sensorId = positive(params.get('sensor_id'));
      if (['company_id', 'site_id', 'equipment_id', 'sensor_id'].some(key => params.has(key) && positive(params.get(key)) === undefined)) {
        this.facade.load(null); this.urlNotice.set('Le périmètre de l’URL est invalide. Sélectionnez une entreprise, un site un équipement et un capteur valides.');
        this.company.setValue(null, { emitEvent: false }); this.site.setValue(null, { emitEvent: false }); this.equipment.setValue(null, { emitEvent: false }); this.sensor.setValue(null, { emitEvent: false });
        return;
      }
      const start = params.get('start_time') ?? '', end = params.get('end_time') ?? '';
      this.restorePeriod(params.has('start_time') ? start : undefined, params.has('end_time') ? end : undefined);
      const query: MeasurementsQuery = { company_id: companyId, site_id: siteId, equipment_id: equipmentId, sensor_id: sensorId,
        page: positive(params.get('page'), 1)!, page_size: positive(params.get('page_size'), 20, 100)!,
        quality: this.qualities.find(value => value === params.get('quality')), start_time: params.has('start_time') ? start : undefined, end_time: params.has('end_time') ? end : undefined };
      this.sensor.setValue(sensorId ?? null, { emitEvent: false });
      this.quality.setValue(query.quality ?? '', { emitEvent: false }); this.size.setValue(query.page_size, { emitEvent: false });
      this.company.setValue(companyId ?? null, { emitEvent: false }); this.site.setValue(siteId ?? null, { emitEvent: false }); this.equipment.setValue(equipmentId ?? null, { emitEvent: false });
      if (params.has('quality') && !query.quality) {
        this.facade.load(null); this.urlNotice.set('La qualité de l’URL est invalide. Choisissez une qualité reconnue.'); return;
      }
      try { validateMeasurementPeriod(query.start_time, query.end_time); } catch {
        this.periodError.set('Période invalide : vérifiez les dates et heures UTC, puis le début strictement antérieur à la fin.');
        this.facade.load(query); return;
      }
      this.periodError.set('');
      const invalid = ['page','page_size'].some(key => params.has(key) && params.get(key) !== String(query[key as 'page' | 'page_size']));
      if (invalid) { this.facade.load(null); this.urlNotice.set('La pagination de l’URL a été normalisée.'); void this.navigate(query, true); return; }
      this.company.setValue(companyId ?? null, { emitEvent: false }); this.site.setValue(siteId ?? null, { emitEvent: false });
      this.equipment.setValue(equipmentId ?? null, { emitEvent: false });
      this.quality.setValue(query.quality ?? '', { emitEvent: false }); this.size.setValue(query.page_size, { emitEvent: false });
      if (!same(this.facade.query(), query)) this.facade.load(query);
    });
    effect(() => {
      const company = this.facade.company(), site = this.facade.site(), query = this.facade.query();
      if (company) this.site.enable({ emitEvent: false }); else this.site.disable({ emitEvent: false });
      if (company && site) this.equipment.enable({ emitEvent: false }); else this.equipment.disable({ emitEvent: false });
      if (company && site && this.facade.equipment()) this.sensor.enable({ emitEvent: false }); else this.sensor.disable({ emitEvent: false });
      this.ensureCatalog(this.sensorRequests, this.sensors(), this.facade.equipment()?.id);
      this.ensureCatalog(this.siteRequests, this.sites(), company?.id);
      this.ensureCatalog(this.equipmentRequests, this.equipments(), site?.id);
      if (query && company && ((!this.route.snapshot.queryParamMap.has('company_id')) || (site && !this.route.snapshot.queryParamMap.has('site_id')) || (this.facade.equipment() && !this.route.snapshot.queryParamMap.has('equipment_id'))))
        void this.navigate(query, true);
    });
  }

  private changeParent(field: 'company_id' | 'site_id' | 'equipment_id' | 'sensor_id', id: number | null): void {
    this.urlNotice.set('');
    const query: MeasurementsQuery = { company_id: this.company.value ?? undefined, site_id: this.site.value ?? undefined,
      equipment_id: this.equipment.value ?? undefined, sensor_id: this.sensor.value ?? undefined, quality: this.quality.value || undefined, page: 1, page_size: this.size.value };
    if (field === 'company_id') {
      query.site_id = undefined; this.site.setValue(null, { emitEvent: false }); this.siteRequests.next(null);
    }
    if (field === 'company_id' || field === 'site_id') {
      query.equipment_id = undefined; this.equipment.setValue(null, { emitEvent: false }); this.equipmentRequests.next(null);
    }
    if (field !== 'sensor_id') { query.sensor_id = undefined; this.sensor.setValue(null, { emitEvent: false }); this.sensorRequests.next(null); }
    query[field] = id ?? undefined;
    this.restorePeriod(); this.periodError.set(''); this.facade.load(query); void this.navigate(query);
  }
  private options<T extends { id: number }>(items: T[], selected: T | null): T[] {
    return [...new Map([...items, ...(selected ? [selected] : [])].map(item => [item.id, item])).values()];
  }
  private connectCatalog<T extends { id: number }>(requests: Subject<CatalogRequest>, target: WritableSignal<Catalog<T>>,
    fetch: (scope: number | null, page: number) => Observable<Page<T>>): void {
    requests.pipe(switchMap(request => {
      if (!request) { target.set(catalog<T>()); return EMPTY; }
      const previous = request.page > 1 && target().scope === request.scope ? target() : catalog<T>();
      target.set({ ...previous, scope: request.scope, status: 'loading', requestedPage: request.page });
      return fetch(request.scope, request.page).pipe(tap(data => target.set({ ...data, scope: request.scope,
        items: this.options([...previous.items, ...data.items], null), status: 'ready', requestedPage: request.page, retryable: false })),
      catchError((error: unknown) => {
        const status = error instanceof HttpErrorResponse ? error.status : -1;
        target.set({ ...previous, scope: request.scope, status: 'error', requestedPage: request.page, retryable: status === 0 || status >= 500 }); return EMPTY;
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }
  private ensureCatalog<T>(requests: Subject<CatalogRequest>, current: Catalog<T>, scope: number | undefined): void {
    if (scope === undefined) { if (current.status !== 'idle') requests.next(null); }
    else if (current.scope !== scope) requests.next({ scope, page: 1 });
  }
  moreSensors(): void { this.more(this.sensorRequests, this.sensors()); }
  retrySensors(): void { this.retryCatalog(this.sensorRequests, this.sensors()); }
  moreCompanies(): void { this.more(this.companyRequests, this.companies()); }
  moreSites(): void { this.more(this.siteRequests, this.sites()); }
  moreEquipments(): void { this.more(this.equipmentRequests, this.equipments()); }
  retryCompanies(): void { this.retryCatalog(this.companyRequests, this.companies()); }
  retrySites(): void { this.retryCatalog(this.siteRequests, this.sites()); }
  retryEquipments(): void { this.retryCatalog(this.equipmentRequests, this.equipments()); }
  private more<T>(requests: Subject<CatalogRequest>, current: Catalog<T>): void {
    if (current.status === 'ready' && current.page < current.pages) requests.next({ scope: current.scope, page: current.page + 1 });
  }
  private retryCatalog<T>(requests: Subject<CatalogRequest>, current: Catalog<T>): void {
    if (current.status === 'error' && current.retryable) requests.next({ scope: current.scope, page: current.requestedPage });
  }
  applyPeriod(event?: Event): void {
    event?.preventDefault();
    try {
      // A partially entered native date/time can have an empty value but badInput=true.
      if ([...this.element.nativeElement.querySelectorAll<HTMLInputElement>('.period-bound input')].some(input => !input.validity.valid))
        throw new TypeError('Invalid native date or time input.');
      const start = serializeMeasurementBound(this.start.getRawValue(), this.startBaseline);
      const end = serializeMeasurementBound(this.end.getRawValue(), this.endBaseline);
      validateMeasurementPeriod(start, end);
      this.periodError.set(''); const query = this.facade.query();
      if (query) void this.navigate({ ...query, start_time: start, end_time: end, page: 1 });
    } catch {
      this.periodError.set('Période invalide : renseignez une date et une heure UTC par borne, 0 à 6 chiffres de fraction, et un début strictement antérieur à la fin.');
      // Focus an existing control immediately; aria-invalid is updated in the same rendering turn.
      this.element.nativeElement.querySelector<HTMLInputElement>('#measurements-start-date')?.focus();
    }
  }
  private boundForm() {
    return new FormGroup({ date: new FormControl('', { nonNullable: true }),
      time: new FormControl('', { nonNullable: true }), fraction: new FormControl('', { nonNullable: true }) });
  }
  private restorePeriod(start?: string, end?: string): void {
    this.startBaseline = restoreMeasurementBound(start); this.endBaseline = restoreMeasurementBound(end);
    this.start.setValue(this.startBaseline.parts, { emitEvent: false }); this.end.setValue(this.endBaseline.parts, { emitEvent: false });
  }
  companyVerified(): boolean { return this.company.value !== null && this.facade.company()?.id === this.company.value; }
  siteVerified(): boolean { return this.companyVerified() && this.facade.site()?.id === this.site.value && this.facade.site()?.company_id === this.company.value; }
  equipmentVerified(): boolean { return this.siteVerified() && this.facade.equipment()?.id === this.equipment.value && this.facade.equipment()?.site_id === this.site.value; }
  sensorVerified(): boolean { return this.equipmentVerified() && this.facade.sensor()?.id === this.sensor.value && this.facade.sensor()?.equipment_id === this.equipment.value; }
  clearFilters(): void {
    this.restorePeriod(); this.periodError.set(''); this.urlNotice.set('');
    const query = this.facade.query();
    const scope = query ?? { company_id: this.company.value ?? undefined, site_id: this.site.value ?? undefined,
      equipment_id: this.equipment.value ?? undefined, sensor_id: this.sensor.value ?? undefined, page: 1, page_size: this.size.value };
    void this.navigate({ ...scope, quality: undefined, start_time: undefined, end_time: undefined, page: 1 });
  }
  changePage(page: number): void {
    const query = this.facade.query();
    if (query && !this.busy() && page >= 1 && (page <= this.page() || this.canNext())) void this.navigate({ ...query, page });
  }
  recoverPage(): void { const query = this.facade.query(), state = this.facade.state();
    if (query && state.status === 'success' && !state.data.items.length) void this.navigate({ ...query, page: Math.max(1, Math.min(query.page - 1, state.data.pages)) });
  }
  formatValue(value: number): string { return (Object.is(value, -0) ? '-0' : String(value)).replace('.', ','); }
  detailUrl(id: number): string {
    return this.router.serializeUrl(this.router.createUrlTree(['/measurements', id], { queryParams: this.facade.query() }));
  }
  private navigate(query: MeasurementsQuery, replaceUrl = false): Promise<boolean> {
    return this.router.navigate([], { relativeTo: this.route, queryParams: { company_id: query.company_id ?? null,
      site_id: query.site_id ?? null, equipment_id: query.equipment_id ?? null, sensor_id: query.sensor_id ?? null, quality: query.quality ?? null, start_time: query.start_time ?? null, end_time: query.end_time ?? null,
      page: query.page, page_size: query.page_size }, queryParamsHandling: 'merge', preserveFragment: true, replaceUrl });
  }
}
