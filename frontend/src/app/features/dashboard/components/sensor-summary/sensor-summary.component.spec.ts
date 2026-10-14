import { ComponentFixture, TestBed } from '@angular/core/testing';
import { emptyDashboardResponse } from '../../testing/dashboard-testing';
import { SensorSummaryComponent } from './sensor-summary.component';

describe('SensorSummaryComponent', () => {
  let fixture: ComponentFixture<SensorSummaryComponent>;
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [SensorSummaryComponent] });
    fixture = TestBed.createComponent(SensorSummaryComponent);
    const data = emptyDashboardResponse();
    fixture.componentRef.setInput('status', { ...data.sensor_status,
      distribution: [{ value: 'active', count: 0 }, { value: 'custom_sensor_status', count: 4 }] });
    fixture.componentRef.setInput('coverage', { ...data.sensor_coverage, coverage: { numerator: 3, denominator: 7, percentage: 42.86 } });
    fixture.componentRef.setInput('activity', { ...data.measurements.activity,
      active_sensors_reporting_ratio: { numerator: 2, denominator: 6, percentage: 33.33 } });
    fixture.detectChanges();
  });
  it('distinguishes equipment coverage from emission by currently active sensors on the period', () => {
    const cards = fixture.nativeElement.querySelectorAll('app-dashboard-kpi-card');
    expect(cards[1].textContent).toContain('42,86'); expect(cards[1].textContent).toContain('État actuel');
    expect(cards[1].textContent).toContain('3 équipements avec au moins un capteur actif sur 7');
    expect(cards[2].textContent).toContain('33,33'); expect(cards[2].textContent).toContain('Sur la période');
    expect(cards[2].textContent).toContain('2 capteurs actuellement actifs ayant émis sur 6');
    expect(cards[2].textContent).toContain('Fin de période exclusive');
  });
  it('preserves unknown categories, table semantics and zero counts', () => {
    expect(fixture.nativeElement.querySelector('table').textContent).toContain('custom_sensor_status');
    expect(fixture.nativeElement.querySelector('tbody td').textContent).toBe('0');
    expect(fixture.nativeElement.querySelector('caption')).not.toBeNull();
    expect(fixture.nativeElement.querySelector('h1')).toBeNull();
    expect(fixture.componentInstance.categoryLabel('toString')).toContain('non reconnus : toString');
  });
  it('preserves all null ratios as non calculable', () => {
    const data = emptyDashboardResponse();
    fixture.componentRef.setInput('coverage', data.sensor_coverage); fixture.componentRef.setInput('activity', data.measurements.activity); fixture.detectChanges();
    expect([...fixture.nativeElement.querySelectorAll('.kpi-value')].map((el: Element) => el.textContent)).toEqual(['Non calculable', 'Non calculable', 'Non calculable']);
  });
});
