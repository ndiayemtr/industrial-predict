import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, Injector, afterNextRender, computed, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormControl, FormGroup, ReactiveFormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { merge, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { CompanyRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { EmptyStateComponent } from '../../../../shared/components/empty-state/empty-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { restoreMeasurementBound } from '../../../measurements/utils/measurement-period-draft';
import { PredictionsQuery } from '../../models/predictions-state.model';
import { PredictionsListFacade } from '../../predictions-list.facade';
import { predictionPeriodDraft } from '../../utils/prediction-period-draft';
import { predictionQueryKeys, predictionTypes, readPredictionQuery } from '../../utils/prediction-query';
import { PredictionReferenceCatalog } from '../../utils/prediction-reference-catalog';

type ScopeKey = 'company_id' | 'site_id' | 'equipment_id';

@Component({
  selector: 'app-predictions-list', standalone: true,
  imports: [ReactiveFormsModule, PageHeaderComponent, LoadingStateComponent, EmptyStateComponent, ErrorStateComponent],
  providers: [PredictionsListFacade], changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './predictions-list.component.html', styleUrl: './predictions-list.component.scss'
})
export class PredictionsListComponent {
  readonly facade = inject(PredictionsListFacade);
  private readonly references = inject(ReferenceDataApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly destroy = inject(DestroyRef);
  private readonly element = inject<ElementRef<HTMLElement>>(ElementRef);
  private readonly injector = inject(Injector);
  readonly company = new FormControl<number | null>(null);
  readonly site = new FormControl<number | null>({ value: null, disabled: true });
  readonly equipment = new FormControl<number | null>({ value: null, disabled: true });
  readonly predictionType = new FormControl('', { nonNullable: true });
  readonly level = new FormControl('', { nonNullable: true });
  readonly alert = new FormControl('', { nonNullable: true });
  readonly size = new FormControl(20, { nonNullable: true });
  readonly start = this.boundForm();
  readonly end = this.boundForm();
  private startBaseline = restoreMeasurementBound();
  private endBaseline = restoreMeasurementBound();
  private filterBaseline = '';
  private filterUrlBaseline = '';
  private contextBaseline = '';
  readonly draft = signal(false);
  readonly fieldErrors = signal<Readonly<Record<string, string>>>({});
  readonly feedback = signal('');
  readonly urlNotice = signal('');
  readonly referenceLabel = businessReferenceLabel;
  readonly types = predictionTypes;
  readonly typeLabels = { anomaly: 'Anomalie', failure_risk: 'Risque de panne', health_score: 'Indice de santé', rul: 'Durée de vie utile restante' } as const;
  readonly companies = new PredictionReferenceCatalog(this.destroy, (_, page) => this.references.getCompanies({ page, page_size: 50 }));
  readonly sites = new PredictionReferenceCatalog(this.destroy, (id, page) => this.references.getSites(id!, { page, page_size: 50 }).pipe(tap(data => {
    if (!Array.isArray(data?.items) || data.items.some(item => !item || item.company_id !== id)) throw new TypeError('Catalogue de sites incohérent.');
  })));
  readonly equipments = new PredictionReferenceCatalog(this.destroy, (id, page) => this.references.getEquipments(id!, { page, page_size: 50 }).pipe(tap(data => {
    if (!Array.isArray(data?.items) || data.items.some(item => !item || item.site_id !== id)) throw new TypeError('Catalogue d’équipements incohérent.');
  })));
  readonly selectors = [
    { key: 'company_id' as const, name: 'Entreprise', plural: 'entreprises', control: this.company, catalog: this.companies },
    { key: 'site_id' as const, name: 'Site industriel', plural: 'sites', control: this.site, catalog: this.sites },
    { key: 'equipment_id' as const, name: 'Équipement industriel', plural: 'équipements', control: this.equipment, catalog: this.equipments }
  ];
  readonly bounds = [{ key: 'start', label: 'Début UTC (inclus)', form: this.start }, { key: 'end', label: 'Fin UTC (incluse)', form: this.end }];
  readonly busy = computed(() => this.facade.state().status === 'loading');
  readonly canFilter = computed(() => !!(this.facade.company() && this.facade.site() && this.facade.equipment()));
  readonly page = computed(() => this.facade.query()?.page ?? 1);
  readonly pageSize = computed(() => this.facade.query()?.page_size ?? 20);
  readonly sizes = computed(() => [...new Set([20, 50, 100, this.pageSize()])].sort((a, b) => a - b));
  readonly filtered = computed(() => {
    const query = this.facade.query();
    return !!query && [query.prediction_type, query.level, query.is_alert, query.start_time, query.end_time].some(value => value !== undefined);
  });
  readonly canNext = computed(() => { const state = this.facade.state(); return state.status === 'success' && this.page() < state.data.pages; });

  constructor() {
    this.companies.load(null);
    for (const selector of this.selectors) selector.control.valueChanges.pipe(takeUntilDestroyed(this.destroy)).subscribe(id => this.changeScope(selector.key, id));
    merge(this.start.valueChanges, this.end.valueChanges, this.predictionType.valueChanges, this.level.valueChanges, this.alert.valueChanges)
      .pipe(takeUntilDestroyed(this.destroy)).subscribe(() => {
        this.draft.set(this.filterSnapshot() !== this.filterBaseline);
        if (this.feedback()) this.validateDraft();
      });
    this.size.valueChanges.pipe(takeUntilDestroyed(this.destroy)).subscribe(page_size => {
      const query = this.facade.query();
      if (query) void this.navigate({ ...query, page_size, page: 1 });
    });
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroy)).subscribe(params => {
      const context = ['company_id', 'site_id', 'equipment_id'].map(key => params.getAll(key).join(',')).join('/');
      const contextChanged = context !== this.contextBaseline;
      const filterUrl = ['prediction_type', 'level', 'is_alert', 'start_time', 'end_time'].map(key => params.getAll(key)).map(value => JSON.stringify(value)).join('/');
      const timeChanged = params.get('start_time') !== (this.startBaseline.raw ?? null) || params.get('end_time') !== (this.endBaseline.raw ?? null);
      const query = (() => { try { return readPredictionQuery(params); } catch (error) {
        this.urlNotice.set(error instanceof Error ? error.message : 'URL invalide.'); return null;
      } })();
      if (contextChanged || timeChanged || filterUrl !== this.filterUrlBaseline || !this.draft()) this.restoreFilters(params.get('start_time') ?? undefined, params.get('end_time') ?? undefined,
        params.get('prediction_type') ?? '', params.get('level') ?? '', params.get('is_alert') ?? '');
      this.filterUrlBaseline = filterUrl;
      this.contextBaseline = context;
      if (!query) {
        this.facade.block(this.urlNotice()); this.site.disable({ emitEvent: false }); this.equipment.disable({ emitEvent: false });
        this.company.setValue(null, { emitEvent: false }); this.site.setValue(null, { emitEvent: false }); this.equipment.setValue(null, { emitEvent: false });
        this.sites.clear(); this.equipments.clear();
        return;
      }
      this.urlNotice.set('');
      this.company.setValue(query.company_id ?? null, { emitEvent: false }); this.site.setValue(query.site_id ?? null, { emitEvent: false });
      this.equipment.setValue(query.equipment_id ?? null, { emitEvent: false }); this.size.setValue(query.page_size, { emitEvent: false });
      if (!this.same(this.facade.query(), query)) this.facade.load(query);
    });
    effect(() => {
      const company = this.facade.company(), site = this.facade.site();
      if (company) this.site.enable({ emitEvent: false }); else this.site.disable({ emitEvent: false });
      if (company && site) this.equipment.enable({ emitEvent: false }); else this.equipment.disable({ emitEvent: false });
      this.sites.ensure(company?.id); this.equipments.ensure(site?.id);
    });
  }

  options(key: ScopeKey, catalog: PredictionReferenceCatalog): CompanyRead[] {
    const selected = key === 'company_id' ? this.facade.company() : key === 'site_id' ? this.facade.site() : this.facade.equipment();
    return [...new Map([...catalog.state().items, ...(selected ? [selected] : [])].map(item => [item.id, item])).values()];
  }
  private changeScope(key: ScopeKey, id: number | null): void {
    const query: PredictionsQuery = { company_id: this.company.value ?? undefined, site_id: this.site.value ?? undefined,
      equipment_id: this.equipment.value ?? undefined, page: 1, page_size: this.size.value };
    query[key] = id ?? undefined;
    if (key === 'company_id') { query.site_id = undefined; this.site.setValue(null, { emitEvent: false }); this.sites.clear(); }
    if (key !== 'equipment_id') { query.equipment_id = undefined; this.equipment.setValue(null, { emitEvent: false }); this.equipments.clear(); }
    this.facade.load(query); // Cancel old results immediately, retaining only unchanged verified parents.
    this.restoreFilters();
    void this.navigate(query);
  }
  applyFilters(): void {
    const period = this.validateDraft();
    if (!period) {
      afterNextRender(() => this.element.nativeElement.querySelector<HTMLElement>('#predictions-feedback')?.focus(), { injector: this.injector });
      return;
    }
    let query = this.facade.query();
    if (!query) {
      // Repair filters without dropping or inventing the industrial URL scope.
      try { query = readPredictionQuery(this.router.parseUrl(this.router.url).queryParamMap); }
      catch { query = null; }
    }
    if (!query) {
      const params = this.route.snapshot.queryParamMap;
      void this.router.navigate([], { relativeTo: this.route, queryParams: {
        prediction_type: this.predictionType.value || null, level: this.level.value === '' ? null : this.level.value,
        is_alert: this.alert.value === '' ? null : this.alert.value, ...period, page: 1,
        start_time: period.start_time ?? null, end_time: period.end_time ?? null
      }, queryParamsHandling: 'merge', preserveFragment: true });
      // Duplicated or invalid scope stays blocked until explicitly corrected.
      if (['company_id', 'site_id', 'equipment_id'].some(key => params.getAll(key).length > 1)) this.feedback.set('Corrigez le contexte répété ou recommencez la sélection.');
      return;
    }
    void this.navigate({ ...query, ...period, prediction_type: predictionTypes.find(type => type === this.predictionType.value),
      level: this.level.value === '' ? undefined : this.level.value, is_alert: this.alert.value === '' ? undefined : this.alert.value === 'true', page: 1 });
  }
  private validateDraft() {
    const invalid = [...this.element.nativeElement.querySelectorAll<HTMLInputElement>('.period-bound input')]
      .filter(input => !input.validity.valid).map(input => input.id.slice('predictions-'.length));
    const result = predictionPeriodDraft(this.start.getRawValue(), this.startBaseline, this.end.getRawValue(), this.endBaseline, invalid);
    const errors = { ...result.errors };
    if (this.predictionType.value !== '' && !predictionTypes.some(value => value === this.predictionType.value)) errors['type'] = 'Choisissez un type disponible.';
    if (Array.from(this.level.value).length > 50) errors['level'] = 'Utilisez au plus 50 caractères bruts, sans supprimer les espaces.';
    if (!['', 'true', 'false'].includes(this.alert.value)) errors['alert'] = 'Choisissez Tous, Oui ou Non.';
    this.fieldErrors.set(errors);
    this.feedback.set(Object.keys(errors).length ? 'Filtres invalides. Corrigez les champs indiqués ; aucun nouveau chargement effectué.' : '');
    return Object.keys(errors).length ? null : result.period;
  }
  clearPeriod(): void {
    this.startBaseline = restoreMeasurementBound(); this.endBaseline = restoreMeasurementBound();
    this.start.setValue(this.startBaseline.parts, { emitEvent: false }); this.end.setValue(this.endBaseline.parts, { emitEvent: false });
    this.fieldErrors.set({}); this.feedback.set('');
    void this.router.navigate([], { relativeTo: this.route, queryParams: { start_time: null, end_time: null, page: 1 }, queryParamsHandling: 'merge', preserveFragment: true });
  }
  clearFilters(): void {
    this.restoreFilters();
    void this.router.navigate([], { relativeTo: this.route, queryParams: { prediction_type: null, level: null, is_alert: null,
      start_time: null, end_time: null, page: 1, page_size: 20 }, queryParamsHandling: 'merge', preserveFragment: true });
  }
  resetSelection(): void {
    this.company.setValue(null, { emitEvent: false }); this.site.setValue(null, { emitEvent: false }); this.equipment.setValue(null, { emitEvent: false });
    this.facade.load(null); this.sites.clear(); this.equipments.clear(); this.restoreFilters();
    void this.navigate({ page: 1, page_size: 20 });
  }
  changePage(page: number): void {
    const query = this.facade.query();
    if (query && !this.busy() && page >= 1 && (page < this.page() || this.canNext())) void this.navigate({ ...query, page });
  }
  recoverPage(): void { const query = this.facade.query(); if (query && this.facade.state().status === 'out-of-range') void this.navigate({ ...query, page: 1 }); }
  refresh(): void { const query = this.facade.query(); if (query && !this.busy()) this.facade.load(query); }
  private navigate(query: PredictionsQuery): Promise<boolean> {
    return this.router.navigate([], { relativeTo: this.route, queryParams: Object.fromEntries(predictionQueryKeys.map(key => [key, query[key] ?? null])), preserveFragment: true });
  }
  private same(a: Readonly<PredictionsQuery> | null, b: PredictionsQuery): boolean { return a !== null && predictionQueryKeys.every(key => a[key] === b[key]); }
  private boundForm() { return new FormGroup({ date: new FormControl('', { nonNullable: true }), time: new FormControl('', { nonNullable: true }), fraction: new FormControl('', { nonNullable: true }) }); }
  private filterSnapshot(): string { return JSON.stringify([this.predictionType.value, this.level.value, this.alert.value, this.start.getRawValue(), this.end.getRawValue()]); }
  private restoreFilters(start?: string, end?: string, type = '', level = '', alert = ''): void {
    this.startBaseline = restoreMeasurementBound(start); this.endBaseline = restoreMeasurementBound(end);
    this.start.setValue(this.startBaseline.parts, { emitEvent: false }); this.end.setValue(this.endBaseline.parts, { emitEvent: false });
    this.predictionType.setValue(type, { emitEvent: false }); this.level.setValue(level, { emitEvent: false }); this.alert.setValue(alert, { emitEvent: false });
    this.filterBaseline = this.filterSnapshot(); this.draft.set(false); this.fieldErrors.set({}); this.feedback.set('');
  }
}
