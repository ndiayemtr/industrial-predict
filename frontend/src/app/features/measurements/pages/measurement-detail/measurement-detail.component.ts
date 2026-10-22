import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Params, RouterLink } from '@angular/router';
import { Observable, Subject, catchError, defer, distinctUntilChanged, map, of, startWith, switchMap, tap, throwError } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { CompanyRead, EquipmentRead, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { SensorsApiService } from '../../../sensors/data-access/sensors-api.service';
import { SensorRead } from '../../../sensors/models/sensor.model';
import { MeasurementsApiService } from '../../data-access/measurements-api.service';
import { MeasurementRead } from '../../models/measurement.model';
import { formatMeasurementUtc } from '../../utils/measurement-time';
import { formatMeasurementValue, measurementQualityLabels } from '../../utils/measurement-display';

type ReadError = { status: 'error'; title: string; message: string; retryable: boolean };
type ParentState<T> = { status: 'waiting' | 'loading' } | { status: 'success'; data: T } | ReadError;
interface References {
  sensor: ParentState<SensorRead>;
  equipment: ParentState<EquipmentRead>;
  site: ParentState<SiteRead>;
  company: ParentState<CompanyRead>;
}
type DetailState = { status: 'loading' } | ReadError | { status: 'success'; data: MeasurementRead; references: References };
type Scope = keyof References;
class ReferenceLinkError extends Error {}
const validId = (id: number): boolean => Number.isSafeInteger(id) && id > 0;
const parseId = (raw: string | null): number | undefined => raw !== null && /^\d+$/.test(raw) && validId(Number(raw)) ? Number(raw) : undefined;
const waiting = (): References => ({ sensor: { status: 'waiting' }, equipment: { status: 'waiting' }, site: { status: 'waiting' }, company: { status: 'waiting' } });

@Component({
  selector: 'app-measurement-detail', standalone: true,
  imports: [RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './measurement-detail.component.html', styleUrl: './measurement-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MeasurementDetailComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(MeasurementsApiService);
  private readonly sensorsApi = inject(SensorsApiService);
  private readonly referencesApi = inject(ReferenceDataApiService);
  private readonly refresh = new Subject<void>();
  private readonly referencesRefresh = new Subject<void>();
  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });
  readonly fragment = toSignal(this.route.fragment, { requireSync: true });
  readonly qualityLabels = measurementQualityLabels();
  readonly formatTime = formatMeasurementUtc;
  readonly formatValue = formatMeasurementValue;
  readonly referenceLabel = businessReferenceLabel;
  // Navigation data only: preserve raw values, repeated params and offsets without using them for reads.
  readonly listQuery = computed<Params>(() => Object.fromEntries(this.params().keys.map(key => [key, this.params().getAll(key)])));
  readonly state = toSignal(this.route.paramMap.pipe(map(params => params.get('measurementId')), distinctUntilChanged(), switchMap(raw => {
    const id = parseId(raw);
    if (id === undefined) return of<DetailState>({ status: 'error', title: 'Identifiant invalide',
      message: 'L’identifiant de la mesure doit être un entier positif valide. Revenez à la liste.', retryable: false });
    return this.refresh.pipe(startWith(undefined), switchMap(() => this.api.getById(id).pipe(
      switchMap(data => this.loadReferences(data)),
      catchError(error => of<DetailState>(this.readError(error))),
      startWith<DetailState>({ status: 'loading' })
    )));
  })), { initialValue: { status: 'loading' } as DetailState });

  readonly differentContext = computed(() => {
    const current = this.state(); if (current.status !== 'success') return false;
    const refs = current.references;
    const actual = { sensor_id: current.data.sensor_id,
      equipment_id: refs.sensor.status === 'success' ? refs.sensor.data.equipment_id : undefined,
      site_id: refs.equipment.status === 'success' ? refs.equipment.data.site_id : undefined,
      company_id: refs.site.status === 'success' ? refs.site.data.company_id : undefined };
    return Object.entries(actual).some(([key, id]) => id !== undefined && this.params().has(key) && this.params().get(key) !== String(id));
  });
  readonly currentUnit = computed(() => {
    const current = this.state(); if (current.status !== 'success' || current.references.sensor.status !== 'success') return null;
    const unit = current.references.sensor.data.unit;
    return typeof unit === 'string' && unit.trim() ? unit : null;
  });
  readonly sensorQuery = computed<Params>(() => {
    const current = this.state(); if (current.status !== 'success') return {};
    const refs = current.references;
    if (refs.sensor.status !== 'success' || refs.equipment.status !== 'success' || refs.site.status !== 'success' || refs.company.status !== 'success') return {};
    const fallback: Params = { company_id: refs.company.data.id, site_id: refs.site.data.id, equipment_id: refs.equipment.data.id, page: 1, page_size: 20 };
    const params = this.params();
    const company = parseId(params.get('return_sensor_company_id')), site = parseId(params.get('return_sensor_site_id')), equipment = parseId(params.get('return_sensor_equipment_id'));
    const page = params.has('return_sensor_page') ? parseId(params.get('return_sensor_page')) : 1;
    const size = params.has('return_sensor_page_size') ? parseId(params.get('return_sensor_page_size')) : 20;
    const search = params.get('return_sensor_search'), status = params.get('return_sensor_status');
    if (!company || !site || !equipment || !page || !size || size > 100 || (search !== null && search.length > 100)
      || (status !== null && status !== 'active' && status !== 'inactive')) return fallback;
    return { company_id: company, site_id: site, equipment_id: equipment, page, page_size: size,
      ...(search !== null ? { search } : {}), ...(status !== null ? { status } : {}) };
  });

  retry(): void { const current = this.state(); if (current.status === 'error' && current.retryable) this.refresh.next(); }
  retryReferences(): void {
    const current = this.state();
    if (current.status === 'success' && Object.values(current.references).some(ref => ref.status === 'error' && ref.retryable)) this.referencesRefresh.next();
  }
  private loadReferences(data: MeasurementRead): Observable<DetailState> {
    return this.referencesRefresh.pipe(startWith(undefined), switchMap(() =>
      this.readReference(data, waiting(), 'sensor', data.sensor_id, () => this.sensorsApi.getById(data.sensor_id), (sensor, chain) =>
        this.readReference(data, chain, 'equipment', sensor.equipment_id, () => this.referencesApi.getEquipmentById(sensor.equipment_id), (equipment, chain) =>
          this.readReference(data, chain, 'site', equipment.site_id, () => this.referencesApi.getSiteById(equipment.site_id), (site, chain) =>
            this.readReference(data, chain, 'company', site.company_id, () => this.referencesApi.getCompanyById(site.company_id), (_, chain) =>
              of<DetailState>({ status: 'success', data, references: chain })))))
    ));
  }
  private readReference<T extends { id: number }>(data: MeasurementRead, chain: References, scope: Scope, id: number,
    fetch: () => Observable<T>, next: (item: T, chain: References) => Observable<DetailState>): Observable<DetailState> {
    const read = validId(id) ? defer(fetch).pipe(tap(item => {
      if (!item || item.id !== id) throw new ReferenceLinkError('La référence reçue ne correspond pas au rattachement réel.');
    })) : throwError(() => new ReferenceLinkError('Le rattachement contient un identifiant de référence invalide.'));
    return read.pipe(switchMap(item => next(item, { ...chain, [scope]: { status: 'success', data: item } })),
      catchError(error => of<DetailState>({ status: 'success', data, references: { ...chain, [scope]: this.readError(error, scope) } })),
      startWith<DetailState>({ status: 'success', data, references: { ...chain, [scope]: { status: 'loading' } } }));
  }
  private readError(error: unknown, scope?: Scope): ReadError {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    const names: Record<Scope, string> = { sensor: 'Capteur', equipment: 'Équipement', site: 'Site industriel', company: 'Entreprise' };
    return { status: 'error', retryable: status === 0 || status >= 500,
      title: scope ? `${names[scope]} indisponible` : status === 404 ? 'Mesure introuvable (404)' : 'Chargement impossible',
      message: error instanceof ReferenceLinkError ? error.message
        : error instanceof TypeError ? 'La réponse contient des données de mesure invalides. Aucune valeur de remplacement n’est affichée.'
        : status === 404 ? scope ? 'Cette référence réelle n’existe pas ou n’est plus disponible. La mesure reste affichée.' : 'Cette mesure n’existe pas ou n’est plus disponible. Revenez à la liste.'
        : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
        : status === 400 || status === 422 ? 'La référence demandée n’est pas acceptée par le serveur.'
        : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
        : scope ? 'Le rattachement réel ne peut pas être chargé. La mesure reste affichée.' : 'Les informations de la mesure ne peuvent pas être chargées.' };
  }
}
