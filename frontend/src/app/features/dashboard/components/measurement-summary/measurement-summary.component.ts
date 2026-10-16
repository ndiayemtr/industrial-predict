import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { DashboardPeriod, MeasurementSummary } from '../../models/dashboard.model';
import { DashboardKpiCardComponent } from '../dashboard-kpi-card/dashboard-kpi-card.component';
import { formatUtcDateTime } from '../../../../shared/utils/datetime-display';

const qualityLabels: Readonly<Record<string, string>> = {
  good: 'Bonne', suspect: 'Suspecte', bad: 'Mauvaise', missing: 'Manquante', estimated: 'Estimée'
};

@Component({
  selector: 'app-measurement-summary', standalone: true,
  imports: [DashboardKpiCardComponent],
  templateUrl: './measurement-summary.component.html',
  styleUrl: './measurement-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MeasurementSummaryComponent {
  readonly formatDateTime = formatUtcDateTime;
  readonly summary = input.required<MeasurementSummary>();
  readonly period = input.required<DashboardPeriod>();
  qualityLabel(value: string): string {
    return Object.hasOwn(qualityLabels, value) ? qualityLabels[value] : `Autres / non reconnus : ${value}`;
  }
}
