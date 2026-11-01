import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export type DashboardTemporalScope = 'État actuel' | 'Sur la période' | 'Au calcul';
const numberFormat = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 });

@Component({
  selector: 'app-dashboard-kpi-card',
  standalone: true,
  templateUrl: './dashboard-kpi-card.component.html',
  styleUrl: './dashboard-kpi-card.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DashboardKpiCardComponent {
  readonly label = input.required<string>();
  readonly value = input.required<number | string | null | undefined>();
  readonly unit = input<string>();
  readonly temporalScope = input.required<DashboardTemporalScope>();
  readonly information = input<string>();
  readonly attention = input(false);
  readonly needsAttention = computed(() => this.attention() && typeof this.value() === 'number' && Number.isFinite(this.value()) && (this.value() as number) > 0);
  readonly formattedValue = computed(() => {
    const value = this.value();
    return value == null ? 'Non renseignée' : typeof value === 'number' ? numberFormat.format(value) : value;
  });
  readonly showUnit = computed(() => typeof this.value() === 'number' && !!this.unit());
}
