import { DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, HostListener, Injector, afterNextRender, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NbToastrService } from '@nebular/theme';
import { SensorRead } from '../../models/sensor.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { SensorField, SensorFieldErrors, SensorFormComponent } from '../../components/sensor-form/sensor-form.component';
import { SensorsApiService } from '../../data-access/sensors-api.service';
import { SensorCreate } from '../../models/sensor-write.model';
import { SensorCreateReferencesFacade } from './sensor-create-references.facade';

function positive(raw: string | null, fallback?: number, max = Number.MAX_SAFE_INTEGER): number | undefined {
  return raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= max ? Number(raw) : fallback;
}

@Component({
  selector: 'app-sensor-create', standalone: true,
  imports: [SensorFormComponent, RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  providers: [SensorCreateReferencesFacade], templateUrl: './sensor-create.component.html',
  styleUrl: './sensor-create.component.scss', changeDetection: ChangeDetectionStrategy.OnPush
})
export class SensorCreateComponent {
  readonly references = inject(SensorCreateReferencesFacade);
  private readonly api = inject(SensorsApiService);
  private readonly router = inject(Router);
  private readonly toastr = inject(NbToastrService);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly params = inject(ActivatedRoute).snapshot.queryParamMap;
  private readonly validCompany = positive(this.params.get('company_id'));
  private readonly validSite = positive(this.params.get('site_id'));
  private readonly validEquipment = positive(this.params.get('equipment_id'));
  private readonly completeContext = this.validCompany !== undefined && this.validSite !== undefined && this.validEquipment !== undefined;
  private readonly returnPrefix = this.params.keys.some(key => key.startsWith('return_')) ? 'return_' : '';
  private readonly returnValue = (key: string) => this.params.get(this.returnPrefix + key);
  private readonly search = this.returnValue('search')?.trim() ?? '';
  private readonly context = {
    company_id: positive(this.returnValue('company_id')), site_id: positive(this.returnValue('site_id')), equipment_id: positive(this.returnValue('equipment_id')),
    page: positive(this.returnValue('page'), 1)!, page_size: positive(this.returnValue('page_size'), 20, 100)!,
    search: this.search && this.search.length <= 100 ? this.search : undefined,
    status: (['active', 'inactive'] as const).find(value => value === this.returnValue('status'))
  };
  readonly contextNotice = !this.completeContext && ['company_id', 'site_id', 'equipment_id'].some(key => this.params.has(key))
    ? 'Le contexte est partiel ou invalide. Choisissez explicitement une entreprise, un site et un équipement.' : '';
  readonly listQuery = () => this.context;
  readonly editor = viewChild(SensorFormComponent);
  readonly state = signal<'idle' | 'saving' | 'success' | 'error'>('idle');
  readonly message = signal('');
  readonly fieldErrors = signal<SensorFieldErrors>({});
  readonly uncertain = signal(false);
  readonly created = signal<SensorRead | null>(null);
  private notified = false;
  private opening = false;

  constructor() {
    this.references.choose(this.completeContext ? this.validCompany! : null, this.completeContext ? this.validSite! : null,
      this.completeContext ? this.validEquipment! : null, this.completeContext);
  }
  locked(): boolean { return this.state() === 'saving' || this.state() === 'success' || this.uncertain(); }
  selectCompany(id: number | null): void { if (!this.locked()) this.references.choose(id, null, null); }
  selectSite(id: number | null): void {
    if (!this.locked()) this.references.choose(this.editor()?.form.controls.company_id.value ?? null, id, null);
  }
  selectEquipment(id: number | null): void {
    if (!this.locked()) this.references.choose(this.editor()?.form.controls.company_id.value ?? null, this.editor()?.form.controls.site_id.value ?? null, id);
  }
  verifyReferences(): void { if (!this.locked()) this.references.verify(); }
  clearFieldErrors(): void { this.fieldErrors.set({}); }
  acknowledgeVerification(): void { if (this.state() === 'error') this.uncertain.set(false); }
  cancel(): void { void this.router.navigate(['/sensors'], { queryParams: this.listQuery() }); }

  save(body: SensorCreate): void {
    const company = this.references.company(), site = this.references.site(), equipment = this.references.equipment();
    if (this.locked() || this.references.state() !== 'ready' || !company || !site || !equipment || site.company_id !== company.id || equipment.site_id !== site.id
      || body.equipment_id !== equipment.id || this.editor()?.form.controls.equipment_id.value !== equipment.id || this.editor()?.form.controls.company_id.value !== company.id
      || this.editor()?.form.controls.site_id.value !== site.id) return;
    const payload: SensorCreate = { equipment_id: equipment.id, name: body.name, code: body.code,
      sensor_type: body.sensor_type, unit: body.unit, status: body.status,
      ...(Object.hasOwn(body, 'description') ? { description: body.description } : {}) };
    this.state.set('saving'); this.fieldErrors.set({}); this.message.set('');
    this.api.create(payload).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ next: sensor => {
      if (!Number.isSafeInteger(sensor.id) || sensor.id < 1 || sensor.equipment_id !== equipment.id) {
        this.saveError(new HttpErrorResponse({ status: 502 })); return;
      }
      this.created.set(sensor); this.state.set('success'); void this.openCreated(sensor);
    }, error: (error: unknown) => this.saveError(error) });
  }
  recoveryUrl(): string { return this.router.createUrlTree(['/sensors', this.created()!.id], { queryParams: this.successQuery(this.created()!) }).toString(); }
  recover(event: MouseEvent): void {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); const created = this.created(); if (created) void this.openCreated(created);
  }
  private successQuery(sensor: SensorRead) {
    const company = this.references.company(), site = this.references.site();
    return this.context.company_id === company?.id && this.context.site_id === site?.id && this.context.equipment_id === sensor.equipment_id
      ? this.context : { company_id: company?.id, site_id: site?.id, equipment_id: sensor.equipment_id, page: 1, page_size: 20 };
  }
  private async openCreated(equipment: SensorRead): Promise<void> {
    if (this.opening) return; this.opening = true;
    try {
      const navigated = await this.router.navigate(['/sensors', equipment.id], {
        queryParams: this.successQuery(equipment), state: { createdSensorId: equipment.id }
      });
      if (navigated && !this.notified) { this.notified = true; this.toastr.success('Capteur créé avec succès.', ''); }
      if (!navigated) this.navigationFailed();
    } catch { this.navigationFailed(); }
    finally { this.opening = false; }
  }
  private navigationFailed(): void {
    this.message.set('Le capteur est créé, mais sa fiche n’a pas pu être ouverte. Utilisez le lien de récupération sans soumettre à nouveau.');
  }
  private saveError(error: unknown): void {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    const fields: SensorFieldErrors = {};
    const allowed = ['equipment_id', 'name', 'code', 'sensor_type', 'unit', 'status', 'description'] as const;
    if (status === 422 && error instanceof HttpErrorResponse && Array.isArray(error.error?.detail)) {
      for (const item of error.error.detail) {
        if (Array.isArray(item?.loc) && item.loc.length === 2 && item.loc[0] === 'body' && allowed.includes(item.loc[1])) {
          fields[item.loc[1] as SensorField] = 'Cette valeur n’est pas acceptée par le serveur.';
        }
      }
    }
    if (status === 404) this.references.invalidate();
    this.fieldErrors.set(fields); this.uncertain.set(status === 0 || status >= 500);
    this.message.set(status === 409 ? 'Le serveur signale un conflit. Vérifiez l’équipement et le code global du capteur. La cause exacte n’est pas précisée.'
      : status === 422 ? 'Le serveur a refusé les données. Vérifiez les champs signalés ; une autre contrainte peut aussi être en cause.'
      : status === 404 ? 'Le rattachement peut être devenu indisponible. Vos saisies sont conservées.'
      : this.uncertain() ? 'La création n’a pas pu être confirmée. Le capteur peut avoir été créé. Vérifiez la liste avant toute nouvelle soumission.'
      : 'Le serveur a refusé la création. Vos saisies sont conservées.');
    this.state.set('error');
    const first = this.editor()?.fieldOrder.find(field => fields[field]);
    if (first) {
      const focus = afterNextRender(() => this.editor()?.focusField(first), { injector: this.injector });
      this.destroyRef.onDestroy(() => focus.destroy());
    }
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
