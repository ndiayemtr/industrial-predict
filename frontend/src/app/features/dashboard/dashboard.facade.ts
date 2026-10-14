import { HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, Injectable, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Subject, catchError, switchMap, tap } from 'rxjs';
import { DashboardApiService } from './data-access/dashboard-api.service';
import { DashboardFilters } from './models/dashboard-filters.model';
import { DashboardError, DashboardState } from './models/dashboard-state.model';

@Injectable()
export class DashboardFacade {
  private readonly api = inject(DashboardApiService);
  private readonly destroyRef = inject(DestroyRef);
  private readonly requests = new Subject<Readonly<DashboardFilters>>();
  private readonly currentState = signal<DashboardState>({ status: 'idle' });
  private readonly applied = signal<Readonly<DashboardFilters> | null>(null);
  readonly state = this.currentState.asReadonly();
  readonly appliedFilters = this.applied.asReadonly();
  readonly canRefresh = computed(() => {
    const state = this.state();
    return this.applied() !== null && (state.status === 'success' || state.status === 'empty'
      || (state.status === 'error' && state.error.retryable));
  });

  constructor() {
    this.requests.pipe(switchMap(filters => {
      this.currentState.set({ status: 'loading', filters });
      return this.api.getDashboard(filters).pipe(tap(data => {
        const empty = data.assets.sites === 0 && data.assets.equipments === 0 && data.assets.sensors === 0;
        this.currentState.set({ status: empty ? 'empty' : 'success', filters, data });
      }), catchError((error: unknown) => {
        this.currentState.set({ status: 'error', filters, error: this.describeError(error) });
        return EMPTY;
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }

  applyFilters(filters: DashboardFilters): void {
    if (!this.validFilters(filters)) return;
    const snapshot = Object.freeze({ ...filters });
    this.applied.set(snapshot);
    this.requests.next(snapshot);
  }

  refresh(): void {
    const filters = this.applied();
    if (filters && this.canRefresh()) this.requests.next(filters);
  }

  retry(): void {
    const state = this.state();
    if (state.status === 'error' && state.error.retryable) this.refresh();
  }

  private validFilters(filters: DashboardFilters): boolean {
    const positiveId = (id: number) => Number.isSafeInteger(id) && id > 0;
    const zoned = (value: string) => /(Z|[+-]\d{2}:\d{2})$/i.test(value);
    const start = Date.parse(filters.start_time);
    const end = Date.parse(filters.end_time);
    return positiveId(filters.company_id)
      && (filters.site_id == null || positiveId(filters.site_id))
      && (filters.equipment_id == null || positiveId(filters.equipment_id))
      && zoned(filters.start_time) && zoned(filters.end_time)
      && Number.isFinite(start) && Number.isFinite(end) && start < end && end <= Date.now();
  }

  private describeError(error: unknown): DashboardError {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    if (status === 400 || status === 422) return { kind: 'validation', title: 'Filtres à vérifier',
      message: 'Vérifiez le périmètre et les dates UTC, puis appliquez les filtres corrigés.', retryable: false };
    if (status === 404) return { kind: 'not-found', title: 'Périmètre introuvable',
      message: 'Une entreprise, un site ou un équipement sélectionné n’est plus disponible. Vérifiez votre sélection.', retryable: false };
    if (status === 0) return { kind: 'network', title: 'Connexion indisponible',
      message: 'Impossible de joindre le serveur. Vous pouvez réessayer avec les filtres appliqués.', retryable: true };
    if (status >= 500) return { kind: 'server', title: 'Dashboard indisponible',
      message: 'Le serveur n’a pas pu produire le Dashboard. Vous pouvez réessayer.', retryable: true };
    return { kind: 'unexpected', title: 'Chargement impossible',
      message: 'Une erreur inattendue empêche le chargement du Dashboard.', retryable: false };
  }
}
