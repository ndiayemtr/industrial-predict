import { DOCUMENT } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, HostListener, Injector, afterNextRender, inject, signal, viewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { NbToastrService } from '@nebular/theme';
import { EquipmentRead } from '../../../../core/models/reference-data.model';
import { PageHeaderComponent } from '../../../../shared/components/page-header/page-header.component';
import { LoadingStateComponent } from '../../../../shared/components/loading-state/loading-state.component';
import { ErrorStateComponent } from '../../../../shared/components/error-state/error-state.component';
import { EquipmentField, EquipmentFieldErrors, EquipmentFormComponent } from '../../components/equipment-form/equipment-form.component';
import { EquipmentsApiService } from '../../data-access/equipments-api.service';
import { EquipmentCreate } from '../../models/equipment-write.model';
import { equipmentCriticalityLabels, equipmentStatusLabels } from '../../models/equipment-labels';
import { EquipmentCreateReferencesFacade } from './equipment-create-references.facade';

function positive(raw: string | null, fallback?: number, max = Number.MAX_SAFE_INTEGER): number | undefined {
  return raw !== null && /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 && Number(raw) <= max ? Number(raw) : fallback;
}

@Component({
  selector: 'app-equipment-create', standalone: true,
  imports: [EquipmentFormComponent, RouterLink, PageHeaderComponent, LoadingStateComponent, ErrorStateComponent],
  providers: [EquipmentCreateReferencesFacade], templateUrl: './equipment-create.component.html',
  styleUrl: './equipment-create.component.scss', changeDetection: ChangeDetectionStrategy.OnPush
})
export class EquipmentCreateComponent {
  readonly references = inject(EquipmentCreateReferencesFacade);
  private readonly api = inject(EquipmentsApiService);
  private readonly router = inject(Router);
  private readonly toastr = inject(NbToastrService);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly params = inject(ActivatedRoute).snapshot.queryParamMap;
  private readonly validCompany = positive(this.params.get('company_id'));
  private readonly invalidCompany = this.params.has('company_id') && this.validCompany === undefined;
  private readonly validSite = this.invalidCompany ? undefined : positive(this.params.get('site_id'));
  private readonly search = this.params.get('search')?.trim() ?? '';
  private readonly context = {
    company_id: this.validCompany, site_id: this.validSite,
    page: positive(this.params.get('page'), 1)!, page_size: positive(this.params.get('page_size'), 20, 100)!,
    search: this.search && this.search.length <= 100 ? this.search : undefined,
    status: (Object.keys(equipmentStatusLabels()) as EquipmentRead['status'][]).find(value => value === this.params.get('status')),
    criticality: (Object.keys(equipmentCriticalityLabels()) as EquipmentRead['criticality'][]).find(value => value === this.params.get('criticality'))
  };
  readonly contextNotice = this.invalidCompany || (this.params.has('site_id') && this.validSite === undefined)
    ? 'Le contexte de rattachement est invalide. Choisissez explicitement une entreprise et un site disponibles.' : '';
  readonly listQuery = () => this.context;
  readonly editor = viewChild(EquipmentFormComponent);
  readonly state = signal<'idle' | 'saving' | 'success' | 'error'>('idle');
  readonly message = signal('');
  readonly fieldErrors = signal<EquipmentFieldErrors>({});
  readonly uncertain = signal(false);
  readonly created = signal<EquipmentRead | null>(null);
  private notified = false;
  private opening = false;

  constructor() { this.references.choose(this.validCompany ?? null, this.validSite ?? null, true); }
  locked(): boolean { return this.state() === 'saving' || this.state() === 'success' || this.uncertain(); }
  selectCompany(id: number | null): void { if (!this.locked()) this.references.choose(id, null); }
  selectSite(id: number | null): void {
    if (!this.locked()) this.references.choose(this.editor()?.form.controls.company_id.value ?? null, id);
  }
  verifyReferences(): void { if (!this.locked()) this.references.verify(); }
  clearFieldErrors(): void { this.fieldErrors.set({}); }
  acknowledgeVerification(): void { if (this.state() === 'error') this.uncertain.set(false); }
  cancel(): void { void this.router.navigate(['/equipments'], { queryParams: this.listQuery() }); }

  save(body: EquipmentCreate): void {
    const company = this.references.company(), site = this.references.site();
    if (this.locked() || this.references.state() !== 'ready' || !company || !site || site.company_id !== company.id
      || body.site_id !== site.id || this.editor()?.form.controls.company_id.value !== company.id
      || this.editor()?.form.controls.site_id.value !== site.id) return;
    const payload: EquipmentCreate = { site_id: site.id, name: body.name, code: body.code,
      equipment_type: body.equipment_type, status: body.status, criticality: body.criticality,
      ...(Object.hasOwn(body, 'description') ? { description: body.description } : {}) };
    this.state.set('saving'); this.fieldErrors.set({}); this.message.set('');
    this.api.create(payload).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({ next: equipment => {
      this.created.set(equipment); this.state.set('success'); void this.openCreated(equipment);
    }, error: (error: unknown) => this.saveError(error) });
  }
  recoveryUrl(): string { return this.router.createUrlTree(['/equipments', this.created()!.id], { queryParams: this.listQuery() }).toString(); }
  recover(event: MouseEvent): void {
    if (event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault(); const created = this.created(); if (created) void this.openCreated(created);
  }
  private async openCreated(equipment: EquipmentRead): Promise<void> {
    if (this.opening) return; this.opening = true;
    try {
      const navigated = await this.router.navigate(['/equipments', equipment.id], {
        queryParams: this.listQuery(), state: { createdEquipmentId: equipment.id }
      });
      if (navigated && !this.notified) { this.notified = true; this.toastr.success('Équipement créé avec succès.', ''); }
      if (!navigated) this.navigationFailed();
    } catch { this.navigationFailed(); }
    finally { this.opening = false; }
  }
  private navigationFailed(): void {
    this.message.set('L’équipement est créé, mais sa fiche n’a pas pu être ouverte. Utilisez le lien de récupération sans soumettre à nouveau.');
  }
  private saveError(error: unknown): void {
    const status = error instanceof HttpErrorResponse ? error.status : -1;
    const fields: EquipmentFieldErrors = {};
    const allowed = ['site_id', 'name', 'code', 'equipment_type', 'status', 'criticality', 'description'] as const;
    if (status === 422 && error instanceof HttpErrorResponse && Array.isArray(error.error?.detail)) {
      for (const item of error.error.detail) {
        if (Array.isArray(item?.loc) && item.loc.length === 2 && item.loc[0] === 'body' && allowed.includes(item.loc[1])) {
          fields[item.loc[1] as EquipmentField] = 'Cette valeur n’est pas acceptée par le serveur.';
        }
      }
    }
    if (status === 404) this.references.invalidate();
    this.fieldErrors.set(fields); this.uncertain.set(status === 0 || status >= 500);
    this.message.set(status === 409 ? 'Le serveur signale un conflit. Vérifiez le site et le code global de l’équipement. La cause exacte n’est pas précisée.'
      : status === 422 ? 'Le serveur a refusé les données. Vérifiez les champs signalés ; une autre contrainte peut aussi être en cause.'
      : status === 404 ? 'Le rattachement peut être devenu indisponible. Vos saisies sont conservées.'
      : this.uncertain() ? 'La création n’a pas pu être confirmée. L’équipement peut avoir été créé. Vérifiez la liste avant toute nouvelle soumission.'
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
