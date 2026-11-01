import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DashboardPeriod, MeasurementSummary } from '../../models/dashboard.model';
import { DailyVolumeChartComponent } from '../daily-volume-chart/daily-volume-chart.component';
import { formatReadingAge } from '../../utils/reading-age';
import { DashboardKpiCardComponent } from '../dashboard-kpi-card/dashboard-kpi-card.component';
import { formatUtcDateTime } from '../../../../shared/utils/datetime-display';

const qualityLabels: Readonly<Record<string, string>> = {
  good: 'Bonne', suspect: 'Suspecte', bad: 'Mauvaise', missing: 'Manquante', estimated: 'Estimée'
};

@Component({
  selector: 'app-measurement-summary', standalone: true,
  imports: [DashboardKpiCardComponent, DailyVolumeChartComponent],
  templateUrl: './measurement-summary.component.html',
  styleUrl: './measurement-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MeasurementSummaryComponent {
  readonly formatDateTime = formatUtcDateTime;
  readonly formatAge = formatReadingAge;
  validAge(value: unknown): boolean {
    return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= Number.MAX_SAFE_INTEGER;
  }
  readonly summary = input.required<MeasurementSummary>();
  readonly period = input.required<DashboardPeriod>();
  readonly equipmentLabels = input<Readonly<Record<number, string>>>({});
  equipmentLabel(id: number): string {
    const label = this.equipmentLabels()[id];
    return !label || label === 'Référence indisponible' ? 'Équipement indisponible' : label;
  }
  qualityLabel(value: string): string {
    return Object.hasOwn(qualityLabels, value) ? qualityLabels[value] : `Autres / non reconnus : ${value}`;
  }
}
