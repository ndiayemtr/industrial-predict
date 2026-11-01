import { TestBed } from '@angular/core/testing';
import { DailyVolumeChartComponent } from './daily-volume-chart.component';

describe('DailyVolumeChartComponent', () => {
  it('retains every API day, including zeros, with accessible scale and date bounds', () => {
    const fixture = TestBed.createComponent(DailyVolumeChartComponent);
    const days = [{ date: '2026-10-01', count: 0 }, { date: '2026-10-02', count: 12 }, { date: '2026-10-03', count: 0 }];
    fixture.componentRef.setInput('days', days); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('polyline').getAttribute('points')).toBe('16,130 400,18 784,130');
    expect(fixture.nativeElement.querySelector('svg').getAttribute('role')).toBe('img');
    expect(fixture.nativeElement.querySelector('svg').getAttribute('aria-label')).toContain('Maximum quotidien : 12');
    expect(fixture.nativeElement.textContent).toContain('2 à zéro');
    expect(fixture.nativeElement.textContent).toContain('2026-10-01');
    expect(fixture.nativeElement.textContent).toContain('2026-10-03');
    expect(days[0].count).toBe(0);
  });
  it('uses a compact state for a real zero day and distinguishes an absent series', () => {
    const fixture = TestBed.createComponent(DailyVolumeChartComponent);
    fixture.componentRef.setInput('days', []); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('svg')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Données quotidiennes indisponibles');
    fixture.componentRef.setInput('days', [{ date: '2026-10-01', count: 0 }]); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('svg')).toBeNull();
    expect(fixture.nativeElement.querySelector('.no-measurements').textContent).toBe('Aucune mesure enregistrée sur la période sélectionnée');
    expect(fixture.componentInstance.days()[0].count).toBe(0);
  });
  it('omits the chart for a multi-day all-zero series, without changing the API input', () => {
    const fixture = TestBed.createComponent(DailyVolumeChartComponent);
    const days = [{ date: '2026-10-01', count: 0 }, { date: '2026-10-02', count: 0 }];
    const snapshot = JSON.stringify(days);
    fixture.componentRef.setInput('days', days); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('svg')).toBeNull();
    expect(fixture.nativeElement.querySelector('.no-measurements')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('[role="alert"]')).toBeNull();
    expect(JSON.stringify(days)).toBe(snapshot);
  });
  it.each([null, undefined, NaN, -1])('does not turn an unknown or invalid count into no measurements (%s)', count => {
    const fixture = TestBed.createComponent(DailyVolumeChartComponent);
    fixture.componentRef.setInput('days', [{ date: '2026-10-01', count }]); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('svg, .no-measurements')).toBeNull();
    expect(fixture.nativeElement.querySelector('.unavailable-series')).not.toBeNull();
  });
});
