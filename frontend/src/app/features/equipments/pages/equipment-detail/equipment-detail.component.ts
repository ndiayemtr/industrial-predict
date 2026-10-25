import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Observable, Subject, catchError, distinctUntilChanged, map, of, startWith, switchMap, throwError } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { CompanyRead, EquipmentRead, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { formatAdministrativeDateTime } from '../../../../shared/utils/datetime-display';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { EquipmentsApiService } from '../../data-access/equipments-api.service';
import { equipmentCriticalityLabels, equipmentStatusLabels } from '../../models/equipment-labels';
import { EquipmentsQuery } from '../../models/equipments-state.model';
import { readPredictionNavigationContext } from '../../../predictions/utils/prediction-navigation';

type ReadError = { status: 'error'; title: string; message: string; retryable: boolean };
type ReadState<T> = { status: 'loading' } | { status: 'success'; data: T } | ReadError;
type CompanyState = ReadState<CompanyRead> | { status: 'waiting' };
type DetailState = { status: 'loading' } | ReadError
  | { status: 'success'; data: EquipmentRead; site: ReadState<SiteRead>; company: CompanyState };
type Scope = 'equipment' | 'site' | 'company';
class ReferenceError extends Error {}
const positive = (raw: string | null, fallback?: number, maximum = Number.MAX_SAFE_INTEGER): number | undefined =>
  raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) >= 1 && Number(raw) <= maximum ? Number(raw) : fallback;
const validId = (id: number): boolean => Number.isSafeInteger(id) && id > 0;

