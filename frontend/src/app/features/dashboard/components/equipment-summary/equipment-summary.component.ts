import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { EquipmentCriticalitySummary, EquipmentStatusSummary } from '../../models/dashboard.model';
import { DashboardKpiCardComponent } from '../dashboard-kpi-card/dashboard-kpi-card.component';

const statusLabels: Readonly<Record<string, string>> = { operational: 'Opérationnel', maintenance: 'En maintenance', out_of_service: 'Hors service' };
const criticalityLabels: Readonly<Record<string, string>> = { low: 'Faible', medium: 'Moyenne', high: 'Élevée', critical: 'Critique' };

@Component({
  selector: 'app-equipment-summary', standalone: true,
  imports: [DashboardKpiCardComponent],
  templateUrl: './equipment-summary.component.html',
  styleUrl: './equipment-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class EquipmentSummaryComponent {
  readonly status = input.required<EquipmentStatusSummary>();
  readonly criticality = input.required<EquipmentCriticalitySummary>();
  categoryLabel(value: string, kind: 'status' | 'criticality'): string {
    const labels = kind === 'status' ? statusLabels : criticalityLabels;
    return Object.hasOwn(labels, value) ? labels[value] : `Autres / non reconnus : ${value}`;
  }
}
