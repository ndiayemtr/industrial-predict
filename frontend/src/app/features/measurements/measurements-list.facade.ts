import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, Subject, catchError, of, switchMap, tap, throwError } from 'rxjs';
import { ReferenceDataApiService } from '../../core/api/reference-data-api.service';
import { CompanyRead, EquipmentRead, SiteRead } from '../../core/models/reference-data.model';
import { SensorsApiService } from '../sensors/data-access/sensors-api.service';
import { SensorRead } from '../sensors/models/sensor.model';
import { MeasurementsApiService } from './data-access/measurements-api.service';
import { validateMeasurementPeriod } from './utils/measurement-time';
import { MeasurementsQuery, MeasurementsState } from './models/measurements-state.model';

const positive = (id: number | undefined): id is number => Number.isSafeInteger(id) && Number(id) > 0;
class ScopeError extends Error {}

@Injectable()
export class MeasurementsListFacade {
  private readonly references = inject(ReferenceDataApiService);
  private readonly api = inject(MeasurementsApiService);
  private readonly sensorsApi = inject(SensorsApiService);
  private readonly requests = new Subject<Readonly<MeasurementsQuery> | null>();
  private readonly applied = signal<Readonly<MeasurementsQuery> | null>(null);
  private readonly current = signal<MeasurementsState>({ status: 'idle' });
  private readonly selectedSensor = signal<SensorRead | null>(null);
  readonly sensor = this.selectedSensor.asReadonly();
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
      if (!query || ![query.company_id, query.site_id, query.equipment_id, query.sensor_id].some(id => id !== undefined)) {
        this.current.set({ status: 'idle' }); return EMPTY;
      }
      try { validateMeasurementPeriod(query.start_time, query.end_time); } catch {
        this.current.set({ status: 'error', retryable: false, message: 'Période invalide : utilisez des dates avec fuseau et un début strictement antérieur à la fin.' }); return EMPTY;
      }
      this.current.set({ status: 'loading' });
      let referencesVerified = false;
      const cached = this.sensor();
      if (cached && this.equipment() && this.site() && this.company() && cached.id === query.sensor_id && this.equipment()?.id === query.equipment_id && this.site()?.id === query.site_id
        && this.company()?.id === query.company_id) return this.readMeasurements(query);
      return this.resolveSensor(query.sensor_id).pipe(switchMap(sensor => {
        if (sensor && query.equipment_id !== undefined && sensor.equipment_id !== query.equipment_id) throw new ScopeError('Ce capteur n’appartient pas à l’équipement sélectionné.');
        return this.resolveEquipment(query.equipment_id ?? sensor?.equipment_id).pipe(
        switchMap(equipment => {
          if (equipment && query.site_id !== undefined && equipment.site_id !== query.site_id)
            throw new ScopeError('Cet équipement n’appartient pas au site sélectionné.');
          return this.resolveSite(query.site_id ?? equipment?.site_id).pipe(
            switchMap(site => {
              if (site && query.company_id !== undefined && site.company_id !== query.company_id)
                throw new ScopeError('Ce site n’appartient pas à l’entreprise sélectionnée.');
              return this.resolveCompany(query.company_id ?? site?.company_id).pipe(
                switchMap(company => {
                  this.selectedSensor.set(sensor); this.selectedCompany.set(company); this.selectedSite.set(site); this.selectedEquipment.set(equipment);
                  this.applied.set(Object.freeze({ ...query, company_id: company?.id, site_id: site?.id, equipment_id: equipment?.id, sensor_id: sensor?.id }));
                  if (!sensor || !equipment || !site || !company) { this.current.set({ status: 'idle' }); return EMPTY; }
                  referencesVerified = true;
                  return this.readMeasurements(this.applied()!);
                })
              );
            })
          );
        })); }), catchError((error: unknown) => {
          if (!referencesVerified) {
            this.selectedSensor.set(null); this.selectedCompany.set(null); this.selectedSite.set(null); this.selectedEquipment.set(null);
          }
          const status = error instanceof HttpErrorResponse ? error.status : -1;
          this.current.set({ status: 'error', retryable: !(error instanceof ScopeError) && (status === 0 || status >= 500),
            message: error instanceof ScopeError ? error.message
              : status === 404 ? 'Une référence n’existe plus. Vérifiez l’entreprise, le site et l’équipement.'
              : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
              : status === 422 ? 'Vérifiez les références, les filtres et la pagination.'
              : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
              : 'Les mesures ou leurs références ne peuvent pas être chargées.' });
          return EMPTY;
        })
      );
    }), takeUntilDestroyed(inject(DestroyRef))).subscribe();
  }

  load(query: MeasurementsQuery | null): void {
    if (!query || this.sensor()?.id !== query.sensor_id || this.equipment()?.id !== query.equipment_id
      || this.site()?.id !== query.site_id || this.company()?.id !== query.company_id) this.selectedSensor.set(null);
    if (!query || this.company()?.id !== query.company_id) this.selectedCompany.set(null);
    if (!query || this.site()?.id !== query.site_id || this.site()?.company_id !== query.company_id) this.selectedSite.set(null);
    if (!query || this.equipment()?.id !== query.equipment_id || this.equipment()?.site_id !== query.site_id) this.selectedEquipment.set(null);
    this.applied.set(query ? Object.freeze({ ...query }) : null);
    this.requests.next(this.applied());
  }
  retry(): void { const state = this.state(); if (state.status === 'error' && state.retryable) this.load(this.query()); }
  private readMeasurements(query: MeasurementsQuery): Observable<unknown> {
    return this.api.list({ sensor_id: query.sensor_id!, page: query.page, page_size: query.page_size,
      quality: query.quality, start_time: query.start_time, end_time: query.end_time }).pipe(tap(data => {
      this.current.set({ status: data.total === 0 ? 'empty' : 'success', data });
    }), catchError((error: unknown) => {
      const status = error instanceof HttpErrorResponse ? error.status : -1;
      this.current.set({ status: 'error', retryable: status === 0 || status >= 500,
        message: error instanceof TypeError ? 'La réponse contient des données de mesure invalides ou d’un autre capteur.'
          : status === 400 ? 'La période est invalide. Vérifiez les bornes UTC.'
          : status === 422 ? 'Les filtres ou la pagination sont invalides.'
          : status === 404 ? 'Le capteur ou les mesures ne sont plus disponibles.'
          : status === 401 || status === 403 ? 'L’accès aux mesures a été refusé.'
          : 'Les mesures ne peuvent pas être chargées. Vous pouvez réessayer.' }); return EMPTY;
    }));
  }
  private resolveSensor(id: number | undefined): Observable<SensorRead | null> {
    if (id === undefined) return of(null);
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez un capteur valide.'));
    return this.sensorsApi.getById(id).pipe(tap(item => {
      if (item.id !== id || !positive(item.equipment_id)) throw new ScopeError('La référence capteur reçue est incohérente.');
    }));
  }
  private resolveEquipment(id: number | undefined): Observable<EquipmentRead | null> {
    if (id === undefined) return of(null);
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez un équipement valide.'));
    return this.references.getEquipmentById(id).pipe(tap(item => {
      if (item.id !== id || !positive(item.site_id)) throw new ScopeError('La référence équipement reçue est incohérente.');
    }));
  }
  private resolveSite(id: number | undefined): Observable<SiteRead | null> {
    if (id === undefined) return of(null);
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez un site valide.'));
    return this.references.getSiteById(id).pipe(tap(item => {
      if (item.id !== id || !positive(item.company_id)) throw new ScopeError('La référence site reçue est incohérente.');
    }));
  }
  private resolveCompany(id: number | undefined): Observable<CompanyRead | null> {
    if (id === undefined) return of(null);
    if (!positive(id)) return throwError(() => new ScopeError('Sélectionnez une entreprise valide.'));
    return this.references.getCompanyById(id).pipe(tap(item => {
      if (item.id !== id) throw new ScopeError('La référence entreprise reçue est incohérente.');
    }));
  }
}
