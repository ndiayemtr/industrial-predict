import { DestroyRef, Injectable, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { EMPTY, Observable, Subject, catchError, forkJoin, from, map, mergeMap, of, shareReplay, switchMap, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../core/api/reference-data-api.service';
import { CompanyRead, EquipmentRead, SiteRead } from '../../core/models/reference-data.model';
import { businessReferenceLabel } from '../../shared/utils/business-reference-label';
import { DashboardFilters } from './models/dashboard-filters.model';

export interface DashboardReferenceCatalog {
  companies: readonly CompanyRead[];
  sites: readonly SiteRead[];
  equipments: readonly EquipmentRead[];
}
type ReferenceKind = 'company' | 'site' | 'equipment';
interface ReferenceLabel { readonly id: number | null; readonly label: string }
type Labels = Readonly<Record<ReferenceKind, ReferenceLabel>>;
const unavailable = 'Référence indisponible';
const pending = 'Chargement de la référence...';

/** Page-local labels for the applied scope, independent of editable controls. */
@Injectable()
export class DashboardReferences {
  private readonly api = inject(ReferenceDataApiService);
  private readonly requests = new Subject<Record<ReferenceKind, Observable<ReferenceLabel>>>();
  private readonly labels = signal<Labels | null>(null);
  private readonly readingRequests = new Subject<readonly number[] | null>();
  private readonly equipmentCache = new Map<number, Observable<ReferenceLabel>>();
  private applied: Readonly<DashboardFilters> | null = null;
  private readonly currentEquipmentLabels = signal<Readonly<Record<number, string>>>({});
  readonly equipmentLabels = this.currentEquipmentLabels.asReadonly();

  constructor() {
    this.requests.pipe(switchMap(request => forkJoin(request)),
      takeUntilDestroyed(inject(DestroyRef))).subscribe(labels => this.labels.set(Object.freeze(labels)));
    this.readingRequests.pipe(switchMap(ids => ids === null ? EMPTY : from([...new Set(ids)]).pipe(
      mergeMap(id => this.equipmentReference(id), 4)
    )), takeUntilDestroyed(inject(DestroyRef))).subscribe();
  }

  capture(filters: Readonly<DashboardFilters>, catalog: DashboardReferenceCatalog): void {
    this.readingRequests.next(null);
    this.equipmentCache.clear();
    this.currentEquipmentLabels.set({});
    this.applied = filters;
    const companyId = filters.company_id;
    const siteId = filters.site_id ?? null;
    const equipmentId = filters.equipment_id ?? null;
    const company = catalog.companies.find(item => item.id === companyId);
    const site = catalog.sites.find(item => item.id === siteId && item.company_id === companyId);
    const equipment = catalog.equipments.find(item => item.id === equipmentId && item.site_id === siteId);
    const equipmentLabels: Record<number, string> = {};
    for (const item of catalog.equipments) {
      if (item.site_id === siteId || (siteId === null
        && catalog.sites.some(parent => parent.id === item.site_id && parent.company_id === companyId))) {
        const reference = { id: item.id, label: businessReferenceLabel(item) };
        this.equipmentCache.set(item.id, of(reference));
        equipmentLabels[item.id] = reference.label;
      }
    }
    this.currentEquipmentLabels.set(Object.freeze(equipmentLabels));
    // Copy labels immediately: later catalog changes must not rename applied results.
    const initial = {
      company: { id: companyId, label: company ? businessReferenceLabel(company) : pending },
      site: { id: siteId, label: siteId === null ? 'Tous les sites' : site ? businessReferenceLabel(site) : pending },
      equipment: { id: equipmentId, label: equipmentId === null ? 'Tous les équipements' : equipment ? businessReferenceLabel(equipment) : pending }
    };
    this.labels.set(Object.freeze(initial));
    this.requests.next({
      company: company ? of(initial.company) : this.resolve(companyId, this.api.getCompanyById(companyId), item => item.id === companyId),
      site: siteId === null || site ? of(initial.site)
        : this.resolve(siteId, this.api.getSiteById(siteId), item => item.id === siteId && item.company_id === companyId),
      equipment: equipmentId === null || equipment ? of(initial.equipment)
        : this.equipmentReference(equipmentId)
    });
  }

  loadReadings(filters: Readonly<DashboardFilters>, ids: readonly number[]): void {
    if (filters === this.applied) this.readingRequests.next(ids);
  }

  label(kind: ReferenceKind, id: number | null): string {
    const reference = this.labels()?.[kind];
    return reference?.id === id ? reference.label : unavailable;
  }

  private resolve<T extends CompanyRead>(id: number, source: Observable<T>, matches: (item: T) => boolean): Observable<ReferenceLabel> {
    return source.pipe(map(item => ({ id, label: matches(item) ? businessReferenceLabel(item) : unavailable })),
      catchError(() => of({ id, label: unavailable })));
  }

  private equipmentReference(id: number): Observable<ReferenceLabel> {
    const cached = this.equipmentCache.get(id);
    if (cached) return cached;
    if (!Number.isSafeInteger(id) || id <= 0) return of({ id, label: unavailable });
    const siteId = this.applied?.site_id;
    this.currentEquipmentLabels.update(labels => ({ ...labels, [id]: pending }));
    const source = this.resolve(id, this.api.getEquipmentById(id), item => item.id === id && (siteId == null || item.site_id === siteId)).pipe(
      tap(reference => this.currentEquipmentLabels.update(labels => ({ ...labels, [id]: reference.label }))),
      shareReplay({ bufferSize: 1, refCount: true })
    );
    this.equipmentCache.set(id, source);
    return source;
  }
}
