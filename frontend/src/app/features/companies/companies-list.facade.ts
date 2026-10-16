import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { CompaniesApiService } from './data-access/companies-api.service';
import { CompaniesQuery, CompaniesState } from './models/companies-state.model';

@Injectable()
export class CompaniesListFacade {
  private readonly api = inject(CompaniesApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly requests = new Subject<Readonly<CompaniesQuery>>();
  private readonly current = signal<CompaniesState>({ status: 'idle' });
  private readonly applied = signal<Readonly<CompaniesQuery> | null>(null);
  readonly state = this.current.asReadonly();
  readonly query = this.applied.asReadonly();

  constructor() {
    this.requests.pipe(switchMap(query => {
      this.current.set({ status: 'loading', query });
      return this.api.list(query).pipe(
        tap(data => this.current.set({ status: data.total === 0 ? 'empty' : 'success', query, data })),
        catchError((error: unknown) => {
          const status = error instanceof HttpErrorResponse ? error.status : -1;
          this.current.set({ status: 'error', query, error: {
            message: status === 422 ? 'Vérifiez les paramètres de recherche et de pagination.'
              : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
              : 'La liste des entreprises ne peut pas être chargée. Réessayez ou modifiez votre recherche.',
            retryable: status === 0 || status >= 500
          } });
          return EMPTY;
        })
      );
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  load(query: CompaniesQuery): void {
    const snapshot = Object.freeze({ ...query });
    this.applied.set(snapshot);
    this.requests.next(snapshot);
  }

  retry(): void {
    const state = this.state();
    if (state.status === 'error' && state.error.retryable) this.load(state.query);
  }
}
