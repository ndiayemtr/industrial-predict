import { DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, HostListener, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { CompanyFormComponent, CompanyField, CompanyFieldErrors } from '../../components/company-form/company-form.component';
import { CompaniesApiService } from '../../data-access/companies-api.service';
import { CompanyCreate } from '../../models/company-write.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';

type SaveState = 'idle' | 'saving' | 'success' | 'error';

@Component({
  selector: 'app-company-form-page', standalone: true,
  imports: [CompanyFormComponent, RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './company-form-page.component.html', styleUrl: './company-form-page.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class CompanyFormPageComponent {
  private readonly api = inject(CompaniesApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
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

  save(body: CompanyCreate): void {
    if (this.state() === 'saving' || this.state() === 'success' || this.uncertain()) return;
    this.state.set('saving');
    this.message.set('');
    this.fieldErrors.set({});
    this.api.create(body).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: company => {
        this.state.set('success');
        void this.router.navigate(['/companies', company.id], { queryParams: this.listQuery, state: { createdCompanyId: company.id } });
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
        this.message.set(status === 409 ? 'Le serveur signale un conflit de code. Vérifiez le champ Code.'
          : status === 422 ? 'Le serveur a refusé les données. Vérifiez les champs signalés ; une autre contrainte de validation peut aussi être en cause.'
          : uncertain ? `L’enregistrement n’a pas pu être confirmé (${status === 0 ? 'erreur réseau' : 'erreur serveur'}). L’entreprise peut avoir été créée. Vérifiez la liste avant toute nouvelle soumission.`
          : 'Le serveur a refusé la création. Vos saisies sont conservées.');
        this.state.set('error');
      }
    });
  }

  acknowledgeVerification(): void { this.uncertain.set(false); }
  clearFieldErrors(): void { this.fieldErrors.set({}); }
  cancel(): void { void this.router.navigate(['/companies'], { queryParams: this.listQuery }); }

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
