import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { MaintenanceSummary } from '../../models/dashboard.model';
import { DashboardKpiCardComponent } from '../dashboard-kpi-card/dashboard-kpi-card.component';

const priorityLabels: Readonly<Record<string, string>> = { low: 'Faible', medium: 'Moyenne', high: 'Élevée', critical: 'Critique' };
const typeLabels: Readonly<Record<string, string>> = { preventive: 'Préventive', corrective: 'Corrective', predictive: 'Prédictive' };

@Component({
  selector: 'app-maintenance-summary', standalone: true,
  imports: [DashboardKpiCardComponent],
  templateUrl: './maintenance-summary.component.html',
  styleUrl: './maintenance-summary.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class MaintenanceSummaryComponent {
  readonly summary = input.required<MaintenanceSummary>();
  readonly noOpenInterventions = computed(() => {
    const { open, overdue } = this.summary();
    return [open.total, open.planned, open.in_progress, open.other, open.priorities.total, open.priorities.low, open.priorities.medium,
      open.priorities.high, open.priorities.critical, open.priorities.other,
      overdue.overdue, overdue.planned_without_planned_at].every(value => value === 0)
      && open.priorities.distribution.every(category => category.count === 0);
  });
  readonly noCompletedInterventions = computed(() => {
    const completed = this.summary().completed;
    return [completed.total, completed.completed_without_completed_at, completed.types.total, completed.types.preventive,
      completed.types.corrective, completed.types.predictive, completed.types.other,
      this.summary().corrective.ratio.numerator, this.summary().corrective.ratio.denominator].every(value => value === 0)
      && completed.types.distribution.every(category => category.count === 0);
  });
  readonly downtimeContext = computed(() => {
    const coverage = this.summary().downtime.coverage;
    if (coverage.eligible_records === 0) return 'Aucune intervention terminée éligible sur la période ; la somme renvoyée est zéro.';
    if (coverage.valid_values === 0) return 'Aucune durée valide renseignée parmi les interventions éligibles ; somme non renseignée.';
    return coverage.valid_values < coverage.eligible_records ? 'Couverture partielle : la somme porte uniquement sur les durées valides renseignées.' : 'Couverture complète des interventions éligibles.';
  });
  categoryLabel(value: string, kind: 'priority' | 'type'): string {
    const labels = kind === 'priority' ? priorityLabels : typeLabels;
    return Object.hasOwn(labels, value) ? labels[value] : `Autres / non reconnus : ${value}`;
  }
  // Preserve the existing nullish fallback without asserting non-null API data.
  displayCount(value: number | null | undefined): number | string {
    return value ?? 'Non renseigné';
  }

}