@Component({
  selector: 'app-equipment-detail', standalone: true,
  imports: [RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './equipment-detail.component.html', styleUrl: './equipment-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class EquipmentDetailComponent {
  private readonly createdEquipmentId = inject(Router).currentNavigation()?.extras.state?.['createdEquipmentId'];
  private readonly updatedEquipmentId = inject(Router).currentNavigation()?.extras.state?.['updatedEquipmentId'];
  readonly updateConfirmed = toSignal(inject(ActivatedRoute).paramMap.pipe(map(params => this.updatedEquipmentId != null
    && params.get('equipmentId') === String(this.updatedEquipmentId))), { requireSync: true });
  readonly creationConfirmed = toSignal(inject(ActivatedRoute).paramMap.pipe(map(params => this.createdEquipmentId != null
    && params.get('equipmentId') === String(this.createdEquipmentId))), { requireSync: true });
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly detailId = toSignal(this.route.paramMap.pipe(map(params => positive(params.get('equipmentId')))), { requireSync: true });
  private readonly api = inject(EquipmentsApiService);
  private readonly references = inject(ReferenceDataApiService);
  private readonly refresh = new Subject<void>();
  private readonly siteRefresh = new Subject<void>();
  private readonly companyRefresh = new Subject<void>();
  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });
  readonly formatDateTime = formatAdministrativeDateTime;
  readonly referenceLabel = businessReferenceLabel;
  readonly statusLabels: Readonly<Partial<Record<string, string>>> = equipmentStatusLabels();
  readonly criticalityLabels: Readonly<Partial<Record<string, string>>> = equipmentCriticalityLabels();
  readonly state = toSignal(this.route.paramMap.pipe(
    map(params => params.get('equipmentId')), distinctUntilChanged(),
    switchMap(raw => {
      const id = positive(raw);
      if (id === undefined) return of<DetailState>({ status: 'error', title: 'Identifiant invalide',
        message: 'L’identifiant de l’équipement doit être un entier positif valide. Revenez à la liste.', retryable: false });
      return this.refresh.pipe(startWith(undefined), switchMap(() => this.api.getById(id).pipe(
        switchMap(data => data.id === id ? this.loadSite(data)
          : throwError(() => new ReferenceError('La réponse équipement ne correspond pas à la fiche demandée.'))),
        catchError(error => of<DetailState>(this.readError(error, 'equipment'))),
        startWith<DetailState>({ status: 'loading' })
      )));
    })
  ), { initialValue: { status: 'loading' } as DetailState });

  // Return context is independent of the real parent chain, even after a retry.
  readonly listQuery = computed<EquipmentsQuery>(() => {
    const params = this.params(), search = params.get('search')?.trim() ?? '';
    return { company_id: positive(params.get('company_id')), site_id: positive(params.get('site_id')),
      page: positive(params.get('page'), 1)!, page_size: positive(params.get('page_size'), 20, 100)!,
      search: search && search.length <= 100 ? search : undefined,
      status: (Object.keys(this.statusLabels) as EquipmentRead['status'][]).find(value => value === params.get('status')),
      criticality: (Object.keys(this.criticalityLabels) as EquipmentRead['criticality'][]).find(value => value === params.get('criticality')) };
  });
  private readonly industrialQuery = computed(() => {
    const current = this.state();
    if (current.status !== 'success' || current.site.status !== 'success' || current.company.status !== 'success') return null;
    const equipment = current.data, site = current.site.data, company = current.company.data;
    if (![equipment.id, site.id, company.id].every(validId) || equipment.site_id !== site.id || site.company_id !== company.id) return null;
    return { company_id: company.id, site_id: site.id, equipment_id: equipment.id, page: 1, page_size: 20 };
  });
  readonly sensorsQuery = this.industrialQuery;
  readonly maintenanceQuery = this.industrialQuery;
  readonly predictionsReturn = computed(() => {
    const context = readPredictionNavigationContext(this.params(), this.detailId());
    return context ? this.router.createUrlTree(['/predictions'], { queryParams: context.query }) : null;
  });
  readonly predictionsQuery = computed(() => this.predictionsReturn() ? null : this.industrialQuery());
  readonly differentContext = computed(() => {
    const state = this.state(), query = this.listQuery();
    return state.status === 'success' && ((query.site_id !== undefined && query.site_id !== state.data.site_id)
      || (query.company_id !== undefined && state.site.status === 'success' && query.company_id !== state.site.data.company_id));
  });

  retry(): void { const state = this.state(); if (state.status === 'error' && state.retryable) this.refresh.next(); }
  retrySite(): void { const state = this.state(); if (state.status === 'success' && state.site.status === 'error' && state.site.retryable) this.siteRefresh.next(); }
  retryCompany(): void { const state = this.state(); if (state.status === 'success' && state.company.status === 'error' && state.company.retryable) this.companyRefresh.next(); }
  display(value: string | null | undefined): string { return value?.trim() ? value : 'Non renseigné'; }
  siteQuery(site: SiteRead): { company_id?: number } { return validId(site.company_id) ? { company_id: site.company_id } : {}; }

  private loadSite(data: EquipmentRead): Observable<DetailState> {
    return this.siteRefresh.pipe(startWith(undefined), switchMap(() => {
      const read = validId(data.site_id) ? this.references.getSiteById(data.site_id)
        : throwError(() => new ReferenceError('La référence du site de cet équipement est invalide.'));
      return read.pipe(switchMap(site => site.id === data.site_id ? this.loadCompany(data, site)
        : throwError(() => new ReferenceError('La référence site reçue ne correspond pas au rattachement de l’équipement.'))),
      catchError(error => of<DetailState>({ status: 'success', data, site: this.readError(error, 'site'), company: { status: 'waiting' } })),
      startWith<DetailState>({ status: 'success', data, site: { status: 'loading' }, company: { status: 'waiting' } }));
    }));
  }
  private loadCompany(data: EquipmentRead, site: SiteRead): Observable<DetailState> {
    return this.companyRefresh.pipe(startWith(undefined), switchMap(() => {
      const read = validId(site.company_id) ? this.references.getCompanyById(site.company_id)
        : throwError(() => new ReferenceError('La référence entreprise de ce site est invalide.'));
      return read.pipe(map((company): DetailState => {
        if (company.id !== site.company_id) throw new ReferenceError('La référence entreprise reçue ne correspond pas au site réel.');
        return { status: 'success', data, site: { status: 'success', data: site }, company: { status: 'success', data: company } };
      }), catchError(error => of<DetailState>({ status: 'success', data, site: { status: 'success', data: site }, company: this.readError(error, 'company') })),
      startWith<DetailState>({ status: 'success', data, site: { status: 'success', data: site }, company: { status: 'loading' } }));
    }));
  }
  private readError(error: unknown, scope: Scope): ReadError {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    return { status: 'error', retryable: status === 0 || status >= 500,
      title: scope === 'site' ? 'Site industriel indisponible' : scope === 'company' ? 'Entreprise indisponible'
        : status === 404 ? 'Équipement introuvable (404)' : 'Chargement impossible',
      message: error instanceof ReferenceError ? error.message
        : status === 404 ? scope === 'equipment' ? 'Cet équipement n’existe pas ou n’est plus disponible. Revenez à la liste.'
          : scope === 'site' ? 'Le site réel de cet équipement n’est plus disponible.' : 'L’entreprise réelle du site n’est plus disponible.'
        : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
        : status === 400 || status === 422 ? 'La référence demandée n’est pas acceptée par le serveur.'
        : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
        : scope === 'equipment' ? 'Les informations de l’équipement ne peuvent pas être chargées.'
          : scope === 'site' ? 'Le nom et le code du site réel ne peuvent pas être chargés.' : 'Le nom et le code de l’entreprise réelle ne peuvent pas être chargés.' };
  }
}
