import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, WritableSignal, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { EMPTY, Observable, Subject, catchError, merge, switchMap, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { Page } from '../../../../core/models/page.model';
import { CompanyRead, EquipmentCriticality, EquipmentStatus, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { EquipmentsListFacade } from '../../equipments-list.facade';
import { EquipmentsQuery } from '../../models/equipments-state.model';

type Catalog<T> = Page<T> & { scope: number | null; status: 'idle' | 'loading' | 'ready' | 'error'; requestedPage: number; retryable: boolean };
type CatalogRequest = { scope: number | null; page: number } | null;
const catalog = <T>(): Catalog<T> => ({ items: [], total: 0, page: 0, page_size: 50, pages: 0,
  scope: null, status: 'idle', requestedPage: 1, retryable: false });
const positive = (raw: string | null, fallback?: number, maximum = Number.MAX_SAFE_INTEGER) =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= maximum ? Number(raw) : fallback;
const same = (a: Readonly<EquipmentsQuery> | null, b: EquipmentsQuery) => a !== null &&
  (['company_id', 'site_id', 'page', 'page_size', 'search', 'status', 'criticality'] as const).every(key => a[key] === b[key]);

@Component({
  selector: 'app-equipments-list', standalone: true,
  imports: [ReactiveFormsModule, RouterLink, PageHeaderComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent],
  providers: [EquipmentsListFacade], templateUrl: './equipments-list.component.html',
  styleUrl: './equipments-list.component.scss', changeDetection: ChangeDetectionStrategy.OnPush
})
export class EquipmentsListComponent {
  readonly facade = inject(EquipmentsListFacade);
  private readonly references = inject(ReferenceDataApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly companyRequests = new Subject<CatalogRequest>();
  private readonly siteRequests = new Subject<CatalogRequest>();
  readonly companies = signal(catalog<CompanyRead>());
  readonly sites = signal(catalog<SiteRead>());
  readonly company = new FormControl<number | null>(null);
  readonly site = new FormControl<number | null>({ value: null, disabled: true });
  readonly search = new FormControl('', { nonNullable: true, validators: Validators.maxLength(100) });
  readonly status = new FormControl<EquipmentStatus | ''>('', { nonNullable: true });
  readonly criticality = new FormControl<EquipmentCriticality | ''>('', { nonNullable: true });
  readonly size = new FormControl(20, { nonNullable: true });
  readonly urlNotice = signal('');
  readonly referenceLabel = businessReferenceLabel;
  readonly statusLabels: Record<EquipmentStatus, string> = { operational: 'Opérationnel', maintenance: 'En maintenance', out_of_service: 'Hors service' };
  readonly criticalityLabels: Record<EquipmentCriticality, string> = { low: 'Faible', medium: 'Moyenne', high: 'Élevée', critical: 'Critique' };
  readonly statuses = Object.keys(this.statusLabels) as EquipmentStatus[];
  readonly criticalities = Object.keys(this.criticalityLabels) as EquipmentCriticality[];
  readonly companyOptions = computed(() => this.options(this.companies().items, this.facade.company()));
  readonly siteOptions = computed(() => this.options(this.sites().items, this.facade.site()).filter(item => item.company_id === this.sites().scope));
  readonly busy = computed(() => this.facade.state().status === 'loading');
  readonly canFilter = computed(() => !!this.facade.site());
  readonly page = computed(() => this.facade.query()?.page ?? 1);
  readonly pageSize = computed(() => this.facade.query()?.page_size ?? 20);
  readonly sizes = computed(() => [...new Set([20, 50, 100, this.pageSize()])].sort((a, b) => a - b));
  readonly filtered = computed(() => !!(this.facade.query()?.search || this.facade.query()?.status || this.facade.query()?.criticality));
  readonly canNext = computed(() => { const state = this.facade.state(); return state.status === 'success' && this.page() < state.data.pages; });

  constructor() {
    this.connectCatalog(this.companyRequests, this.companies, (_, page) => this.references.getCompanies({ page, page_size: 50 }));
    this.connectCatalog(this.siteRequests, this.sites, (scope, page) => this.references.getSites(scope!, { page, page_size: 50 }).pipe(tap(data => {
      if (data.items.some(item => item.company_id !== scope)) throw new Error('Incoherent site catalog');
    })));
    this.companyRequests.next({ scope: null, page: 1 });
    this.company.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => {
      this.site.setValue(null, { emitEvent: false }); this.facade.load(null); this.siteRequests.next(null);
      void this.navigate({ ...this.filters(), company_id: id ?? undefined, page: 1, page_size: this.size.value });
    });
    this.site.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(id => {
      const appliedSearch = this.facade.query()?.search;
      this.facade.load(null);
      void this.navigate({ ...this.filters(), company_id: this.company.value ?? undefined, site_id: id ?? undefined,
        search: appliedSearch, page: 1, page_size: this.size.value });
    });
    merge(this.status.valueChanges, this.criticality.valueChanges, this.size.valueChanges)
      .pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
        const query = this.facade.query();
        if (query) void this.navigate({ ...query, ...this.filters(), page: 1, page_size: this.size.value });
      });
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const companyId = positive(params.get('company_id'));
      const invalidCompany = params.has('company_id') && companyId === undefined;
      const siteId = invalidCompany ? undefined : positive(params.get('site_id'));
      const search = (params.get('search')?.trim() ?? '');
      const status = this.statuses.find(value => value === params.get('status'));
      const criticality = this.criticalities.find(value => value === params.get('criticality'));
      const query: EquipmentsQuery = { company_id: companyId, site_id: siteId,
        page: positive(params.get('page'), 1)!, page_size: positive(params.get('page_size'), 20, 100)!,
        search: search.length <= 100 && search ? search : undefined, status, criticality };
      const invalid = (['company_id', 'site_id', 'page', 'page_size', 'search', 'status', 'criticality'] as const)
        .some(key => params.has(key) && params.get(key) !== String(query[key] ?? ''))
        || ['company_id', 'site_id', 'search', 'status', 'criticality'].some(key => params.get(key) === '');
      if (invalid) {
        this.facade.load(null); this.urlNotice.set('Les paramètres de l’URL ont été normalisés avant le chargement.');
        void this.navigate(query, true); return;
      }
      this.company.setValue(companyId ?? null, { emitEvent: false }); this.site.setValue(siteId ?? null, { emitEvent: false });
      if (companyId === undefined) this.site.disable({ emitEvent: false }); else this.site.enable({ emitEvent: false });
      this.search.setValue(query.search ?? '', { emitEvent: false }); this.status.setValue(status ?? '', { emitEvent: false });
      this.criticality.setValue(criticality ?? '', { emitEvent: false }); this.size.setValue(query.page_size, { emitEvent: false });
      this.ensureSiteCatalog(companyId);
      if (!same(this.facade.query(), query)) this.facade.load(query);
    });
    effect(() => {
      const query = this.facade.query(), company = this.facade.company();
      if (query?.site_id && company && !this.route.snapshot.queryParamMap.has('company_id')) {
        void this.navigate({ ...query, company_id: company.id }, true);
      }
    });
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
        target.set({ ...previous, scope: request.scope, status: 'error', requestedPage: request.page, retryable: status === 0 || status >= 500 });
        return EMPTY;
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }
  private ensureSiteCatalog(companyId: number | undefined): void {
    if (companyId === undefined) { if (this.sites().status !== 'idle') this.siteRequests.next(null); }
    else if (this.sites().scope !== companyId) this.siteRequests.next({ scope: companyId, page: 1 });
  }
  moreCompanies(): void { const c = this.companies(); if (c.status === 'ready' && c.page < c.pages) this.companyRequests.next({ scope: null, page: c.page + 1 }); }
  moreSites(): void { const c = this.sites(); if (c.status === 'ready' && c.page < c.pages) this.siteRequests.next({ scope: c.scope, page: c.page + 1 }); }
  retryCompanies(): void { const c = this.companies(); if (c.status === 'error' && c.retryable) this.companyRequests.next({ scope: null, page: c.requestedPage }); }
  retrySites(): void { const c = this.sites(); if (c.status === 'error' && c.retryable) this.siteRequests.next({ scope: c.scope, page: c.requestedPage }); }
  applySearch(event?: Event): void {
    event?.preventDefault(); this.search.markAsTouched(); const query = this.facade.query();
    if (query && this.canFilter() && this.search.valid) void this.navigate({ ...query, search: this.search.value.trim() || undefined, page: 1 });
  }
  clearSearch(): void { this.search.setValue(''); this.applySearch(); }
  clearFilters(): void { const query = this.facade.query(); if (query) void this.navigate({ ...query, search: undefined, status: undefined, criticality: undefined, page: 1 }); }
  changePage(page: number): void {
    const query = this.facade.query();
    if (query && !this.busy() && page >= 1 && (page <= this.page() || this.canNext())) void this.navigate({ ...query, page });
  }
  recoverPage(): void { const query = this.facade.query(), state = this.facade.state();
    if (query && state.status === 'success' && !state.data.items.length) void this.navigate({ ...query, page: Math.max(1, Math.min(query.page - 1, state.data.pages)) });
  }
  private filters() { return { status: this.status.value || undefined, criticality: this.criticality.value || undefined }; }
  private navigate(query: EquipmentsQuery, replaceUrl = false): Promise<boolean> {
    return this.router.navigate([], { relativeTo: this.route, queryParams: { company_id: query.company_id ?? null,
      site_id: query.site_id ?? null, page: query.page, page_size: query.page_size, search: query.search || null,
      status: query.status || null, criticality: query.criticality || null }, queryParamsHandling: 'merge', preserveFragment: true, replaceUrl });
  }
}
