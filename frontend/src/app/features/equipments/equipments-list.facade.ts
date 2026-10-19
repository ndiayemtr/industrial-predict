import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, Subject, catchError, of, switchMap, tap, throwError } from 'rxjs';
import { ReferenceDataApiService } from '../../core/api/reference-data-api.service';
import { CompanyRead, SiteRead } from '../../core/models/reference-data.model';
import { EquipmentsApiService } from './data-access/equipments-api.service';
import { EquipmentsQuery, EquipmentsState } from './models/equipments-state.model';

const positive = (id: number | undefined): id is number => Number.isSafeInteger(id) && Number(id) > 0;
class ScopeError extends Error {}

@Injectable()
export class EquipmentsListFacade {
  private readonly references = inject(ReferenceDataApiService);
  private readonly api = inject(EquipmentsApiService);
  private readonly requests = new Subject<Readonly<EquipmentsQuery> | null>();
  private readonly applied = signal<Readonly<EquipmentsQuery> | null>(null);
  private readonly current = signal<EquipmentsState>({ status: 'idle' });
  private readonly selectedCompany = signal<CompanyRead | null>(null);
  private readonly selectedSite = signal<SiteRead | null>(null);
  readonly query = this.applied.asReadonly();
  readonly state = this.current.asReadonly();
  readonly company = this.selectedCompany.asReadonly();
  readonly site = this.selectedSite.asReadonly();

  constructor() {
    this.requests.pipe(switchMap(query => {
      if (!query) { this.current.set({ status: 'idle' }); return EMPTY; }
      if (query.company_id === undefined && query.site_id === undefined) {
        this.current.set({ status: 'idle' }); return EMPTY;
      }
      this.current.set({ status: 'loading' });
      let parents: Observable<SiteRead | null>;
      if (query.company_id !== undefined) {
        parents = this.readCompany(query.company_id).pipe(switchMap(() => query.site_id === undefined
          ? of(null) : this.readSite(query.site_id)));
      } else {
        parents = this.readSite(query.site_id!).pipe(switchMap(site => this.readCompany(site.company_id).pipe(switchMap(() => of(site)))));
      }
      return parents.pipe(switchMap(site => {
        if (!site) { this.current.set({ status: 'idle' }); return EMPTY; }
        const company = this.selectedCompany()!;
        if (site.company_id !== company.id) throw new ScopeError('Ce site n’appartient pas à l’entreprise sélectionnée. Choisissez un site cohérent.');
        this.selectedSite.set(site);
        this.applied.set(Object.freeze({ ...query, company_id: company.id }));
        return this.api.list({ site_id: site.id, page: query.page, page_size: query.page_size,
          search: query.search, status: query.status, criticality: query.criticality }).pipe(tap(data => {
          if (data.items.some(item => item.site_id !== site.id)) throw new ScopeError('La réponse contient des équipements d’un autre site. Aucun résultat n’est affiché.');
          this.current.set({ status: data.total === 0 ? 'empty' : 'success', data });
        }));
      }), catchError((error: unknown) => {
        const status = error instanceof HttpErrorResponse ? error.status : -1;
        this.current.set({ status: 'error', retryable: !(error instanceof ScopeError) && (status === 0 || status >= 500),
          message: error instanceof ScopeError ? error.message
            : status === 404 ? 'L’entreprise ou le site n’existe plus. Vérifiez votre sélection.'
            : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
            : status === 422 ? 'Vérifiez les références, les filtres et les paramètres de pagination.'
            : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
            : 'Les équipements ou leurs références ne peuvent pas être chargés.' });
        return EMPTY;
      }));
    }), takeUntilDestroyed(inject(DestroyRef))).subscribe();
  }

  load(query: EquipmentsQuery | null): void {
    if (!query || this.company()?.id !== query.company_id) this.selectedCompany.set(null);
    if (!query || this.site()?.id !== query.site_id || this.site()?.company_id !== query.company_id) this.selectedSite.set(null);
    this.applied.set(query ? Object.freeze({ ...query }) : null);
    this.requests.next(this.applied());
  }
  retry(): void { const state = this.state(); if (state.status === 'error' && state.retryable) this.load(this.query()); }
  private readCompany(id: number): Observable<CompanyRead> {
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez une entreprise valide.'));
    return this.references.getCompanyById(id).pipe(tap(company => {
      if (company.id !== id) throw new ScopeError('La référence entreprise reçue ne correspond pas à la sélection.');
      this.selectedCompany.set(company);
    }));
  }
  private readSite(id: number): Observable<SiteRead> {
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez un site valide.'));
    return this.references.getSiteById(id).pipe(tap(site => {
      if (site.id !== id || !positive(site.company_id)) throw new ScopeError('La référence site reçue n’est pas cohérente.');
    }));
  }
}
