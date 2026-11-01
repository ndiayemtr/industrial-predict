import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export interface DistributionBar { label: string; count: number }

@Component({
  selector: 'app-distribution-chart', standalone: true,
  templateUrl: './distribution-chart.component.html',
  styleUrl: './distribution-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DistributionChartComponent {
  readonly title = input.required<string>();
  readonly items = input.required<readonly DistributionBar[]>();
  readonly allZero = computed(() => this.items().length > 0 && this.items().every(item => item.count === 0));
  readonly maximum = computed(() => Math.max(0, ...this.items().map(item =>
    Number.isFinite(item.count) && item.count >= 0 ? item.count : 0)));
  width(count: number): number {
    return this.maximum() > 0 && Number.isFinite(count) && count >= 0 ? count / this.maximum() * 100 : 0;
  }
  // Preserve the existing nullish fallback without asserting non-null API data.
  displayCount(value: number | null | undefined): number | string {
    return value ?? 'Non renseigné';
  }

}
