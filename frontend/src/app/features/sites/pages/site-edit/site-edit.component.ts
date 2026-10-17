import { DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, HostListener, Injector, afterNextRender, computed, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NbToastrService } from '@nebular/theme';
import { EMPTY, Subject, catchError, distinctUntilChanged, map, startWith, switchMap, takeUntil, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { CompanyRead, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { formatAdministrativeDateTime } from '../../../../shared/utils/datetime-display';
import { SiteFormComponent, SiteFieldErrors } from '../../components/site-form/site-form.component';
import { SitesApiService } from '../../data-access/sites-api.service';
import { SiteUpdate } from '../../models/site-write.model';

const positive = (raw: string | null, fallback: number | null, max = Number.MAX_SAFE_INTEGER) =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= max ? Number(raw) : fallback;
type ReadError = { title: string; message: string; retryable: boolean };

@Component({
  selector: 'app-site-edit', standalone: true,
  imports: [SiteFormComponent, RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './site-edit.component.html', styleUrl: './site-edit.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SiteEditComponent {
  private readonly api = inject(SitesApiService);
  private readonly references = inject(ReferenceDataApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });
  private readonly toastr = inject(NbToastrService);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly reload = new Subject<void>();
  private readonly companyReload = new Subject<void>();
  private readonly routeChanged = new Subject<void>();
  private generation = 0;
  private notified = false;
  readonly original = signal<SiteRead | null>(null);
  readonly company = signal<CompanyRead | null>(null);
  readonly referenceState = signal<'loading' | 'ready' | 'error'>('loading');
  readonly referenceError = signal<ReadError>({ title: '', message: '', retryable: false });
  readonly loadError = signal<ReadError>({ title: '', message: '', retryable: false });
  readonly state = signal<'loading' | 'load-error' | 'idle' | 'saving' | 'success' | 'error'>('loading');
  readonly editor = viewChild(SiteFormComponent);
  readonly fieldErrors = signal<SiteFieldErrors>({});
  readonly message = signal('');
  readonly notice = signal('');
  readonly uncertain = signal(false);
  readonly formatDateTime = formatAdministrativeDateTime;
  readonly companyLabel = computed(() => this.company() ? businessReferenceLabel(this.company()!)
    : this.referenceState() === 'loading' ? 'Chargement de l’entreprise...' : 'Entreprise indisponible');
  readonly listQuery = computed(() => {
    const site = this.original(), params = this.params();
    const companyId = positive(params.get('company_id'), null) ?? site?.company_id;
    const search = params.get('search')?.trim() ?? '';
    return { ...(companyId != null ? { company_id: companyId } : {}), page: positive(params.get('page'), 1)!,
      page_size: positive(params.get('page_size'), 20, 100)!, ...(search && search.length <= 100 ? { search } : {}) };
  });

  constructor() {
    this.route.paramMap.pipe(map(params => params.get('siteId')), distinctUntilChanged(), switchMap(raw => {
      this.routeChanged.next(); this.generation++; this.notified = false;
      this.original.set(null); this.company.set(null); this.uncertain.set(false);
      this.fieldErrors.set({}); this.message.set(''); this.notice.set('');
      const id = positive(raw, null);
      if (id === null) {
        this.loadError.set({ title: 'Identifiant invalide', message: 'Revenez à la liste pour sélectionner un site.', retryable: false });
        this.state.set('load-error'); return EMPTY;
      }
      return this.reload.pipe(startWith(undefined), switchMap(() => {
        this.state.set('loading');
        return this.api.getById(id).pipe(tap(site => {
          this.original.set(site); this.company.set(null); this.state.set('idle');
        }), switchMap(site => this.companyReload.pipe(startWith(undefined), switchMap(() => {
          this.referenceState.set('loading');
          return this.references.getCompanyById(site.company_id).pipe(tap(company => {
            if (company.id !== site.company_id) throw new Error('Reference mismatch');
            this.company.set(company); this.referenceState.set('ready');
          }), catchError((error: unknown) => {
            this.company.set(null); this.referenceError.set(this.readError(error, true)); this.referenceState.set('error'); return EMPTY;
          }));
        }))), catchError((error: unknown) => {
          this.loadError.set(this.readError(error, false)); this.state.set('load-error'); return EMPTY;
        }));
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  retryLoad(): void { if (this.state() === 'load-error' && this.loadError().retryable) this.reload.next(); }
  retryCompany(): void { if (this.referenceState() === 'error' && this.referenceError().retryable) this.companyReload.next(); }
  clearFieldErrors(): void { this.fieldErrors.set({}); this.notice.set(''); }
  acknowledgeVerification(): void { this.uncertain.set(false); }
  cancel(): void { void this.router.navigate(this.original() ? ['/sites', this.original()!.id] : ['/sites'], { queryParams: this.listQuery() }); }

  save(_body: SiteUpdate): void {
    const site = this.original();
    if (!site || !this.editor() || !['idle', 'error'].includes(this.state()) || this.uncertain() || this.referenceState() !== 'ready') return;
    // The form owns the diff; never trust additional caller properties or company_id.
    const patch = this.editor()!.changes();
    if (!Object.keys(patch).length) { this.notice.set('Aucune modification à enregistrer.'); return; }
    if (this.editor()!.form.invalid) return;
    this.state.set('saving'); this.message.set(''); this.notice.set(''); this.fieldErrors.set({});
    const generation = this.generation;
    this.api.update(site.id, patch).pipe(takeUntil(this.routeChanged), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: result => {
        this.state.set('success'); void this.openUpdated(result, generation);
      }, error: (error: unknown) => this.saveError(error)
    });
  }
  private async openUpdated(site: SiteRead, generation: number): Promise<void> {
    try {
      const navigated = await this.router.navigate(['/sites', site.id], { queryParams: this.listQuery(), state: { updatedSiteId: site.id } });
      if (navigated && generation === this.generation && !this.notified) {
        this.notified = true; this.toastr.success('Site modifié avec succès.', '');
      }
    } catch { this.message.set('Le site est modifié, mais sa fiche n’a pas pu être ouverte. Utilisez le lien ci-dessous.'); }
  }
  private saveError(error: unknown): void {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    const fields: SiteFieldErrors = {};
    if (status === 422 && error instanceof HttpErrorResponse && Array.isArray(error.error?.detail)) {
      for (const item of error.error.detail) {
        if (Array.isArray(item?.loc) && item.loc.length === 2 && item.loc[0] === 'body'
          && ['name', 'code', 'description'].includes(item.loc[1])) fields[item.loc[1] as 'name' | 'code' | 'description'] = 'Cette valeur n’est pas acceptée par le serveur.';
      }
    }
    this.fieldErrors.set(fields); this.uncertain.set(status === 0 || status >= 500);
    this.message.set(status === 404 ? 'Ce site n’existe plus ou n’est plus disponible. Vos saisies sont conservées ; aucune recréation automatique.'
      : status === 409 ? 'Le serveur signale un conflit. La cause exacte n’est pas précisée. Vos saisies sont conservées.'
      : status === 422 ? 'Le serveur a refusé les données. Vérifiez les champs signalés ; une autre contrainte peut aussi être en cause.'
      : this.uncertain() ? 'La modification n’a pas pu être confirmée. Le site peut avoir été modifié. Vérifiez la fiche avant toute nouvelle soumission.'
      : 'Le serveur a refusé la modification. Vos saisies sont conservées.');
    this.state.set('error');
    const first = (['name', 'code', 'description'] as const).find(field => fields[field]);
    if (first) {
      const focus = afterNextRender(() => this.editor()?.focusField(first), { injector: this.injector });
      this.destroyRef.onDestroy(() => focus.destroy());
    }
  }
  private readError(error: unknown, company: boolean): ReadError {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    return { title: status === 404 ? company ? 'Entreprise introuvable' : 'Site introuvable (404)'
      : company ? 'Référence entreprise indisponible' : 'Chargement impossible',
      message: company ? 'Le rattachement reste inchangé. La référence entreprise doit être disponible avant l’enregistrement.'
        : status === 404 ? 'Ce site n’existe pas ou n’est plus disponible.'
        : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
        : 'Les informations du site ne peuvent pas être chargées.', retryable: status === 0 || status >= 500 };
  }
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
