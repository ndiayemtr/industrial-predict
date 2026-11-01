import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { DailyMeasurementCount } from '../../models/dashboard.model';

@Component({
  selector: 'app-daily-volume-chart', standalone: true,
  templateUrl: './daily-volume-chart.component.html',
  styleUrl: './daily-volume-chart.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush
})
export class DailyVolumeChartComponent {
  readonly days = input.required<readonly DailyMeasurementCount[]>();
  readonly seriesState = computed(() => {
    const days = this.days();
    if (!days.length) return 'unavailable';
    if (days.some(day => typeof day.count !== 'number' || !Number.isSafeInteger(day.count) || day.count < 0)) return 'invalid';
    return days.every(day => day.count === 0) ? 'empty' : 'data';
  });
  readonly maximum = computed(() => this.days().reduce((max, day) => Math.max(max, day.count), 0));
  readonly zeroDays = computed(() => this.days().filter(day => day.count === 0).length);
  readonly points = computed(() => {
    const days = this.days(); const max = this.maximum();
    return days.map((day, index) => `${days.length === 1 ? 400 : 16 + index / (days.length - 1) * 768},${max > 0 ? 130 - day.count / max * 112 : 130}`).join(' ');
  });
  readonly description = computed(() => `${this.days().length} journées UTC, dont ${this.zeroDays()} à zéro. Maximum quotidien : ${this.maximum()} mesures. Les valeurs exactes de chaque jour figurent dans le tableau repliable ci-dessous.`);
}
