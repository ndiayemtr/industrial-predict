import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, Subject, catchError, switchMap, tap } from 'rxjs';
import { Page } from '../../../core/models/page.model';
import { CompanyRead } from '../../../core/models/reference-data.model';
import { positiveId } from './prediction-query';

interface Catalog extends Page<CompanyRead> {
  scope: number | null;
  status: 'idle' | 'loading' | 'ready' | 'error';
  requestedPage: number;
  retryable: boolean;
}
const empty = (): Catalog => ({ items: [], total: 0, page: 0, page_size: 50, pages: 0,
  scope: null, status: 'idle', requestedPage: 1, retryable: false });

// Component-owned catalogs: no global cache, no automatic exhaustive loading.
export class PredictionReferenceCatalog {
  private readonly current = signal<Catalog>(empty());
  readonly state = this.current.asReadonly();
  private readonly requests = new Subject<{ scope: number | null; page: number } | null>();

  constructor(destroy: DestroyRef, fetch: (scope: number | null, page: number) => Observable<Page<CompanyRead>>) {
    this.requests.pipe(switchMap(request => {
      if (!request) { this.current.set(empty()); return EMPTY; }
      const previous = request.page > 1 && this.state().scope === request.scope ? this.state() : empty();
      this.current.set({ ...previous, scope: request.scope, status: 'loading', requestedPage: request.page });
      return fetch(request.scope, request.page).pipe(tap(data => {
        if (!data || !Array.isArray(data.items) || data.page !== request.page || data.page_size !== 50
          || !Number.isSafeInteger(data.total) || data.total < 0 || data.pages !== Math.ceil(data.total / 50)
          || data.items.length > 50 || data.items.some(item => !item || !positiveId(item.id) || typeof item.name !== 'string' || typeof item.code !== 'string')) {
          throw new TypeError('Catalogue de références invalide.');
        }
        const items = [...new Map([...previous.items, ...data.items].map(item => [item.id, item])).values()];
        this.current.set({ ...data, items, scope: request.scope, status: 'ready', requestedPage: request.page, retryable: false });
      }), catchError((error: unknown) => {
        const status = error instanceof HttpErrorResponse ? error.status : -1;
        this.current.set({ ...previous, scope: request.scope, status: 'error', requestedPage: request.page, retryable: status === 0 || status >= 500 });
        return EMPTY;
      }));
    }), takeUntilDestroyed(destroy)).subscribe();
  }
  load(scope: number | null, page = 1): void { this.requests.next({ scope, page }); }
  clear(): void { this.requests.next(null); }
  ensure(scope: number | undefined): void {
    if (scope === undefined) { if (this.state().status !== 'idle') this.clear(); }
    else if (this.state().scope !== scope) this.load(scope);
  }
  more(): void { const state = this.state(); if (state.status === 'ready' && state.page < state.pages) this.load(state.scope, state.page + 1); }
  retry(): void { const state = this.state(); if (state.status === 'error' && state.retryable) this.load(state.scope, state.requestedPage); }
}
