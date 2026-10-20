import { DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, HostListener, Injector, afterNextRender, computed, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed, toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NbToastrService } from '@nebular/theme';
import { EMPTY, Subject, catchError, distinctUntilChanged, map, startWith, switchMap, takeUntil, tap } from 'rxjs';
import { ReferenceDataApiService } from '../../../../core/api/reference-data-api.service';
import { CompanyRead, EquipmentRead, SiteRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { businessReferenceLabel } from '../../../../shared/utils/business-reference-label';
import { formatAdministrativeDateTime } from '../../../../shared/utils/datetime-display';
import { SensorFormComponent, SensorFieldErrors } from '../../components/sensor-form/sensor-form.component';
import { SensorsApiService } from '../../data-access/sensors-api.service';
import { SensorRead } from '../../models/sensor.model';

function positive(raw: string | null, fallback?: number, maximum = Number.MAX_SAFE_INTEGER): number | undefined {
  return raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= maximum ? Number(raw) : fallback;
}
type ReadError = { title: string; message: string; retryable: boolean };

@Component({
  selector: 'app-sensor-edit', standalone: true,
  imports: [SensorFormComponent, RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  templateUrl: './sensor-edit.component.html', styleUrl: './sensor-edit.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SensorEditComponent {
  private readonly api = inject(SensorsApiService);
  private readonly references = inject(ReferenceDataApiService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly params = toSignal(this.route.queryParamMap, { requireSync: true });
  private readonly toastr = inject(NbToastrService);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly reload = new Subject<void>();
  private readonly referenceReload = new Subject<void>();
  private readonly routeChanged = new Subject<void>();
  private generation = 0;
  private notified = false;
  private opening = false;
  readonly original = signal<SensorRead | null>(null);
  readonly saved = signal<SensorRead | null>(null);
  readonly equipment = signal<EquipmentRead | null>(null);
  readonly site = signal<SiteRead | null>(null);
  readonly company = signal<CompanyRead | null>(null);
  readonly referenceState = signal<'loading' | 'ready' | 'error'>('loading');
  readonly referenceError = signal<ReadError>({ title: '', message: '', retryable: false });
  readonly loadError = signal<ReadError>({ title: '', message: '', retryable: false });
  readonly state = signal<'loading' | 'load-error' | 'idle' | 'saving' | 'success' | 'error'>('loading');
  readonly editor = viewChild(SensorFormComponent);
  readonly fieldErrors = signal<SensorFieldErrors>({});
  readonly message = signal('');
  readonly notice = signal('');
  readonly uncertain = signal(false);
  readonly formatDateTime = formatAdministrativeDateTime;
  readonly companyLabel = computed(() => this.company() ? businessReferenceLabel(this.company()!) : 'Entreprise indisponible');
  readonly siteLabel = computed(() => this.site() ? businessReferenceLabel(this.site()!) : 'Site indisponible');
  readonly equipmentLabel = computed(() => this.equipment() ? businessReferenceLabel(this.equipment()!) : 'Équipement indisponible');
  readonly listQuery = computed(() => {
    const params = this.params(), search = params.get('search')?.trim() ?? '';
    return { company_id: positive(params.get('company_id')), site_id: positive(params.get('site_id')), equipment_id: positive(params.get('equipment_id')),
      page: positive(params.get('page'), 1)!, page_size: positive(params.get('page_size'), 20, 100)!,
      search: search && search.length <= 100 ? search : undefined,
      status: (['active', 'inactive'] as const).find(value => value === params.get('status')) };
  });

  constructor() {
    this.route.paramMap.pipe(map(params => params.get('sensorId')), distinctUntilChanged(), switchMap(raw => {
      this.routeChanged.next(); this.generation++; this.notified = false; this.opening = false;
      this.original.set(null); this.saved.set(null); this.equipment.set(null); this.site.set(null); this.company.set(null); this.uncertain.set(false);
      this.fieldErrors.set({}); this.message.set(''); this.notice.set(''); this.referenceState.set('loading');
      const id = positive(raw);
      if (id === undefined) {
        this.loadError.set({ title: 'Identifiant invalide', message: 'Revenez à la liste pour sélectionner un capteur.', retryable: false });
        this.state.set('load-error'); return EMPTY;
      }
      return this.reload.pipe(startWith(undefined), switchMap(() => {
        this.state.set('loading');
        return this.api.getById(id).pipe(tap(sensor => {
          if (sensor.id !== id) throw new Error('Sensor mismatch');
          this.original.set(sensor); this.state.set('idle');
        }), switchMap(sensor => this.referenceReload.pipe(startWith(undefined), switchMap(() => {
          this.referenceState.set('loading'); this.equipment.set(null); this.site.set(null); this.company.set(null);
          if (positive(String(sensor.equipment_id)) === undefined) {
            this.referenceError.set(this.readError(new Error('Invalid equipment'), 'equipment')); this.referenceState.set('error'); return EMPTY;
          }
          let scope: 'equipment' | 'site' | 'company' = 'equipment';
          return this.references.getEquipmentById(sensor.equipment_id).pipe(tap(equipment => {
            if (equipment.id !== sensor.equipment_id || positive(String(equipment.site_id)) === undefined) throw new Error('Equipment mismatch');
            this.equipment.set(equipment); scope = 'site';
          }), switchMap(equipment => this.references.getSiteById(equipment.site_id)), tap(site => {
            if (site.id !== this.equipment()?.site_id || positive(String(site.company_id)) === undefined) throw new Error('Site mismatch');
            this.site.set(site); scope = 'company';
          }), switchMap(site => this.references.getCompanyById(site.company_id)), tap(company => {
            if (company.id !== this.site()?.company_id) throw new Error('Company mismatch');
            this.company.set(company); this.referenceState.set('ready');
          }), catchError((error: unknown) => {
            this.referenceError.set(this.readError(error, scope)); this.referenceState.set('error'); return EMPTY;
          }));
        }))), catchError((error: unknown) => {
          this.loadError.set(this.readError(error, 'sensor')); this.state.set('load-error'); return EMPTY;
        }));
      }));
    }), takeUntilDestroyed(this.destroyRef)).subscribe();
  }
  retryLoad(): void { if (this.state() === 'load-error' && this.loadError().retryable) this.reload.next(); }
  retryReferences(): void { if (this.referenceState() === 'error' && this.referenceError().retryable) this.referenceReload.next(); }
  clearFieldErrors(): void { this.fieldErrors.set({}); this.notice.set(''); }
  acknowledgeVerification(): void { if (this.state() === 'error') this.uncertain.set(false); }
  cancel(): void { void this.router.navigate(this.original() ? ['/sensors', this.original()!.id] : ['/sensors'], { queryParams: this.listQuery() }); }

  save(): void {
    const original = this.original(), editor = this.editor();
    if (!original || !editor || !['idle', 'error'].includes(this.state()) || this.uncertain() || this.referenceState() !== 'ready') return;
    // Recalculate the raw diff here; never accept additional caller fields.
    const patch = editor.changes();
    if (!Object.keys(patch).length) { this.notice.set('Aucune modification à enregistrer.'); return; }
    if (editor.form.invalid) return;
    this.state.set('saving'); this.message.set(''); this.notice.set(''); this.fieldErrors.set({});
    const generation = this.generation;
    this.api.patch(original.id, patch).pipe(takeUntil(this.routeChanged), takeUntilDestroyed(this.destroyRef)).subscribe({
      next: result => {
        if (result.id !== original.id || result.equipment_id !== original.equipment_id || result.sensor_type !== original.sensor_type || result.unit !== original.unit) {
          this.saveError(new HttpErrorResponse({ status: 502 })); return;
        }
        this.saved.set(result); this.state.set('success'); void this.openUpdated(result, generation); },
      error: (error: unknown) => this.saveError(error)
    });
  }
  recoveryUrl(): string { return this.router.createUrlTree(['/sensors', this.saved()!.id], { queryParams: this.listQuery() }).toString(); }
  recover(event: MouseEvent): void {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); const saved = this.saved(); if (saved) void this.openUpdated(saved, this.generation);
  }
  private async openUpdated(sensor: SensorRead, generation: number): Promise<void> {
    if (this.opening) return; this.opening = true;
    try {
      const navigated = await this.router.navigate(['/sensors', sensor.id], { queryParams: this.listQuery(), state: { updatedSensorId: sensor.id } });
      if (generation !== this.generation) return;
      if (navigated && !this.notified && this.router.isActive(this.router.createUrlTree(['/sensors', sensor.id]),
        { paths: 'exact', queryParams: 'ignored', matrixParams: 'ignored', fragment: 'ignored' })) { this.notified = true; this.toastr.success('Capteur modifié avec succès.', ''); }
      if (!navigated) this.navigationFailed();
    } catch { if (generation === this.generation && !this.destroyRef.destroyed) this.navigationFailed(); }
    finally { if (generation === this.generation) this.opening = false; }
  }
  private navigationFailed(): void {
    this.message.set('Le capteur est modifié, mais sa fiche n’a pas pu être ouverte. Utilisez le lien de récupération sans soumettre à nouveau.');
  }
  private saveError(error: unknown): void {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    const fields: SensorFieldErrors = {};
    const allowed = ['name', 'code', 'status', 'description'] as const;
    if (status === 422 && error instanceof HttpErrorResponse && Array.isArray(error.error?.detail)) {
      for (const item of error.error.detail) {
        if (Array.isArray(item?.loc) && item.loc.length === 2 && item.loc[0] === 'body' && allowed.includes(item.loc[1])) {
          fields[item.loc[1] as typeof allowed[number]] = 'Cette valeur n’est pas acceptée par le serveur.';
        }
      }
    }
    this.fieldErrors.set(fields); this.uncertain.set(status === 0 || status >= 500);
    this.message.set(status === 404 ? 'Ce capteur n’existe plus ou n’est plus disponible. Vos saisies sont conservées ; aucune recréation automatique.'
      : status === 409 ? 'Le serveur signale un conflit. La cause exacte n’est pas précisée. Vos saisies sont conservées.'
      : status === 422 ? 'Le serveur a refusé les données. Vérifiez les champs signalés ; une autre contrainte peut aussi être en cause.'
      : this.uncertain() ? 'La modification n’a pas pu être confirmée. Le capteur peut avoir été modifié. Vérifiez la fiche avant toute nouvelle soumission.'
      : 'Le serveur a refusé la modification. Vos saisies sont conservées.');
    this.state.set('error');
    const first = this.editor()?.fieldOrder.find(field => fields[field]);
    if (first) {
      const focus = afterNextRender(() => this.editor()?.focusField(first), { injector: this.injector });
      this.destroyRef.onDestroy(() => focus.destroy());
    }
  }
  private readError(error: unknown, scope: 'sensor' | 'equipment' | 'site' | 'company'): ReadError {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    return { title: scope === 'equipment' ? 'Équipement industriel indisponible' : scope === 'site' ? 'Site industriel indisponible' : scope === 'company' ? 'Entreprise indisponible'
      : status === 404 ? 'Capteur introuvable (404)' : 'Chargement impossible',
      message: scope !== 'sensor' ? 'Le rattachement reste inchangé. Les références réelles doivent être disponibles et cohérentes avant l’enregistrement. Vos saisies sont conservées.'
        : status === 404 ? 'Ce capteur n’existe pas ou n’est plus disponible.' : 'Les informations du capteur ne peuvent pas être chargées.',
      retryable: status === 0 || status >= 500 };
  }
  canLeave(): boolean {
    if (this.state() === 'saving') return false;
    return this.state() === 'success' || !this.editor()?.hasChanges()
      || (this.document.defaultView?.confirm('Quitter cette page et abandonner les modifications non enregistrées ?') ?? false);
  }
  @HostListener('window:beforeunload', ['$event'])
  protectUnload(event: BeforeUnloadEvent): void {
    if (this.state() === 'saving' || (this.state() !== 'success' && this.editor()?.hasChanges())) { event.preventDefault(); event.returnValue = ''; }
  }
}
