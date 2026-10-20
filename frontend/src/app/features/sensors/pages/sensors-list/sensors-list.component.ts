import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, WritableSignal, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
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
import { SensorStatus } from '../../models/sensor.model';
import { SensorsQuery } from '../../models/sensors-state.model';
import { SensorsListFacade } from '../../sensors-list.facade';

type Catalog<T> = Page<T> & { scope: number | null; status: 'idle' | 'loading' | 'ready' | 'error'; requestedPage: number; retryable: boolean };
type CatalogRequest = { scope: number | null; page: number } | null;
const catalog = <T>(): Catalog<T> => ({ items: [], total: 0, page: 0, page_size: 50, pages: 0,
  scope: null, status: 'idle', requestedPage: 1, retryable: false });
const positive = (raw: string | null, fallback?: number, maximum = Number.MAX_SAFE_INTEGER) =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= maximum ? Number(raw) : fallback;
const keys = ['company_id', 'site_id', 'equipment_id', 'page', 'page_size', 'status', 'search'] as const;
const same = (a: Readonly<SensorsQuery> | null, b: SensorsQuery) => a !== null && keys.every(key => a[key] === b[key]);

@Component({
  selector: 'app-sensors-list', standalone: true,
  imports: [ReactiveFormsModule, PageHeaderComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent],
  providers: [SensorsListFacade], templateUrl: './sensors-list.component.html',
  styleUrl: './sensors-list.component.scss', changeDetection: ChangeDetectionStrategy.OnPush
})
export class SensorsListComponent {
  readonly facade = inject(SensorsListFacade);
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
  readonly search = new FormControl('', { nonNullable: true, validators: Validators.maxLength(100) });
  readonly status = new FormControl<SensorStatus | ''>('', { nonNullable: true });
  readonly size = new FormControl(20, { nonNullable: true });
  readonly urlNotice = signal('');
  readonly referenceLabel = businessReferenceLabel;
  readonly statusLabels = { active: 'Actif', inactive: 'Inactif' } as const;
  readonly statuses: SensorStatus[] = ['active', 'inactive'];
  readonly companyOptions = computed(() => this.options(this.companies().items, this.facade.company()));
  readonly siteOptions = computed(() => this.options(this.sites().items, this.facade.site()).filter(item => item.company_id === this.sites().scope));
  readonly equipmentOptions = computed(() => this.options(this.equipments().items, this.facade.equipment()).filter(item => item.site_id === this.equipments().scope));
  readonly busy = computed(() => this.facade.state().status === 'loading');
  readonly canFilter = computed(() => this.facade.equipment() !== null && this.facade.site() !== null && this.facade.company() !== null);
  readonly page = computed(() => this.facade.query()?.page ?? 1);
  readonly pageSize = computed(() => this.facade.query()?.page_size ?? 20);
  readonly sizes = computed(() => [...new Set([20, 50, 100, this.pageSize()])].sort((a, b) => a - b));
  readonly filtered = computed(() => !!(this.facade.query()?.search || this.facade.query()?.status));
  readonly canNext = computed(() => { const state = this.facade.state(); return state.status === 'success' && this.page() < state.data.pages; });

