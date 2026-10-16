import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../core/api/reference-data-api.service';
import { CompanyRead } from '../../core/models/reference-data.model';
import { SitesApiService } from './data-access/sites-api.service';
import { SitesQuery, SitesState } from './models/sites-state.model';

@Injectable()
export class SitesListFacade {
  private readonly api = inject(SitesApiService);
  private readonly references = inject(ReferenceDataApiService);
  private readonly requests = new Subject<Readonly<SitesQuery> | null>();
  private readonly current = signal<SitesState>({ status: 'idle' });
  private readonly applied = signal<Readonly<SitesQuery> | null>(null);
  private readonly selected = signal<CompanyRead | null>(null);
  readonly state = this.current.asReadonly();
  readonly query = this.applied.asReadonly();
  readonly company = this.selected.asReadonly();

  constructor() {
    this.requests.pipe(switchMap(query => {
      this.selected.set(null);
      if (!query) { this.current.set({ status: 'idle' }); return EMPTY; }
      this.current.set({ status: 'loading', query });
      // A filtered empty page does not prove the company exists. Verify its
      // reference even when its option is outside the loaded catalog pages.
      return this.references.getCompanyById(query.company_id).pipe(
        catchError(error => { this.fail(query, error, true); return EMPTY; }),
        switchMap(company => {
          this.selected.set(company);
          return this.api.list(query).pipe(
            tap(data => this.current.set({ status: data.total === 0 ? 'empty' : 'success', query, data })),
            catchError(error => { this.fail(query, error, false); return EMPTY; })
          );
        })
      );
    }), takeUntilDestroyed(inject(DestroyRef))).subscribe();
  }

  load(query: SitesQuery | null): void {
    const snapshot = query ? Object.freeze({ ...query }) : null;
    this.applied.set(snapshot);
    this.requests.next(snapshot);
  }

  retry(): void {
    const state = this.state();
    if (state.status === 'error' && state.retryable) this.load(state.query);
  }

  private fail(query: Readonly<SitesQuery>, error: unknown, company: boolean): void {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    this.current.set({ status: 'error', query, retryable: status === 0 || status >= 500,
      message: company && status === 404 ? 'Cette entreprise n’existe pas ou n’est plus disponible. Sélectionnez une autre entreprise.'
        : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
        : status === 422 ? 'Vérifiez l’entreprise, la recherche et les paramètres de pagination.'
        : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
        : company ? 'Les informations de l’entreprise ne peuvent pas être chargées.'
        : 'La liste des sites ne peut pas être chargée. Vous pouvez modifier les filtres ou réessayer.' });
  }
}
