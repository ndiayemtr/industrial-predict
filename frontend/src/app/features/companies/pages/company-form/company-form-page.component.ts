import { DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, HostListener, Injector, afterNextRender, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NbToastrService } from '@nebular/theme';
import { CompanyFormComponent, CompanyField, CompanyFieldErrors } from '../../components/company-form/company-form.component';
import { CompaniesApiService } from '../../data-access/companies-api.service';
import { CompanyCreate, CompanyUpdate } from '../../models/company-write.model';
import { CompanyRead } from '../../../../core/models/reference-data.model';
import { formatAdministrativeDateTime } from '../../../../shared/utils/datetime-display';
import { EMPTY, Subject, catchError, distinctUntilChanged, map, startWith, switchMap, tap } from 'rxjs';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';

type SaveState = 'loading' | 'load-error' | 'idle' | 'saving' | 'success' | 'error';

@Component({
  selector: 'app-company-form-page', standalone: true,
  imports: [CompanyFormComponent, RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './company-form-page.component.html', styleUrl: './company-form-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CompanyFormPageComponent {
  readonly formatDateTime = formatAdministrativeDateTime;
  private readonly api = inject(CompaniesApiService);
  private readonly toastr = inject(NbToastrService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly reloads = new Subject<void>();
  readonly editMode = this.route.snapshot.data['mode'] === 'edit';
  readonly original = signal<CompanyRead | null>(null);
  readonly loadError = signal({ title: '', message: '', retryable: false });
  readonly notice = signal('');
  readonly editor = viewChild(CompanyFormComponent);
  readonly state = signal<SaveState>('idle');
  readonly message = signal('');
  readonly fieldErrors = signal<CompanyFieldErrors>({});
  readonly uncertain = signal(false);
  readonly listQuery = (() => {
    const params = this.route.snapshot.queryParamMap;
    const positive = (raw: string | null, fallback: number, max = Number.MAX_SAFE_INTEGER) =>
      raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= max ? Number(raw) : fallback;
    const search = params.get('search')?.trim() ?? '';
    return { page: positive(params.get('page'), 1), page_size: positive(params.get('page_size'), 20, 100),
      ...(search && search.length <= 100 ? { search } : {}) };
  })();

  constructor() {
    if (!this.editMode) return;
    this.route.paramMap.pipe(map(params => params.get('companyId')), distinctUntilChanged(), switchMap(raw => {
      this.original.set(null);
      this.uncertain.set(false);
      this.fieldErrors.set({});
      this.notice.set('');
      if (raw === null || !/^\d+$/.test(raw) || !Number.isSafeInteger(Number(raw)) || Number(raw) < 1) {
        this.state.set('load-error');
        this.loadError.set({ title: 'Identifiant invalide', message: 'Revenez à la liste pour sélectionner une entreprise.', retryable: false });
        return EMPTY;
      }
      return this.reloads.pipe(startWith(undefined), switchMap(() => {
        this.state.set('loading');
        return this.api.getById(Number(raw)).pipe(
          tap(company => { this.original.set(company); this.state.set('idle'); }),
          catchError((error: unknown) => {
            const status = error instanceof HttpErrorResponse ? error.status : -1;
            this.loadError.set({ title: status === 404 ? 'Entreprise introuvable' : 'Chargement impossible',
              message: status === 404 ? 'Cette entreprise n’existe pas ou n’est plus disponible.'
                : status === 422 ? 'L’identifiant demandé n’est pas accepté par le serveur.'
                : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.' : 'Les informations de l’entreprise ne peuvent pas être chargées.',
              retryable: status === 0 || status >= 500 });
            this.state.set('load-error');
            return EMPTY;
          })
        );
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  retryLoad(): void {
    if (this.state() === 'load-error' && this.loadError().retryable) this.reloads.next();
  }

  save(body: CompanyCreate): void {
    if (this.state() === 'saving' || this.state() === 'success' || this.uncertain()) return;
    const original = this.original();
    if (this.editMode && (!original || this.state() === 'loading' || this.state() === 'load-error')) return;
    const patch: CompanyUpdate = {};
    if (original) {
      const raw = this.editor()!.form.getRawValue();
      if (raw.name !== original.name && body.name !== original.name) patch.name = body.name;
      if (raw.code !== original.code && body.code !== original.code) patch.code = body.code;
      if (raw.description !== (original.description ?? '')) patch.description = raw.description === '' ? null : raw.description;
      if (Object.keys(patch).length === 0) {
        this.notice.set('Aucune modification à enregistrer.');
        return;
      }
    }
    this.state.set('saving');
    this.message.set('');
    this.fieldErrors.set({});
    this.notice.set('');
    const request = original ? this.api.update(original.id, patch) : this.api.create(body);
    request.pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: company => {
        this.state.set('success');
        // The application-scoped overlay survives destruction of this routed page.
        this.toastr.success(original ? 'Entreprise modifiée avec succès.' : 'Entreprise créée avec succès.', '');
        void this.router.navigate(['/companies', company.id], { queryParams: this.listQuery,
          state: original ? { updatedCompanyId: company.id } : { createdCompanyId: company.id } });
      },
      error: (error: unknown) => {
        const status = error instanceof HttpErrorResponse ? error.status : -1;
        const fields: CompanyFieldErrors = {};
        if (status === 409) fields.code = 'Ce code est déjà utilisé par une autre entreprise.';
        if (status === 422 && error instanceof HttpErrorResponse && Array.isArray(error.error?.detail)) {
          for (const item of error.error.detail) {
            if (!Array.isArray(item?.loc) || item.loc.length !== 2 || item.loc[0] !== 'body') continue;
            const field = item.loc[1];
            if (['name', 'code', 'description'].includes(field)) fields[field as CompanyField] = 'Cette valeur n’est pas acceptée par le serveur.';
          }
        }
        this.fieldErrors.set(fields);
        const uncertain = status === 0 || status >= 500;
        this.uncertain.set(uncertain);
        this.message.set(this.editMode && status === 404 ? 'Cette entreprise n’existe plus. Vos saisies sont conservées ; revenez à la liste. Aucune recréation automatique ne sera effectuée.'
          : status === 409 ? 'Le serveur signale un conflit de code. Vérifiez le champ Code.'
          : status === 422 ? 'Le serveur a refusé les données. Vérifiez les champs signalés ; une autre contrainte de validation peut aussi être en cause.'
          : uncertain ? `L’enregistrement n’a pas pu être confirmé (${status === 0 ? 'erreur réseau' : 'erreur serveur'}). L’entreprise peut avoir été ${this.editMode ? 'modifiée' : 'créée'}. Vérifiez ${this.editMode ? 'la fiche' : 'la liste'} avant toute nouvelle soumission.`
          : `Le serveur a refusé ${this.editMode ? 'la modification' : 'la création'}. Vos saisies sont conservées.`);
        this.state.set('error');
        const first = (['name', 'code', 'description'] as const).find(field => fields[field]);
        if (first) {
          const focus = afterNextRender(() => this.editor()?.focusField(first), { injector: this.injector });
          this.destroyRef.onDestroy(() => focus.destroy());
        }
      }
    });
  }

  acknowledgeVerification(): void { this.uncertain.set(false); }
  clearFieldErrors(): void { this.fieldErrors.set({}); }
  cancel(): void { void this.router.navigate(this.editMode && this.original() ? ['/companies', this.original()!.id] : ['/companies'], { queryParams: this.listQuery }); }

  canLeave(): boolean {
    if (this.state() === 'saving') return false;
    return this.state() === 'success' || !this.editor()?.hasChanges()
      || (this.document.defaultView?.confirm('Quitter cette page et abandonner les modifications non enregistrées ?') ?? false);
  }

  @HostListener('window:beforeunload', ['$event'])
  protectUnload(event: BeforeUnloadEvent): void {
    if (this.state() === 'saving' || (this.state() !== 'success' && this.editor()?.hasChanges())) {
      event.preventDefault();
      event.returnValue = '';
    }
  }
}
