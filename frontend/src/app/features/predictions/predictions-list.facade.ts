import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, Subject, catchError, of, switchMap, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../core/api/reference-data-api.service';
import { CompanyRead, EquipmentRead, SiteRead } from '../../core/models/reference-data.model';
import { PredictionsApiService } from './data-access/predictions-api.service';
import { PredictionsQuery, PredictionsState } from './models/predictions-state.model';
import { positiveId } from './utils/prediction-query';
import { validatePredictionPeriod } from './utils/prediction-time';

class ScopeError extends Error {}

@Injectable()
export class PredictionsListFacade {
  private readonly references = inject(ReferenceDataApiService);
  private readonly api = inject(PredictionsApiService);
  private readonly requests = new Subject<Readonly<PredictionsQuery> | null>();
  private readonly current = signal<PredictionsState>({ status: 'idle' });
  private readonly applied = signal<Readonly<PredictionsQuery> | null>(null);
  private readonly selectedCompany = signal<CompanyRead | null>(null);
  private readonly selectedSite = signal<SiteRead | null>(null);
  private readonly selectedEquipment = signal<EquipmentRead | null>(null);
  readonly state = this.current.asReadonly();
  readonly query = this.applied.asReadonly();
  readonly company = this.selectedCompany.asReadonly();
  readonly site = this.selectedSite.asReadonly();
  readonly equipment = this.selectedEquipment.asReadonly();

  constructor() {
    this.requests.pipe(switchMap(query => {
      if (!query) { this.current.set({ status: 'idle' }); return EMPTY; }
      try {
        for (const id of [query.company_id, query.site_id, query.equipment_id]) {
          if (id !== undefined && !positiveId(id)) throw new ScopeError('Sélectionnez des références valides.');
        }
        if ((query.site_id !== undefined && query.company_id === undefined)
          || (query.equipment_id !== undefined && query.site_id === undefined)) {
          throw new ScopeError('Sélectionnez explicitement l’entreprise, puis le site et l’équipement.');
        }
        validatePredictionPeriod(query.start_time, query.end_time);
      } catch (error) {
        this.clearReferences();
        this.current.set({ status: 'error', retryable: false, message: error instanceof ScopeError ? error.message : 'Période invalide : début et fin inclus, égalité permise, offsets requis.' });
        return EMPTY;
      }
      if (query.company_id === undefined) { this.current.set({ status: 'idle' }); return EMPTY; }
      this.current.set({ status: 'loading' });
      let verified = false;
      const equipmentRead: Observable<EquipmentRead | null> = query.equipment_id === undefined ? of(null) : this.references.getEquipmentById(query.equipment_id);
      return equipmentRead.pipe(
        switchMap(equipment => {
          if (equipment && (equipment.id !== query.equipment_id || equipment.site_id !== query.site_id)) {
            throw new ScopeError('Cet équipement ne correspond pas au site sélectionné.');
          }
          if (query.equipment_id !== undefined && !equipment) throw new ScopeError('Référence équipement invalide.');
          const siteRead: Observable<SiteRead | null> = query.site_id === undefined ? of(null) : this.references.getSiteById(query.site_id);
          return siteRead.pipe(
            switchMap(site => {
              if (site && (site.id !== query.site_id || site.company_id !== query.company_id)) {
                throw new ScopeError('Ce site ne correspond pas à l’entreprise sélectionnée.');
              }
              if (query.site_id !== undefined && !site) throw new ScopeError('Référence site invalide.');
              return this.references.getCompanyById(query.company_id!).pipe(switchMap(company => {
                if (!company || company.id !== query.company_id) throw new ScopeError('Référence entreprise incohérente.');
                this.selectedCompany.set(company); this.selectedSite.set(site); this.selectedEquipment.set(equipment);
                if (!site || !equipment) { this.current.set({ status: 'idle' }); return EMPTY; }
                verified = true;
                return this.api.list({ equipment_id: equipment.id, page: query.page, page_size: query.page_size,
                  prediction_type: query.prediction_type, level: query.level, is_alert: query.is_alert,
                  start_time: query.start_time, end_time: query.end_time }).pipe(tap(data => {
                    if (data.items.some(item => item.equipment_id !== equipment.id)) throw new ScopeError('La réponse contient des prédictions d’un autre équipement.');
                    this.current.set({ status: data.total === 0 ? 'empty' : data.items.length === 0 ? 'out-of-range' : 'success', data });
                  }));
              }));
            })
          );
        }), catchError((error: unknown) => {
          if (!verified) this.clearReferences();
          const status = error instanceof HttpErrorResponse ? error.status : -1;
          this.current.set({ status: 'error', retryable: !(error instanceof ScopeError) && !(error instanceof TypeError) && (status === 0 || status >= 500),
            message: error instanceof ScopeError ? error.message
              : error instanceof TypeError ? 'La réponse ou les filtres Prédictions sont invalides. Aucun résultat n’est affiché.'
              : status === 404 ? 'Une référence n’existe plus. Vérifiez l’entreprise, le site et l’équipement.'
              : status === 422 ? 'Vérifiez les références, les filtres et la pagination.'
              : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
              : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
              : 'Les prédictions ou leurs références ne peuvent pas être chargées.' });
          return EMPTY;
        })
      );
    }), takeUntilDestroyed(inject(DestroyRef))).subscribe();
  }

  load(query: PredictionsQuery | null): void {
    if (!query || this.company()?.id !== query.company_id) this.clearReferences();
    else if (this.site()?.id !== query.site_id) { this.selectedSite.set(null); this.selectedEquipment.set(null); }
    else if (this.equipment()?.id !== query.equipment_id) this.selectedEquipment.set(null);
    this.applied.set(query ? Object.freeze({ ...query }) : null);
    this.requests.next(this.applied());
  }
  block(message: string): void {
    this.load(null);
    this.current.set({ status: 'error', message, retryable: false });
  }
  retry(): void { const state = this.state(); if (state.status === 'error' && state.retryable) this.load(this.query()); }
  private clearReferences(): void { this.selectedCompany.set(null); this.selectedSite.set(null); this.selectedEquipment.set(null); }
}