  constructor() {
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
    merge(this.status.valueChanges, this.size.valueChanges).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
      const query = this.facade.query();
      if (query) void this.navigate({ ...query, status: this.status.value || undefined, page_size: this.size.value, page: 1 });
    });
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const companyId = positive(params.get('company_id')), siteId = positive(params.get('site_id')), equipmentId = positive(params.get('equipment_id'));
      if (['company_id', 'site_id', 'equipment_id'].some(key => params.has(key) && positive(params.get(key)) === undefined)) {
        this.facade.load(null); this.urlNotice.set('Le périmètre de l’URL est invalide. Sélectionnez une entreprise, un site et un équipement valides.');
        this.company.setValue(null, { emitEvent: false }); this.site.setValue(null, { emitEvent: false }); this.equipment.setValue(null, { emitEvent: false });
        return;
      }
      const search = params.get('search')?.trim() ?? '';
      const query: SensorsQuery = { company_id: companyId, site_id: siteId, equipment_id: equipmentId,
        page: positive(params.get('page'), 1)!, page_size: positive(params.get('page_size'), 20, 100)!,
        status: this.statuses.find(value => value === params.get('status')), search: search && search.length <= 100 ? search : undefined };
      const invalid = keys.some(key => params.has(key) && params.get(key) !== String(query[key] ?? ''))
        || ['search', 'status'].some(key => params.get(key) === '');
      if (invalid) { this.facade.load(null); this.urlNotice.set('Les filtres de l’URL ont été normalisés avant le chargement.'); void this.navigate(query, true); return; }
      this.company.setValue(companyId ?? null, { emitEvent: false }); this.site.setValue(siteId ?? null, { emitEvent: false });
      this.equipment.setValue(equipmentId ?? null, { emitEvent: false }); this.search.setValue(query.search ?? '', { emitEvent: false });
      this.status.setValue(query.status ?? '', { emitEvent: false }); this.size.setValue(query.page_size, { emitEvent: false });
      if (!same(this.facade.query(), query)) this.facade.load(query);
    });
    effect(() => {
      const company = this.facade.company(), site = this.facade.site(), query = this.facade.query();
      if (company) this.site.enable({ emitEvent: false }); else this.site.disable({ emitEvent: false });
      if (company && site) this.equipment.enable({ emitEvent: false }); else this.equipment.disable({ emitEvent: false });
      this.ensureCatalog(this.siteRequests, this.sites(), company?.id);
      this.ensureCatalog(this.equipmentRequests, this.equipments(), site?.id);
      if (query && company && ((!this.route.snapshot.queryParamMap.has('company_id')) || (site && !this.route.snapshot.queryParamMap.has('site_id'))))
        void this.navigate(query, true);
    });
  }

  private changeParent(field: 'company_id' | 'site_id' | 'equipment_id', id: number | null): void {
    this.urlNotice.set('');
    const query: SensorsQuery = { company_id: this.company.value ?? undefined, site_id: this.site.value ?? undefined,
      equipment_id: this.equipment.value ?? undefined, status: this.status.value || undefined, page: 1, page_size: this.size.value };
    if (field === 'company_id') {
      query.site_id = undefined; this.site.setValue(null, { emitEvent: false }); this.siteRequests.next(null);
    }
    if (field !== 'equipment_id') {
      query.equipment_id = undefined; this.equipment.setValue(null, { emitEvent: false }); this.equipmentRequests.next(null);
    }
    query[field] = id ?? undefined;
    this.search.setValue(''); this.facade.load(query); void this.navigate(query);
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
  applySearch(event?: Event): void {
    event?.preventDefault(); this.search.markAsTouched(); const query = this.facade.query();
    if (query && this.canFilter() && this.search.valid) void this.navigate({ ...query, search: this.search.value.trim() || undefined, page: 1 });
  }
  clearSearch(): void { this.search.setValue(''); this.applySearch(); }
  clearFilters(): void { const query = this.facade.query(); if (query) void this.navigate({ ...query, search: undefined, status: undefined, page: 1 }); }
  changePage(page: number): void {
    const query = this.facade.query();
    if (query && !this.busy() && page >= 1 && (page <= this.page() || this.canNext())) void this.navigate({ ...query, page });
  }
  recoverPage(): void { const query = this.facade.query(), state = this.facade.state();
    if (query && state.status === 'success' && !state.data.items.length) void this.navigate({ ...query, page: Math.max(1, Math.min(query.page - 1, state.data.pages)) });
  }
  detailUrl(id: number): string {
    return this.router.serializeUrl(this.router.createUrlTree(['/sensors', id], { queryParams: this.facade.query() }));
  }
  private navigate(query: SensorsQuery, replaceUrl = false): Promise<boolean> {
    return this.router.navigate([], { relativeTo: this.route, queryParams: { company_id: query.company_id ?? null,
      site_id: query.site_id ?? null, equipment_id: query.equipment_id ?? null, status: query.status || null, search: query.search || null,
      page: query.page, page_size: query.page_size }, queryParamsHandling: 'merge', preserveFragment: true, replaceUrl });
  }
}
