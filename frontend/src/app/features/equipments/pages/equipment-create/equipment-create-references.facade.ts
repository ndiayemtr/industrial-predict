import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, WritableSignal, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, Subject, catchError, map, of, switchMap, tap, throwError } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { Page } from '../../../../core/models/page.model';
import { CompanyRead, SiteRead } from '../../../../core/models/reference-data.model';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { EquipmentParentSelection } from '../../components/equipment-form/equipment-form.component';

type Catalog<T> = Page<T> & { scope: number | null; status: 'idle' | 'loading' | 'ready' | 'error'; requestedPage: number; retryable: boolean };
type Selection = EquipmentParentSelection & { prefill: boolean };
function empty<T>(): Catalog<T> { return { items: [], total: 0, page: 0, page_size: 50, pages: 0, scope: null, status: 'idle', requestedPage: 1, retryable: false }; }
function positive(id: number | null): id is number { return Number.isSafeInteger(id) && Number(id) > 0; }
function retryable(error: unknown): boolean { return error instanceof HttpErrorResponse && (error.status === 0 || error.status >= 500); }

@Injectable()
export class EquipmentCreateReferencesFacade {
  private readonly api = inject(ReferenceDataApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly requests = new Subject<Selection>();
  private readonly companyRequests = new Subject<{ scope: number | null; page: number } | null>();
  private readonly siteRequests = new Subject<{ scope: number | null; page: number } | null>();
  private selection: Selection = { company_id: null, site_id: null, prefill: false };
  readonly companies = signal(empty<CompanyRead>());
  readonly sites = signal(empty<SiteRead>());
  readonly company = signal<CompanyRead | null>(null);
  readonly site = signal<SiteRead | null>(null);
  readonly initialParents = signal<EquipmentParentSelection | null>(null);
  readonly state = signal<'idle' | 'loading' | 'ready' | 'error'>('idle');
  readonly message = signal('');
  readonly canRetry = signal(false);
  readonly companyOptions = computed(() => this.options(this.companies().items, this.company()));
  readonly siteOptions = computed(() => this.options(this.sites().items, this.site()));

  constructor() {
    this.catalog(this.companyRequests, this.companies, (_, page) => this.api.getCompanies({ page, page_size: 50 }));
    this.catalog(this.siteRequests, this.sites, (scope, page) => this.api.getSites(scope!, { page, page_size: 50 }).pipe(tap(data => {
      if (data.items.some(item => item.company_id !== scope)) throw new Error('Site catalog mismatch');
    })));
    this.requests.pipe(switchMap(selection => {
      this.company.set(null); this.site.set(null); this.message.set(''); this.canRetry.set(false);
      if (selection.company_id === null && selection.site_id === null) { this.state.set('idle'); return EMPTY; }
      this.state.set('loading');
      const parents = selection.company_id !== null
        ? this.readCompany(selection.company_id).pipe(switchMap(company => selection.site_id === null ? of({ company, site: null })
          : this.readSite(selection.site_id).pipe(map(site => ({ company, site })))))
        : this.readSite(selection.site_id!).pipe(switchMap(site => this.readCompany(site.company_id).pipe(map(company => ({ company, site })))));
      return parents.pipe(tap(({ company, site }) => {
        if (site && site.company_id !== company.id) throw new Error('Parent mismatch');
        this.company.set(company); this.site.set(site); this.ensureSites(company.id); this.state.set('ready');
        if (selection.prefill) this.initialParents.set({ company_id: company.id, site_id: site?.id ?? null });
      }), catchError((error: unknown) => {
        this.state.set('error'); this.canRetry.set(retryable(error));
        this.message.set(error instanceof HttpErrorResponse && error.status === 404
          ? 'Une référence de rattachement n’est plus disponible. Choisissez une entreprise et un site disponibles.'
          : 'Le rattachement entreprise/site ne peut pas être vérifié ou n’est pas cohérent. Vos saisies sont conservées.');
        return EMPTY;
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
    this.companyRequests.next({ scope: null, page: 1 });
  }
  choose(company_id: number | null, site_id: number | null, prefill = false): void {
    if (!prefill) this.initialParents.set(null);
    if (company_id !== this.selection.company_id) this.siteRequests.next(null);
    this.selection = { company_id, site_id, prefill }; this.requests.next(this.selection);
  }
  verify(): void { this.requests.next(this.selection); }
  invalidate(): void {
    this.company.set(null); this.site.set(null); this.state.set('error'); this.canRetry.set(true);
    this.message.set('Vérifiez à nouveau le rattachement avant de soumettre. Vos saisies sont conservées.');
  }
  moreCompanies(): void { const c = this.companies(); if (c.status === 'ready' && c.page < c.pages) this.companyRequests.next({ scope: null, page: c.page + 1 }); }
  moreSites(): void { const c = this.sites(); if (c.status === 'ready' && c.page < c.pages) this.siteRequests.next({ scope: c.scope, page: c.page + 1 }); }
  retryCompanies(): void { const c = this.companies(); if (c.status === 'error' && c.retryable) this.companyRequests.next({ scope: null, page: c.requestedPage }); }
  retrySites(): void { const c = this.sites(); if (c.status === 'error' && c.retryable) this.siteRequests.next({ scope: c.scope, page: c.requestedPage }); }
  private ensureSites(id: number): void { if (this.sites().scope !== id) this.siteRequests.next({ scope: id, page: 1 }); }
  private options<T extends CompanyRead>(items: T[], selected: T | null) {
    return [...new Map([...items, ...(selected ? [selected] : [])].map(item => [item.id, { id: item.id, label: businessReferenceLabel(item) }])).values()];
  }
  private readCompany(id: number): Observable<CompanyRead> {
    return !positive(id) ? throwError(() => new Error('Invalid company')) : this.api.getCompanyById(id).pipe(tap(company => {
      if (company.id !== id) throw new Error('Company mismatch'); this.ensureSites(id);
    }));
  }
  private readSite(id: number): Observable<SiteRead> {
    return !positive(id) ? throwError(() => new Error('Invalid site')) : this.api.getSiteById(id).pipe(tap(site => {
      if (site.id !== id || !positive(site.company_id)) throw new Error('Site mismatch');
    }));
  }
  private catalog<T extends { id: number }>(requests: Subject<{ scope: number | null; page: number } | null>, target: WritableSignal<Catalog<T>>,
    read: (scope: number | null, page: number) => Observable<Page<T>>): void {
    requests.pipe(switchMap(request => {
      if (!request) { target.set(empty<T>()); return EMPTY; }
      const previous = request.page > 1 && target().scope === request.scope ? target() : empty<T>();
      target.set({ ...previous, scope: request.scope, status: 'loading', requestedPage: request.page });
      return read(request.scope, request.page).pipe(tap(data => target.set({ ...data, scope: request.scope,
        items: [...new Map([...previous.items, ...data.items].map(item => [item.id, item])).values()],
        status: 'ready', requestedPage: request.page, retryable: false })), catchError(error => {
        target.set({ ...previous, scope: request.scope, status: 'error', requestedPage: request.page, retryable: retryable(error) }); return EMPTY;
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }
}
