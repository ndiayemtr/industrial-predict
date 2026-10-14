import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { MeasurementActivitySummary, SensorCoverageSummary, SensorStatusSummary } from '../../models/dashboard.model';
import { DashboardKpiCardComponent } from '../dashboard-kpi-card/dashboard-kpi-card.component';

const labels: Readonly<Record<string, string>> = { active: 'Actif', inactive: 'Inactif' };

@Component({
  selector: 'app-sensor-summary', standalone: true,
  imports: [DashboardKpiCardComponent],
  templateUrl: './sensor-summary.component.html',
  styleUrl: './sensor-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SensorSummaryComponent {
  readonly status = input.required<SensorStatusSummary>();
  readonly coverage = input.required<SensorCoverageSummary>();
  readonly activity = input.required<MeasurementActivitySummary>();
  categoryLabel(value: string): string {
    return Object.hasOwn(labels, value) ? labels[value] : `Autres / non reconnus : ${value}`;
  }
}
