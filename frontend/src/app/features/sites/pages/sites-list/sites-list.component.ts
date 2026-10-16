import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { Page } from '../../../../core/models/page.model';
import { CompanyRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { SitesListFacade } from '../../sites-list.facade';

type Catalog = Page<CompanyRead> & { status: 'loading' | 'ready' | 'error'; requestedPage: number; retryable: boolean };

@Component({
  selector: 'app-sites-list', standalone: true,
  imports: [ReactiveFormsModule, PageHeaderComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent],
  providers: [SitesListFacade],
  templateUrl: './sites-list.component.html', styleUrl: './sites-list.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SitesListComponent {
  readonly facade = inject(SitesListFacade);
  private readonly references = inject(ReferenceDataApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  private readonly catalogRequests = new Subject<number>();
  readonly company = new FormControl<number | null>(null);
  readonly search = new FormControl('', { nonNullable: true, validators: [Validators.maxLength(100)] });
  readonly size = new FormControl(20, { nonNullable: true });
  readonly urlNotice = signal('');
  readonly catalog = signal<Catalog>({ items: [], total: 0, page: 0, page_size: 50, pages: 0,
    status: 'loading', requestedPage: 1, retryable: false });
  readonly options = computed(() => {
    const selected = this.facade.company();
    return [...new Map([...this.catalog().items, ...(selected ? [selected] : [])].map(item => [item.id, item])).values()];
  });
  readonly page = computed(() => this.facade.query()?.page ?? 1);
  readonly pageSize = computed(() => this.facade.query()?.page_size ?? 20);
  readonly sizes = computed(() => [...new Set([20, 50, 100, this.pageSize()])].sort((a, b) => a - b));
  readonly busy = computed(() => this.facade.state().status === 'loading');
  readonly canSearch = computed(() => !!this.facade.company());
  readonly wildcardSearch = computed(() => /[%_]/.test(this.facade.query()?.search ?? ''));
  readonly canNext = computed(() => {
    const state = this.facade.state();
    return state.status === 'success' && state.query.page < state.data.pages;
  });

  constructor() {
    this.catalogRequests.pipe(switchMap(page => {
      const previous = this.catalog();
      this.catalog.set({ ...previous, status: 'loading', requestedPage: page });
      return this.references.getCompanies({ page, page_size: 50 }).pipe(
        tap(data => this.catalog.set({ ...data,
          items: [...new Map([...(page > 1 ? previous.items : []), ...data.items].map(item => [item.id, item])).values()],
          status: 'ready', requestedPage: page, retryable: false })),
        catchError((error: unknown) => {
          const status = error instanceof HttpErrorResponse ? error.status : -1;
          this.catalog.set({ ...previous, status: 'error', requestedPage: page, retryable: status === 0 || status >= 500 });
          return EMPTY;
        })
      );
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
    this.catalogRequests.next(1);

    this.company.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(companyId => {
      void this.navigate(companyId, 1, this.size.value);
    });
    this.size.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(size => {
      if (size >= 1 && size <= 100) void this.navigate(this.company.value, 1, size, this.facade.query()?.search);
    });
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const positive = (raw: string | null, fallback: number | null, max = Number.MAX_SAFE_INTEGER) =>
        raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) >= 1 && Number(raw) <= max ? Number(raw) : fallback;
      const companyId = positive(params.get('company_id'), null);
      const page = positive(params.get('page'), 1)!;
      const pageSize = positive(params.get('page_size'), 20, 100)!;
      const rawSearch = params.get('search');
      const trimmed = rawSearch?.trim() ?? '';
      const search = trimmed.length <= 100 ? trimmed : '';
      const invalid = (params.has('company_id') && params.get('company_id') !== String(companyId))
        || (params.has('page') && params.get('page') !== String(page))
        || (params.has('page_size') && params.get('page_size') !== String(pageSize))
        || (rawSearch !== null && (rawSearch !== search || !search));
      if (invalid) {
        this.urlNotice.set('Les paramètres de l’URL ont été normalisés avant le chargement.');
        void this.navigate(companyId, page, pageSize, search, true);
        return;
      }
      this.company.setValue(companyId, { emitEvent: false });
      this.size.setValue(pageSize, { emitEvent: false });
      this.search.setValue(search, { emitEvent: false });
      const previous = this.facade.query();
      if (previous?.company_id === companyId && previous.page === page && previous.page_size === pageSize && previous.search === (search || undefined)) return;
      this.facade.load(companyId === null ? null : { company_id: companyId, page, page_size: pageSize, ...(search ? { search } : {}) });
    });
  }

  loadMoreCompanies(): void {
    const catalog = this.catalog();
    if (catalog.status === 'ready' && catalog.page < catalog.pages) this.catalogRequests.next(catalog.page + 1);
  }
  retryCompanies(): void {
    const catalog = this.catalog();
    if (catalog.status === 'error' && catalog.retryable) this.catalogRequests.next(catalog.requestedPage);
  }
  applySearch(event?: Event): void {
    event?.preventDefault();
    this.search.markAsTouched();
    if (this.search.invalid || !this.canSearch()) return;
    void this.navigate(this.company.value, 1, this.size.value, this.search.value.trim());
  }
  clearSearch(): void {
    this.search.setValue('');
    if (this.canSearch()) void this.navigate(this.company.value, 1, this.size.value);
  }
  changePage(page: number): void {
    const query = this.facade.query();
    if (!query || this.busy() || page < 1 || (page > this.page() && !this.canNext())) return;
    void this.navigate(query.company_id, page, query.page_size, query.search);
  }
  recoverPage(): void {
    const state = this.facade.state();
    if (state.status !== 'success' || state.data.items.length > 0) return;
    const last = Math.max(1, state.data.pages);
    void this.navigate(state.query.company_id, last !== state.query.page ? last : 1, state.query.page_size, state.query.search);
  }
  private navigate(companyId: number | null, page: number, pageSize: number, search?: string, replaceUrl = false): Promise<boolean> {
    return this.router.navigate([], { relativeTo: this.route,
      queryParams: { company_id: companyId, page, page_size: pageSize, search: search || null },
      queryParamsHandling: 'merge', preserveFragment: true, replaceUrl });
  }
}
