import { ChangeDetectionStrategy, Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { CompaniesListFacade } from '../../companies-list.facade';
import { CompaniesQuery } from '../../models/companies-state.model';

@Component({
  selector: 'app-companies-list',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, PageHeaderComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent],
  providers: [CompaniesListFacade],
  templateUrl: './companies-list.component.html',
  styleUrl: './companies-list.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CompaniesListComponent {
  readonly facade = inject(CompaniesListFacade);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly destroyRef = inject(DestroyRef);
  readonly search = new FormControl('', { nonNullable: true, validators: [Validators.maxLength(100)] });
  readonly urlNotice = signal('');
  readonly wildcardSearch = computed(() => /[%_]/.test(this.facade.query()?.search ?? ''));
  readonly page = computed(() => this.facade.query()?.page ?? 1);
  readonly pageSize = computed(() => this.facade.query()?.page_size ?? 20);
  readonly busy = computed(() => this.facade.state().status === 'loading');
  readonly canNext = computed(() => {
    const state = this.facade.state();
    return state.status === 'success' && state.query.page < state.data.pages;
  });

  constructor() {
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const positive = (raw: string | null, fallback: number, maximum = Number.MAX_SAFE_INTEGER) =>
        raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw))
          && Number(raw) >= 1 && Number(raw) <= maximum ? Number(raw) : fallback;
      const page = positive(params.get('page'), 1);
      const pageSize = positive(params.get('page_size'), 20, 100);
      const rawSearch = params.get('search');
      const trimmed = rawSearch?.trim() ?? '';
      const search = trimmed.length <= 100 ? trimmed : '';
      const query: CompaniesQuery = { page, page_size: pageSize, ...(search ? { search } : {}) };
      const invalid = (params.has('page') && params.get('page') !== String(page))
        || (params.has('page_size') && params.get('page_size') !== String(pageSize))
        || (rawSearch !== null && (rawSearch !== search || !search));
      if (invalid) {
        this.urlNotice.set('Les paramètres de l’URL ont été normalisés avant le chargement.');
        void this.navigate(query, true);
        return;
      }
      const previous = this.facade.query();
      if (previous?.page === page && previous.page_size === pageSize && previous.search === query.search) return;
      this.search.setValue(search, { emitEvent: false });
      this.facade.load(query);
    });
  }

  applySearch(event?: Event): void {
    event?.preventDefault();
    this.search.markAsTouched();
    if (this.search.invalid) return;
    const search = this.search.value.trim();
    void this.navigate({ page: 1, page_size: this.pageSize(), ...(search ? { search } : {}) });
  }

  clearSearch(): void {
    this.search.setValue('');
    void this.navigate({ page: 1, page_size: this.pageSize() });
  }

  changePage(page: number): void {
    if (this.busy() || page < 1 || (page > this.page() && !this.canNext())) return;
    void this.navigate({ ...this.facade.query()!, page });
  }

  recoverPage(): void {
    const state = this.facade.state();
    if (state.status !== 'success' || state.data.items.length > 0) return;
    const last = Math.max(1, state.data.pages);
    void this.navigate({ ...state.query, page: last !== state.query.page ? last : 1 });
  }

  private navigate(query: CompaniesQuery, replaceUrl = false): Promise<boolean> {
    return this.router.navigate([], { relativeTo: this.route,
      queryParams: { page: query.page, page_size: query.page_size, search: query.search ?? null },
      queryParamsHandling: 'merge', preserveFragment: true, replaceUrl });
  }
}
