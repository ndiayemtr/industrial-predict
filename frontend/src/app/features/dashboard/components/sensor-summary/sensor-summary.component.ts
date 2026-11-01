import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MeasurementActivitySummary, SensorCoverageSummary, SensorStatusSummary } from '../../models/dashboard.model';
import { DistributionChartComponent } from '../distribution-chart/distribution-chart.component';
import { DashboardKpiCardComponent } from '../dashboard-kpi-card/dashboard-kpi-card.component';

const labels: Readonly<Record<string, string>> = { active: 'Actif', inactive: 'Inactif' };

@Component({
  selector: 'app-sensor-summary', standalone: true,
  imports: [DashboardKpiCardComponent, DistributionChartComponent],
  templateUrl: './sensor-summary.component.html',
  styleUrl: './sensor-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class SensorSummaryComponent {
  readonly status = input.required<SensorStatusSummary>();
  readonly coverage = input.required<SensorCoverageSummary>();
  readonly activity = input.required<MeasurementActivitySummary>();
  readonly statusBars = computed(() => this.status().distribution.map(item => ({ label: this.categoryLabel(item.value), count: item.count })));
  categoryLabel(value: string): string {
    return Object.hasOwn(labels, value) ? labels[value] : `Autres / non reconnus : ${value}`;
  }
}
