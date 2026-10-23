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
import { MaintenancePriority, MaintenanceStatus, MaintenanceType } from '../../models/maintenance.model';
import { validateMeasurementPeriod } from '../../../measurements/utils/measurement-time';
import { restoreMeasurementBound, serializeMeasurementBound } from '../../../measurements/utils/measurement-period-draft';
import { MaintenanceQuery } from '../../models/maintenance-state.model';
import { MaintenanceListFacade } from '../../maintenance-list.facade';

type Catalog<T> = Page<T> & { scope: number | null; status: 'idle' | 'loading' | 'ready' | 'error'; requestedPage: number; retryable: boolean };
type CatalogRequest = { scope: number | null; page: number } | null;
const catalog = <T>(): Catalog<T> => ({ items: [], total: 0, page: 0, page_size: 50, pages: 0,
  scope: null, status: 'idle', requestedPage: 1, retryable: false });
const positive = (raw: string | null, fallback?: number, maximum = Number.MAX_SAFE_INTEGER) =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= maximum ? Number(raw) : fallback;
const keys = ['company_id', 'site_id', 'equipment_id', 'page', 'page_size', 'maintenance_type', 'status', 'priority', 'search', 'start_time', 'end_time'] as const;
const same = (a: Readonly<MaintenanceQuery> | null, b: MaintenanceQuery) => a !== null && keys.every(key => a[key] === b[key]);

@Component({
  selector: 'app-maintenance-list', standalone: true,
  imports: [ReactiveFormsModule, PageHeaderComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent],
  providers: [MaintenanceListFacade], templateUrl: './maintenance-list.component.html',
  styleUrl: './maintenance-list.component.scss', changeDetection: ChangeDetectionStrategy.OnPush
})
export class MaintenanceListComponent {
  readonly facade = inject(MaintenanceListFacade);
  readonly start = this.boundForm();
  readonly end = this.boundForm();
  private startBaseline = restoreMeasurementBound();
  private endBaseline = restoreMeasurementBound();
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  readonly periodError = signal('');
  readonly fieldErrors = signal<Readonly<Record<string, string>>>({});
  readonly periodDraft = signal(false);
  readonly searchDraft = signal(false);
  private searchBaseline = '';
  readonly formatTime = (raw: string | null): string => raw === null ? 'Non renseignée'
    : raw + (/(Z|[+-]\d{2}:\d{2})$/.test(raw) ? ' (offset fourni)' : ' (fuseau non fourni)');
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
  readonly maintenanceType = new FormControl<MaintenanceType | ''>('', { nonNullable: true });
  readonly status = new FormControl<MaintenanceStatus | ''>('', { nonNullable: true });
  readonly priority = new FormControl<MaintenancePriority | ''>('', { nonNullable: true });
  readonly search = new FormControl('', { nonNullable: true });
  readonly searchError = signal('');
  readonly size = new FormControl(20, { nonNullable: true });
  readonly urlNotice = signal('');
  readonly referenceLabel = businessReferenceLabel;
  readonly typeLabels = { preventive: 'Préventive', corrective: 'Corrective', predictive: 'Prédictive' } as const;
  readonly statusLabels = { planned: 'Planifiée', in_progress: 'En cours', completed: 'Terminée', cancelled: 'Annulée' } as const;
  readonly priorityLabels = { low: 'Basse', medium: 'Moyenne', high: 'Haute', critical: 'Critique' } as const;
  readonly types = Object.keys(this.typeLabels) as MaintenanceType[];
  readonly statuses = Object.keys(this.statusLabels) as MaintenanceStatus[];
  readonly priorities = Object.keys(this.priorityLabels) as MaintenancePriority[];
  readonly companyOptions = computed(() => this.options(this.companies().items, this.facade.company()));
  readonly siteOptions = computed(() => this.options(this.sites().items, this.facade.site()).filter(item => item.company_id === this.sites().scope));
  readonly equipmentOptions = computed(() => this.options(this.equipments().items, this.facade.equipment()).filter(item => item.site_id === this.equipments().scope));
  readonly busy = computed(() => this.facade.state().status === 'loading');
  readonly canFilter = computed(() => this.facade.equipment() !== null && this.facade.site() !== null && this.facade.company() !== null);
  readonly page = computed(() => this.facade.query()?.page ?? 1);
  readonly pageSize = computed(() => this.facade.query()?.page_size ?? 20);
  readonly sizes = computed(() => [...new Set([20, 50, 100, this.pageSize()])].sort((a, b) => a - b));
  readonly filtered = computed(() => !!(this.facade.query()?.start_time || this.facade.query()?.end_time || this.facade.query()?.search || this.facade.query()?.maintenance_type || this.facade.query()?.status || this.facade.query()?.priority));
  readonly canNext = computed(() => { const state = this.facade.state(); return state.status === 'success' && this.page() < state.data.pages; });

