import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, Subject, catchError, of, switchMap, tap, throwError } from 'rxjs';
import { ReferenceDataApiService } from '../../core/api/reference-data-api.service';
import { CompanyRead, EquipmentRead, SiteRead } from '../../core/models/reference-data.model';
import { MaintenanceApiService } from './data-access/maintenance-api.service';
import { MaintenanceQuery, MaintenanceState } from './models/maintenance-state.model';

import { validateMeasurementPeriod } from '../measurements/utils/measurement-time';

const positive = (id: number | undefined): id is number => Number.isSafeInteger(id) && Number(id) > 0;
class ScopeError extends Error {}

@Injectable()
export class MaintenanceListFacade {
  private readonly references = inject(ReferenceDataApiService);
  private readonly api = inject(MaintenanceApiService);
  private readonly requests = new Subject<Readonly<MaintenanceQuery> | null>();
  private readonly applied = signal<Readonly<MaintenanceQuery> | null>(null);
  private readonly current = signal<MaintenanceState>({ status: 'idle' });
  private readonly selectedCompany = signal<CompanyRead | null>(null);
  private readonly selectedSite = signal<SiteRead | null>(null);
  private readonly selectedEquipment = signal<EquipmentRead | null>(null);
  readonly query = this.applied.asReadonly();
  readonly state = this.current.asReadonly();
  readonly company = this.selectedCompany.asReadonly();
  readonly site = this.selectedSite.asReadonly();
  readonly equipment = this.selectedEquipment.asReadonly();

  constructor() {
    this.requests.pipe(switchMap(query => {
      if (!query || ![query.company_id, query.site_id, query.equipment_id].some(id => id !== undefined)) {
        this.current.set({ status: 'idle' }); return EMPTY;
      }
      try {
        validateMeasurementPeriod(query.start_time, query.end_time);
        if ((query.site_id !== undefined && query.company_id === undefined)
          || (query.equipment_id !== undefined && query.site_id === undefined))
          throw new ScopeError('Sélectionnez explicitement les trois niveaux du contexte industriel.');
      } catch (error) {
        this.selectedCompany.set(null); this.selectedSite.set(null); this.selectedEquipment.set(null);
        this.current.set({ status: 'error', retryable: false, message: error instanceof ScopeError ? error.message : 'Période de création invalide. Aucune lecture effectuée.' });
        return EMPTY;
      }
      this.current.set({ status: 'loading' });
      let referencesVerified = false;
      return this.resolveEquipment(query.equipment_id).pipe(
        switchMap(equipment => {
          if (equipment && query.site_id !== undefined && equipment.site_id !== query.site_id)
            throw new ScopeError('Cet équipement n’appartient pas au site sélectionné.');
          return this.resolveSite(query.site_id ?? equipment?.site_id).pipe(
            switchMap(site => {
              if (site && query.company_id !== undefined && site.company_id !== query.company_id)
                throw new ScopeError('Ce site n’appartient pas à l’entreprise sélectionnée.');
              return this.resolveCompany(query.company_id ?? site?.company_id).pipe(
                switchMap(company => {
                  this.selectedCompany.set(company); this.selectedSite.set(site); this.selectedEquipment.set(equipment);
                  this.applied.set(Object.freeze({ ...query, company_id: company?.id, site_id: site?.id, equipment_id: equipment?.id }));
                  if (!equipment || !site || !company) { this.current.set({ status: 'idle' }); return EMPTY; }
                  referencesVerified = true;
                  return this.api.list({ equipment_id: equipment.id, page: query.page, page_size: query.page_size,
                    status: query.status, search: query.search, maintenance_type: query.maintenance_type, priority: query.priority, start_time: query.start_time, end_time: query.end_time }).pipe(tap(data => {
                    if (data.items.some(item => item.equipment_id !== equipment.id))
                      throw new ScopeError('La réponse contient des interventions d’un autre équipement. Aucun résultat n’est affiché.');
                    this.current.set({ status: data.total === 0 ? 'empty' : 'success', data });
                  }));
                })
              );
            })
          );
        }), catchError((error: unknown) => {
          if (!referencesVerified) {
            this.selectedCompany.set(null); this.selectedSite.set(null); this.selectedEquipment.set(null);
          }
          const status = error instanceof HttpErrorResponse ? error.status : -1;
          this.current.set({ status: 'error', retryable: !(error instanceof ScopeError) && !(error instanceof TypeError) && (status === 0 || status >= 500),
            message: error instanceof ScopeError ? error.message
              : error instanceof TypeError ? 'La réponse Maintenance est invalide. Aucun résultat n’est affiché.'
              : status === 404 ? 'Une référence n’existe plus. Vérifiez l’entreprise, le site et l’équipement.'
              : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
              : status === 422 ? 'Vérifiez les références, les filtres et la pagination.'
              : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
              : 'Les interventions ou leurs références ne peuvent pas être chargées.' });
          return EMPTY;
        })
      );
    }), takeUntilDestroyed(inject(DestroyRef))).subscribe();
  }

  load(query: MaintenanceQuery | null): void {
    if (!query || this.company()?.id !== query.company_id) this.selectedCompany.set(null);
    if (!query || this.site()?.id !== query.site_id || this.site()?.company_id !== query.company_id) this.selectedSite.set(null);
    if (!query || this.equipment()?.id !== query.equipment_id || this.equipment()?.site_id !== query.site_id) this.selectedEquipment.set(null);
    this.applied.set(query ? Object.freeze({ ...query }) : null);
    this.requests.next(this.applied());
  }
  retry(): void { const state = this.state(); if (state.status === 'error' && state.retryable) this.load(this.query()); }
  private resolveEquipment(id: number | undefined): Observable<EquipmentRead | null> {
    if (id === undefined) return of(null);
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez un équipement valide.'));
    return this.references.getEquipmentById(id).pipe(tap(item => {
      if (!item || item.id !== id || !positive(item.site_id)) throw new ScopeError('La référence équipement reçue est incohérente.');
    }));
  }
  private resolveSite(id: number | undefined): Observable<SiteRead | null> {
    if (id === undefined) return of(null);
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez un site valide.'));
    return this.references.getSiteById(id).pipe(tap(item => {
      if (!item || item.id !== id || !positive(item.company_id)) throw new ScopeError('La référence site reçue est incohérente.');
    }));
  }
  private resolveCompany(id: number | undefined): Observable<CompanyRead | null> {
    if (id === undefined) return of(null);
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez une entreprise valide.'));
    return this.references.getCompanyById(id).pipe(tap(item => {
      if (!item || item.id !== id) throw new ScopeError('La référence entreprise reçue est incohérente.');
    }));
  }
}
