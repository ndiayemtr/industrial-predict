import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Observable, Subject, catchError, distinctUntilChanged, map, of, startWith, switchMap, throwError } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { CompanyRead, EquipmentRead, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { formatAdministrativeDateTime } from '../../../../shared/utils/datetime-display';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { SensorsApiService } from '../../data-access/sensors-api.service';
import { SensorRead } from '../../models/sensor.model';
import { SensorsQuery } from '../../models/sensors-state.model';

type ReadError = { status: 'error'; title: string; message: string; retryable: boolean };
type ReadState<T> = { status: 'loading' } | { status: 'success'; data: T } | ReadError;
type ParentState<T> = ReadState<T> | { status: 'waiting' };
type DetailState = { status: 'loading' } | ReadError
  | { status: 'success'; data: SensorRead; equipment: ReadState<EquipmentRead>; site: ParentState<SiteRead>; company: ParentState<CompanyRead> };
type Scope = 'sensor' | 'equipment' | 'site' | 'company';
class ReferenceError extends Error {}
const positive = (raw: string | null, fallback?: number, maximum = Number.MAX_SAFE_INTEGER): number | undefined =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) >= 1 && Number(raw) <= maximum ? Number(raw) : fallback;
const validId = (id: number): boolean => Number.isSafeInteger(id) && id > 0;

