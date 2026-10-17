import { DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, HostListener, Injector, afterNextRender, computed, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NbToastrService } from '@nebular/theme';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { Page } from '../../../../core/models/page.model';
import { CompanyRead, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { SiteFormComponent, SiteField, SiteFieldErrors } from '../../components/site-form/site-form.component';
import { SitesApiService } from '../../data-access/sites-api.service';
import { SiteCreate } from '../../models/site-write.model';

const positive = (raw: string | null, fallback: number | null, max = Number.MAX_SAFE_INTEGER) =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= max ? Number(raw) : fallback;
type Catalog = Page<CompanyRead> & { status: 'loading' | 'ready' | 'error'; requestedPage: number; retryable: boolean };

@Component({
  selector: 'app-site-create', standalone: true,
  imports: [SiteFormComponent, RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './site-create.component.html', styleUrl: './site-create.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SiteCreateComponent {
  private readonly references = inject(ReferenceDataApiService);
  private readonly api = inject(SitesApiService);
  private readonly router = inject(Router);
  private readonly toastr = inject(NbToastrService);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly params = inject(ActivatedRoute).snapshot.queryParamMap;
  readonly initialCompanyId = positive(this.params.get('company_id'), null);
  readonly contextNotice = this.params.has('company_id') && this.initialCompanyId === null
    ? 'L’entreprise du contexte n’est pas valide. Sélectionnez une entreprise.' : '';
  private readonly contextPage = positive(this.params.get('page'), 1)!;
  private readonly contextSize = positive(this.params.get('page_size'), 20, 100)!;
  private readonly contextSearch = this.params.get('search')?.trim() ?? '';
  readonly companyId = signal(this.initialCompanyId);
  readonly selectedCompany = signal<CompanyRead | null>(null);
  readonly referenceState = signal<'idle' | 'loading' | 'ready' | 'error'>('idle');
  readonly referenceMessage = signal('');
  readonly referenceRetryable = signal(false);
  readonly catalog = signal<Catalog>({ items: [], total: 0, page: 0, page_size: 50, pages: 0, status: 'loading', requestedPage: 1, retryable: false });
  private readonly companyRequests = new Subject<number | null>();
  private readonly catalogRequests = new Subject<number>();
  readonly editor = viewChild(SiteFormComponent);
  readonly state = signal<'idle' | 'saving' | 'success' | 'error'>('idle');
  readonly message = signal('');
  readonly fieldErrors = signal<SiteFieldErrors>({});
  readonly uncertain = signal(false);
  readonly created = signal<SiteRead | null>(null);
  private notified = false;
  readonly listQuery = computed(() => {
    const sameCompany = this.companyId() === this.initialCompanyId;
    return { ...(this.companyId() !== null ? { company_id: this.companyId()! } : {}),
      page: sameCompany ? this.contextPage : 1, page_size: this.contextSize,
      ...(sameCompany && this.contextSearch && this.contextSearch.length <= 100 ? { search: this.contextSearch } : {}) };
  });
  readonly options = computed(() => {
    const selected = this.selectedCompany();
    const options = [...new Map([...this.catalog().items, ...(selected ? [selected] : [])].map(item => [item.id, { id: item.id, label: businessReferenceLabel(item) }])).values()];
    const id = this.companyId();
    if (id !== null && !options.some(item => item.id === id)) options.push({ id,
      label: this.referenceState() === 'loading' ? 'Vérification de l’entreprise...' : 'Entreprise indisponible' });
    return options;
  });

  constructor() {
    this.catalogRequests.pipe(switchMap(page => {
      const previous = this.catalog();
      this.catalog.set({ ...previous, status: 'loading', requestedPage: page });
      return this.references.getCompanies({ page, page_size: 50 }).pipe(tap(data => this.catalog.set({ ...data,
        items: [...new Map([...(page > 1 ? previous.items : []), ...data.items].map(item => [item.id, item])).values()], status: 'ready', requestedPage: page, retryable: false })),
      catchError((error: unknown) => {
        this.catalog.set({ ...previous, status: 'error', requestedPage: page, retryable: this.retryable(error) }); return EMPTY;
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
    this.companyRequests.pipe(switchMap(id => {
      this.selectedCompany.set(null); this.referenceMessage.set('');
      if (id === null) { this.referenceState.set('idle'); return EMPTY; }
      this.referenceState.set('loading');
      return this.references.getCompanyById(id).pipe(tap(company => {
        if (company.id !== id) throw new Error('Reference mismatch');
        this.selectedCompany.set(company); this.referenceState.set('ready');
      }), catchError((error: unknown) => {
        this.referenceState.set('error'); this.referenceRetryable.set(this.retryable(error));
        this.referenceMessage.set(error instanceof HttpErrorResponse && error.status === 404
          ? 'Cette entreprise n’existe pas ou n’est plus disponible. Sélectionnez une autre entreprise.'
          : 'La référence entreprise ne peut pas être vérifiée. Vos saisies sont conservées.');
        return EMPTY;
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
    this.catalogRequests.next(1); this.companyRequests.next(this.initialCompanyId);
  }

  selectCompany(id: number | null): void {
    if (this.state() === 'saving' || this.state() === 'success' || this.uncertain()) return;
    this.companyId.set(id); this.companyRequests.next(id);
  }
  loadMoreCompanies(): void { const c = this.catalog(); if (c.status === 'ready' && c.page < c.pages) this.catalogRequests.next(c.page + 1); }
  retryCatalog(): void { const c = this.catalog(); if (c.status === 'error' && c.retryable) this.catalogRequests.next(c.requestedPage); }
  retryCompany(): void { if (this.referenceState() === 'error' && this.referenceRetryable()) this.companyRequests.next(this.companyId()); }
  verifyCompany(): void {
    if (this.state() === 'error' && !this.uncertain() && this.companyId() !== null) this.companyRequests.next(this.companyId());
  }
  clearFieldErrors(): void { this.fieldErrors.set({}); }
  acknowledgeVerification(): void { this.uncertain.set(false); }
  cancel(): void { void this.router.navigate(['/sites'], { queryParams: this.listQuery() }); }

  save(body: SiteCreate): void {
    const company = this.selectedCompany();
    if (this.state() === 'saving' || this.state() === 'success' || this.uncertain() || !company || body.company_id !== company.id) return;
    const payload: SiteCreate = { company_id: company.id, name: body.name, code: body.code,
      ...(Object.hasOwn(body, 'description') ? { description: body.description } : {}) };
    this.state.set('saving'); this.fieldErrors.set({}); this.message.set('');
    this.api.create(payload).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ next: site => {
      this.created.set(site); this.state.set('success'); void this.openCreated(site);
    }, error: (error: unknown) => this.saveError(error) });
  }
  private async openCreated(site: SiteRead): Promise<void> {
    try {
      const navigated = await this.router.navigate(['/sites', site.id], { queryParams: { ...this.listQuery(), company_id: site.company_id }, state: { createdSiteId: site.id } });
      if (navigated && !this.notified) { this.notified = true; this.toastr.success('Site créé avec succès.', ''); }
    } catch { this.message.set('Le site est créé, mais sa fiche n’a pas pu être ouverte. Utilisez le lien ci-dessous.'); }
  }
  private saveError(error: unknown): void {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    const fields: SiteFieldErrors = {};
    if (status === 422 && error instanceof HttpErrorResponse && Array.isArray(error.error?.detail)) {
      for (const item of error.error.detail) {
        if (Array.isArray(item?.loc) && item.loc.length === 2 && item.loc[0] === 'body'
          && ['company_id', 'name', 'code', 'description'].includes(item.loc[1])) fields[item.loc[1] as SiteField] = 'Cette valeur n’est pas acceptée par le serveur.';
      }
    }
    if (status === 404) {
      this.selectedCompany.set(null); this.referenceState.set('error'); this.referenceRetryable.set(true);
      this.referenceMessage.set('L’entreprise de rattachement doit être vérifiée avant une nouvelle soumission.');
    }
    this.fieldErrors.set(fields); this.uncertain.set(status === 0 || status >= 500);
    this.message.set(status === 409 ? 'Le serveur signale un conflit. Vérifiez l’entreprise de rattachement et le code du site. La cause exacte n’est pas précisée.'
      : status === 404 ? 'L’entreprise de rattachement peut être devenue indisponible. Vos saisies sont conservées.'
      : status === 422 ? 'Le serveur a refusé les données. Vérifiez les champs signalés ; une autre contrainte peut aussi être en cause.'
      : this.uncertain() ? 'La création n’a pas pu être confirmée. Le site peut avoir été créé. Vérifiez la liste avant toute nouvelle soumission.'
      : 'Le serveur a refusé la création. Vos saisies sont conservées.');
    this.state.set('error');
    const first = (['company_id', 'name', 'code', 'description'] as const).find(field => fields[field]);
    if (first) {
      const focus = afterNextRender(() => this.editor()?.focusField(first), { injector: this.injector });
      this.destroyRef.onDestroy(() => focus.destroy());
    }
  }
  private retryable(error: unknown): boolean { return error instanceof HttpErrorResponse && (error.status === 0 || error.status >= 500); }
  canLeave(): boolean {
    if (this.state() === 'saving') return false;
    return this.state() === 'success' || !this.editor()?.hasChanges()
      || (this.document.defaultView?.confirm('Quitter cette page et abandonner les modifications non enregistrées ?') ?? false);
  }
  @HostListener('window:beforeunload', ['$event'])
  protectUnload(event: BeforeUnloadEvent): void {
    if (this.state() === 'saving' || (this.state() !== 'success' && this.editor()?.hasChanges())) { event.preventDefault(); event.returnValue = ''; }
  }
}
