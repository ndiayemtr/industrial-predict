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
import { MaintenanceApiService } from '../../data-access/maintenance-api.service';
import { MaintenanceRead } from '../../models/maintenance.model';
import { formatMeasurementUtc } from '../../../measurements/utils/measurement-time';

type ReadError = { status: 'error'; title: string; message: string; retryable: boolean };
type ParentState<T> = { status: 'waiting' | 'loading' } | { status: 'success'; data: T } | ReadError;
interface References {
  equipment: ParentState<EquipmentRead>;
  site: ParentState<SiteRead>;
  company: ParentState<CompanyRead>;
}
type DetailState = { status: 'loading' } | ReadError | { status: 'success'; data: MaintenanceRead; references: References };
type Scope = keyof References;
class ReferenceLinkError extends Error {}
const validId = (id: number): boolean => Number.isSafeInteger(id) && id > 0;
const parseId = (raw: string | null): number | undefined => raw !== null && /^\d+$/.test(raw) && validId(Number(raw)) ? Number(raw) : undefined;
const waiting = (): References => ({ equipment: { status: 'waiting' }, site: { status: 'waiting' }, company: { status: 'waiting' } });

@Component({
  selector: 'app-maintenance-detail', standalone: true,
  imports: [RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './maintenance-detail.component.html', styleUrl: './maintenance-detail.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MaintenanceDetailComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(MaintenanceApiService);
  private readonly referencesApi = inject(ReferenceDataApiService);
  private readonly refresh = new Subject<void>();
  private readonly referencesRefresh = new Subject<void>();
  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });
  readonly fragment = toSignal(this.route.fragment, { requireSync: true });
  readonly typeLabels = { preventive: 'Préventive', corrective: 'Corrective', predictive: 'Prédictive' } as const;
  readonly statusLabels = { planned: 'Planifiée', in_progress: 'En cours', completed: 'Terminée', cancelled: 'Annulée' } as const;
  readonly priorityLabels = { low: 'Basse', medium: 'Moyenne', high: 'Haute', critical: 'Critique' } as const;
  readonly referenceLabel = businessReferenceLabel;
  readonly diagnosticFields = [
    { key: 'description', label: 'Description' }, { key: 'failure_code', label: 'Code de panne' },
    { key: 'root_cause', label: 'Cause racine' }, { key: 'action_taken', label: 'Action réalisée' }
  ] as const;
  readonly businessDates = [
    { key: 'planned_at', label: 'Date planifiée' }, { key: 'started_at', label: 'Date de début' },
    { key: 'completed_at', label: 'Date de fin' }
  ] as const;
  readonly administrativeDates = [{ key: 'created_at', label: 'Date de création' }, { key: 'updated_at', label: 'Dernière modification' }] as const;
  readonly listQuery = computed<Params>(() => Object.fromEntries(this.params().keys
    .filter(key => ['company_id', 'site_id', 'equipment_id', 'maintenance_type', 'status', 'priority', 'search', 'start_time', 'end_time', 'page', 'page_size'].includes(key))
    .map(key => [key, this.params().getAll(key)])));
  readonly display = (value: string | number | null): string => value === null ? 'Non renseigné' : value === '' ? 'Texte vide' : String(value);
  readonly hasOffset = (raw: string): boolean => /(Z|[+-]\d{2}:\d{2})$/.test(raw);
  readonly formatTime = (raw: string): string => this.hasOffset(raw) ? formatMeasurementUtc(raw) : raw + ' (fuseau non fourni)';
  readonly state = toSignal(this.route.paramMap.pipe(map(params => params.get('maintenanceId')), distinctUntilChanged(), switchMap(raw => {
    const id = parseId(raw);
    if (id === undefined) return of<DetailState>({ status: 'error', title: 'Identifiant invalide',
      message: 'L’identifiant de l’intervention doit être un entier positif valide. Revenez à la liste.', retryable: false });
    return this.refresh.pipe(startWith(undefined), switchMap(() => this.api.getById(id).pipe(
      switchMap(data => this.loadReferences(data)),
      catchError(error => of<DetailState>(this.readError(error))),
      startWith<DetailState>({ status: 'loading' })
    )));
  })), { initialValue: { status: 'loading' } as DetailState });

  readonly differentContext = computed(() => {
    const current = this.state(); if (current.status !== 'success') return false;
    const refs = current.references;
    const actual = { equipment_id: current.data.equipment_id,
      site_id: refs.equipment.status === 'success' ? refs.equipment.data.site_id : undefined,
      company_id: refs.site.status === 'success' ? refs.site.data.company_id : undefined };
    return Object.entries(actual).some(([key, id]) => id !== undefined && this.params().has(key) && this.params().get(key) !== String(id));
  });
  readonly equipmentQuery = computed<Params>(() => {
    const current = this.state(); if (current.status !== 'success' || current.references.equipment.status !== 'success') return {};
    const refs = current.references, equipment = current.references.equipment.data;
    return { ...(validId(equipment.site_id) ? { site_id: equipment.site_id } : {}),
      ...(refs.site.status === 'success' && validId(refs.site.data.company_id) ? { company_id: refs.site.data.company_id } : {}), page: 1, page_size: 20 };
  });

  retry(): void { const current = this.state(); if (current.status === 'error' && current.retryable) this.refresh.next(); }
  retryReferences(): void {
    const current = this.state();
    if (current.status === 'success' && Object.values(current.references).some(ref => ref.status === 'error' && ref.retryable)) this.referencesRefresh.next();
  }
  private loadReferences(data: MaintenanceRead): Observable<DetailState> {
    return this.referencesRefresh.pipe(startWith(undefined), switchMap(() =>
      this.readReference(data, waiting(), 'equipment', data.equipment_id, () => this.referencesApi.getEquipmentById(data.equipment_id), (equipment, chain) =>
        this.readReference(data, chain, 'site', equipment.site_id, () => this.referencesApi.getSiteById(equipment.site_id), (site, chain) =>
          this.readReference(data, chain, 'company', site.company_id, () => this.referencesApi.getCompanyById(site.company_id), (_, chain) =>
            of<DetailState>({ status: 'success', data, references: chain }))))
    ));
  }
  private readReference<T extends { id: number }>(data: MaintenanceRead, chain: References, scope: Scope, id: number,
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
    const names: Record<Scope, string> = { equipment: 'Équipement', site: 'Site industriel', company: 'Entreprise' };
    return { status: 'error', retryable: status === 0 || status >= 500,
      title: scope ? `${names[scope]} indisponible` : status === 404 ? 'Intervention introuvable (404)' : error instanceof TypeError ? 'Réponse invalide' : status === 0 ? 'Connexion impossible' : 'Chargement impossible',
      message: error instanceof ReferenceLinkError ? error.message
        : error instanceof TypeError ? 'La réponse contient des données d’intervention invalides. Aucune valeur de remplacement n’est affichée.'
        : status === 404 ? scope ? 'Cette référence réelle n’existe pas ou n’est plus disponible. L’intervention reste affichée.' : 'Cette intervention n’existe pas ou n’est plus disponible. Revenez à la liste.'
        : status === 401 || status === 403 ? 'L’accès aux données demandées a été refusé.'
        : status === 400 || status === 422 ? 'La référence demandée n’est pas acceptée par le serveur.'
        : status === 0 ? 'Impossible de joindre le serveur. Vous pouvez réessayer.'
        : scope ? 'Le rattachement réel ne peut pas être chargé. L’intervention reste affichée.' : 'Les informations de l’intervention ne peuvent pas être chargées.' };
  }
}