@Component({
  selector: 'app-sensor-detail', standalone: true,
  imports: [RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './sensor-detail.component.html', styleUrl: './sensor-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SensorDetailComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(SensorsApiService);
  private readonly references = inject(ReferenceDataApiService);
  private readonly refresh = new Subject<void>();
  private readonly equipmentRefresh = new Subject<void>();
  private readonly siteRefresh = new Subject<void>();
  private readonly companyRefresh = new Subject<void>();
  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });
  readonly formatDateTime = formatAdministrativeDateTime;
  readonly referenceLabel = businessReferenceLabel;
  readonly statusLabels: Readonly<Partial<Record<string, string>>> = { active: 'Actif', inactive: 'Inactif' };
  readonly state = toSignal(this.route.paramMap.pipe(
    map(params => params.get('sensorId')), distinctUntilChanged(),
    switchMap(raw => {
      const id = positive(raw);
      if (id === undefined) return of<DetailState>({ status: 'error', title: 'Identifiant invalide',
        message: 'L’identifiant du capteur doit être un entier positif valide. Revenez à la liste.', retryable: false });
      return this.refresh.pipe(startWith(undefined), switchMap(() => this.api.getById(id).pipe(
        switchMap(data => data.id === id ? this.loadEquipment(data)
          : throwError(() => new ReferenceError('La réponse capteur ne correspond pas à la fiche demandée.'))),
        catchError(error => of<DetailState>(this.readError(error, 'sensor'))),
        startWith<DetailState>({ status: 'loading' })
      )));
    })
  ), { initialValue: { status: 'loading' } as DetailState });

  // Return context is independent of the real parent chain, even after a retry.
  readonly listQuery = computed<SensorsQuery>(() => {
    const params = this.params(), search = params.get('search')?.trim() ?? '';
    return { company_id: positive(params.get('company_id')), site_id: positive(params.get('site_id')), equipment_id: positive(params.get('equipment_id')),
      page: positive(params.get('page'), 1)!, page_size: positive(params.get('page_size'), 20, 100)!,
      search: search && search.length <= 100 ? search : undefined,
      status: (Object.keys(this.statusLabels) as SensorRead['status'][]).find(value => value === params.get('status')) };
  });
  readonly differentContext = computed(() => {
    const state = this.state(), query = this.listQuery();
    return state.status === 'success' && ((query.equipment_id !== undefined && query.equipment_id !== state.data.equipment_id)
      || (query.site_id !== undefined && state.equipment.status === 'success' && query.site_id !== state.equipment.data.site_id)
      || (query.company_id !== undefined && state.site.status === 'success' && query.company_id !== state.site.data.company_id));
  });

  retry(): void { const state = this.state(); if (state.status === 'error' && state.retryable) this.refresh.next(); }
  retryEquipment(): void { const state = this.state(); if (state.status === 'success' && state.equipment.status === 'error' && state.equipment.retryable) this.equipmentRefresh.next(); }
  retrySite(): void { const state = this.state(); if (state.status === 'success' && state.site.status === 'error' && state.site.retryable) this.siteRefresh.next(); }
  retryCompany(): void { const state = this.state(); if (state.status === 'success' && state.company.status === 'error' && state.company.retryable) this.companyRefresh.next(); }
  display(value: string | null | undefined): string { return value?.trim() ? value : 'Non renseigné'; }
  equipmentQuery(): { site_id?: number; company_id?: number } {
    const state = this.state();
    if (state.status !== 'success' || state.equipment.status !== 'success') return {};
    return { site_id: validId(state.equipment.data.site_id) ? state.equipment.data.site_id : undefined,
      company_id: state.site.status === 'success' && validId(state.site.data.company_id) ? state.site.data.company_id : undefined };
  }

  private loadEquipment(data: SensorRead): Observable<DetailState> {
    return this.equipmentRefresh.pipe(startWith(undefined), switchMap(() => {
      const read = validId(data.equipment_id) ? this.references.getEquipmentById(data.equipment_id)
        : throwError(() => new ReferenceError('La référence équipement de ce capteur est invalide.'));
      return read.pipe(switchMap(equipment => equipment.id === data.equipment_id ? this.loadSite(data, equipment)
        : throwError(() => new ReferenceError('La référence équipement reçue ne correspond pas au rattachement du capteur.'))),
      catchError(error => of<DetailState>({ status: 'success', data, equipment: this.readError(error, 'equipment'), site: { status: 'waiting' }, company: { status: 'waiting' } })),
      startWith<DetailState>({ status: 'success', data, equipment: { status: 'loading' }, site: { status: 'waiting' }, company: { status: 'waiting' } }));
    }));
  }
  private loadSite(data: SensorRead, equipment: EquipmentRead): Observable<DetailState> {
    return this.siteRefresh.pipe(startWith(undefined), switchMap(() => {
      const read = validId(equipment.site_id) ? this.references.getSiteById(equipment.site_id)
        : throwError(() => new ReferenceError('La référence du site de cet équipement est invalide.'));
      return read.pipe(switchMap(site => site.id === equipment.site_id ? this.loadCompany(data, equipment, site)
        : throwError(() => new ReferenceError('La référence site reçue ne correspond pas au rattachement de l’équipement.'))),
      catchError(error => of<DetailState>({ status: 'success', data, equipment: { status: 'success', data: equipment }, site: this.readError(error, 'site'), company: { status: 'waiting' } })),
      startWith<DetailState>({ status: 'success', data, equipment: { status: 'success', data: equipment }, site: { status: 'loading' }, company: { status: 'waiting' } }));
    }));
  }
  private loadCompany(data: SensorRead, equipment: EquipmentRead, site: SiteRead): Observable<DetailState> {
    return this.companyRefresh.pipe(startWith(undefined), switchMap(() => {
      const read = validId(site.company_id) ? this.references.getCompanyById(site.company_id)
        : throwError(() => new ReferenceError('La référence entreprise de ce site est invalide.'));
      return read.pipe(map((company): DetailState => {
        if (company.id !== site.company_id) throw new ReferenceError('La référence entreprise reçue ne correspond pas au site réel.');
        return { status: 'success', data, equipment: { status: 'success', data: equipment }, site: { status: 'success', data: site }, company: { status: 'success', data: company } };
      }), catchError(error => of<DetailState>({ status: 'success', data, equipment: { status: 'success', data: equipment }, site: { status: 'success', data: site }, company: this.readError(error, 'company') })),
      startWith<DetailState>({ status: 'success', data, equipment: { status: 'success', data: equipment }, site: { status: 'success', data: site }, company: { status: 'loading' } }));
    }));
  }
  private readError(error: unknown, scope: Scope): ReadError {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    return { status: 'error', retryable: status === 0 || status >= 500,
      title: scope === 'site' ? 'Site industriel indisponible' : scope === 'company' ? 'Entreprise indisponible'
        : scope === 'equipment' ? 'Équipement indisponible' : status === 404 ? 'Capteur introuvable (404)' : 'Chargement impossible',
      message: error instanceof ReferenceError ? error.message
        : status === 404 ? scope === 'sensor' ? 'Ce capteur n’existe pas ou n’est plus disponible. Revenez à la liste.'
          : scope === 'equipment' ? 'L’équipement réel de ce capteur n’est plus disponible.' : scope === 'site' ? 'Le site réel de cet équipement n’est plus disponible.' : 'L’entreprise réelle du site n’est plus disponible.'
        : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
        : status === 400 || status === 422 ? 'La référence demandée n’est pas acceptée par le serveur.'
        : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
        : scope === 'sensor' ? 'Les informations du capteur ne peuvent pas être chargées.'
          : scope === 'equipment' ? 'Le nom et le code de l’équipement réel ne peuvent pas être chargés.'
          : scope === 'site' ? 'Le nom et le code du site réel ne peuvent pas être chargés.' : 'Le nom et le code de l’entreprise réelle ne peuvent pas être chargés.' };
  }
}