  constructor() {
    merge(this.start.valueChanges, this.end.valueChanges).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      const normalized = (parts: { date: string; time: string; fraction: string }) =>
        JSON.stringify({ ...parts, time: /^\d{2}:\d{2}$/.test(parts.time) ? parts.time + ':00' : parts.time });
      this.periodDraft.set(normalized(this.start.getRawValue()) !== normalized(this.startBaseline.parts)
        || normalized(this.end.getRawValue()) !== normalized(this.endBaseline.parts));
      if (this.periodError() || Object.keys(this.fieldErrors()).length) this.validatePeriodDraft();
    });
    this.search.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(value => {
      this.searchDraft.set(value !== this.searchBaseline);
      if (this.searchError()) this.searchError.set(Array.from(value).length > 100 ? 'La recherche doit comporter au plus 100 caractères bruts.' : '');
    });
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
    merge(this.maintenanceType.valueChanges, this.status.valueChanges, this.priority.valueChanges, this.size.valueChanges).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      const query = this.facade.query() ?? { company_id: this.company.value ?? undefined, site_id: this.site.value ?? undefined,
        equipment_id: this.equipment.value ?? undefined,
        start_time: this.route.snapshot.queryParamMap.get('start_time') ?? undefined, end_time: this.route.snapshot.queryParamMap.get('end_time') ?? undefined, page: 1, page_size: this.size.value };
      this.urlNotice.set('');
      void this.navigate({ ...query, maintenance_type: this.maintenanceType.value || undefined, status: this.status.value || undefined, priority: this.priority.value || undefined, page_size: this.size.value, page: 1 });
    });
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const companyId = positive(params.get('company_id')), siteId = positive(params.get('site_id')), equipmentId = positive(params.get('equipment_id'));
      if (['company_id', 'site_id', 'equipment_id'].some(key => params.has(key) && positive(params.get(key)) === undefined)) {
        this.facade.load(null); this.urlNotice.set('Le périmètre de l’URL est invalide. Sélectionnez une entreprise, un site et un équipement valides.');
        this.company.setValue(null, { emitEvent: false }); this.site.setValue(null, { emitEvent: false }); this.equipment.setValue(null, { emitEvent: false });
        return;
      }
      const start = params.get('start_time') ?? '', end = params.get('end_time') ?? '';
      const contextChanged = this.company.value !== (companyId ?? null) || this.site.value !== (siteId ?? null)
        || this.equipment.value !== (equipmentId ?? null);
      if (contextChanged || this.startBaseline.raw !== (params.has('start_time') ? start : undefined)
        || this.endBaseline.raw !== (params.has('end_time') ? end : undefined))
        this.restorePeriod(params.has('start_time') ? start : undefined, params.has('end_time') ? end : undefined);
      const query: MaintenanceQuery = { company_id: companyId, site_id: siteId, equipment_id: equipmentId,
        page: positive(params.get('page'), 1)!, page_size: positive(params.get('page_size'), 20, 100)!,
        maintenance_type: this.types.find(value => value === params.get('maintenance_type')), status: this.statuses.find(value => value === params.get('status')), priority: this.priorities.find(value => value === params.get('priority')), search: params.get('search') ?? undefined, start_time: params.has('start_time') ? start : undefined, end_time: params.has('end_time') ? end : undefined };
      this.maintenanceType.setValue(query.maintenance_type ?? '', { emitEvent: false }); this.status.setValue(query.status ?? '', { emitEvent: false }); this.priority.setValue(query.priority ?? '', { emitEvent: false }); if (contextChanged || (query.search ?? '') !== this.searchBaseline) this.restoreSearch(query.search ?? ''); this.size.setValue(query.page_size, { emitEvent: false });
      this.company.setValue(companyId ?? null, { emitEvent: false }); this.site.setValue(siteId ?? null, { emitEvent: false }); this.equipment.setValue(equipmentId ?? null, { emitEvent: false });
      if (['maintenance_type', 'status', 'priority'].some(key => params.has(key) && !query[key as 'status' | 'priority' | 'maintenance_type']) || (query.search !== undefined && (Array.from(query.search).length < 1 || Array.from(query.search).length > 100))) {
        this.facade.load(null); this.urlNotice.set('Un filtre de l’URL est invalide. Vérifiez les critères et la recherche (1 à 100 caractères bruts).'); return;
      }
      try { validateMeasurementPeriod(query.start_time, query.end_time); } catch {
        this.validatePeriodDraft();
        this.facade.load(query); return;
      }
      if (!this.periodDraft()) { this.periodError.set(''); this.fieldErrors.set({}); }
      const invalid = ['page','page_size'].some(key => params.has(key) && params.get(key) !== String(query[key as 'page' | 'page_size']));
      if (invalid) { this.facade.load(null); this.urlNotice.set('La pagination de l’URL a été normalisée.'); void this.navigate(query, true); return; }
      if (!same(this.facade.query(), query)) this.facade.load(query);
    });
    effect(() => {
      const company = this.facade.company(), site = this.facade.site();
      if (company) this.site.enable({ emitEvent: false }); else this.site.disable({ emitEvent: false });
      if (company && site) this.equipment.enable({ emitEvent: false }); else this.equipment.disable({ emitEvent: false });
      this.ensureCatalog(this.siteRequests, this.sites(), company?.id);
      this.ensureCatalog(this.equipmentRequests, this.equipments(), site?.id);
    });
  }

  private changeParent(field: 'company_id' | 'site_id' | 'equipment_id', id: number | null): void {
    this.urlNotice.set('');
    const query: MaintenanceQuery = { company_id: this.company.value ?? undefined, site_id: this.site.value ?? undefined,
      equipment_id: this.equipment.value ?? undefined, maintenance_type: this.maintenanceType.value || undefined, status: this.status.value || undefined, priority: this.priority.value || undefined, page: 1, page_size: this.size.value };
    if (field === 'company_id') {
      query.site_id = undefined; this.site.setValue(null, { emitEvent: false }); this.siteRequests.next(null);
    }
    if (field === 'company_id' || field === 'site_id') {
      query.equipment_id = undefined; this.equipment.setValue(null, { emitEvent: false }); this.equipmentRequests.next(null);
    }
    query[field] = id ?? undefined;
    this.restoreSearch(''); this.restorePeriod(); this.periodError.set(''); this.facade.load(query); void this.navigate(query);
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
    const period = this.validatePeriodDraft();
    if (!period) {
      const field = Object.keys(this.fieldErrors())[0];
      this.element.nativeElement.querySelector<HTMLInputElement>(field ? '#maintenance-' + field : '#maintenance-end-date')?.focus();
      return;
    }
    const query = this.facade.query();
    if (query) void this.navigate({ ...query, ...period, page: 1 });
  }
  private validatePeriodDraft(): { start_time: string | undefined; end_time: string | undefined } | null {
    const errors: Record<string, string> = {};
    const read = (key: 'start' | 'end', form: typeof this.start, baseline: typeof this.startBaseline): string | undefined => {
      const parts = form.getRawValue();
      for (const field of ['date', 'time', 'fraction'] as const) {
        const input = this.element.nativeElement.querySelector<HTMLInputElement>('#maintenance-' + key + '-' + field);
        if (input && !input.validity.valid) errors[key + '-' + field] = 'Valeur de ' + (field === 'date' ? 'date' : 'l’heure') + ' incomplète ou invalide.';
      }
      if (parts.date && !parts.time) errors[key + '-time'] = 'Renseignez l’heure UTC avec la date, sans heure par défaut.';
      if ((parts.time || parts.fraction) && !parts.date) errors[key + '-date'] = 'Renseignez la date de cette borne.';
      if (parts.fraction && !parts.time) errors[key + '-time'] = 'Renseignez l’heure UTC de cette fraction.';
      if (!/^\d{0,6}$/.test(parts.fraction)) errors[key + '-fraction'] = 'Utilisez de 0 à 6 chiffres pour la fraction.';
      if (parts.time && !/^(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?$/.test(parts.time)) errors[key + '-time'] = 'Heure UTC invalide : heures, minutes et secondes valides requises.';
      if (Object.keys(errors).some(field => field.startsWith(key + '-'))) return undefined;
      try {
        const value = serializeMeasurementBound(parts, baseline);
        validateMeasurementPeriod(value, undefined);
        return value;
      } catch { errors[key + '-date'] = 'Borne invalide : date réelle et horodatage avec offset requis, sans fuseau supposé.'; return undefined; }
    };
    const start_time = read('start', this.start, this.startBaseline), end_time = read('end', this.end, this.endBaseline);
    let message = Object.keys(errors).length ? 'La période n’est pas appliquée. Corrigez les champs indiqués.' : '';
    if (!message) {
      try { validateMeasurementPeriod(start_time, end_time); }
      catch { message = 'Le début doit être strictement antérieur à la fin (début inclus, fin exclue).';
        errors['end-date'] = message; }
    }
    this.fieldErrors.set(errors); this.periodError.set(message);
    return message ? null : { start_time, end_time };
  }
  private boundForm() {
    return new FormGroup({ date: new FormControl('', { nonNullable: true }),
      time: new FormControl('', { nonNullable: true }), fraction: new FormControl('', { nonNullable: true }) });
  }
  private restorePeriod(start?: string, end?: string): void {
    this.periodDraft.set(false); this.periodError.set(''); this.fieldErrors.set({});
    this.startBaseline = restoreMeasurementBound(start); this.endBaseline = restoreMeasurementBound(end);
    this.start.setValue(this.startBaseline.parts, { emitEvent: false }); this.end.setValue(this.endBaseline.parts, { emitEvent: false });
  }
  companyVerified(): boolean { return this.company.value !== null && this.facade.company()?.id === this.company.value; }
  siteVerified(): boolean { return this.companyVerified() && this.facade.site()?.id === this.site.value && this.facade.site()?.company_id === this.company.value; }
  equipmentVerified(): boolean { return this.siteVerified() && this.facade.equipment()?.id === this.equipment.value && this.facade.equipment()?.site_id === this.site.value; }
  applySearch(event?: Event): void {
    event?.preventDefault(); const raw = this.search.value;
    if (Array.from(raw).length > 100) { this.searchError.set('La recherche doit comporter au plus 100 caractères bruts.'); return; }
    this.searchError.set(''); const query = this.facade.query();
    if (query && this.canFilter()) void this.navigate({ ...query, search: raw === '' ? undefined : raw, page: 1 });
  }
  refresh(): void { const query = this.facade.query(); if (query && !this.busy()) this.facade.load(query); }
  private restoreSearch(value: string): void {
    this.searchBaseline = value; this.search.setValue(value, { emitEvent: false }); this.searchDraft.set(false); this.searchError.set('');
  }
  clearPeriod(): void {
    this.restorePeriod();
    // Change only the temporal URL keys, preserving even invalid unrelated filters for explicit repair.
    void this.router.navigate([], { relativeTo: this.route, queryParams: { start_time: null, end_time: null, page: 1 },
      queryParamsHandling: 'merge', preserveFragment: true });
  }
  changePage(page: number): void {
    const query = this.facade.query();
    if (query && !this.busy() && page >= 1 && (page <= this.page() || this.canNext())) void this.navigate({ ...query, page });
  }
  recoverPage(): void { const query = this.facade.query(), state = this.facade.state();
    if (query && state.status === 'success' && !state.data.items.length) void this.navigate({ ...query, page: Math.max(1, Math.min(query.page - 1, state.data.pages)) });
  }
  private navigate(query: MaintenanceQuery, replaceUrl = false): Promise<boolean> {
    return this.router.navigate([], { relativeTo: this.route, queryParams: { company_id: query.company_id ?? null,
      site_id: query.site_id ?? null, equipment_id: query.equipment_id ?? null, maintenance_type: query.maintenance_type ?? null, status: query.status ?? null, priority: query.priority ?? null, search: query.search ?? null, start_time: query.start_time ?? null, end_time: query.end_time ?? null,
      page: query.page, page_size: query.page_size }, queryParamsHandling: 'merge', preserveFragment: true, replaceUrl });
  }
}
