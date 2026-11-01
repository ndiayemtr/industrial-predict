import { ComponentFixture, TestBed } from '@angular/core/testing';
import { emptyDashboardResponse } from '../../testing/dashboard-testing';
import { MeasurementSummaryComponent } from './measurement-summary.component';

describe('MeasurementSummaryComponent', () => {
  let fixture: ComponentFixture<MeasurementSummaryComponent>;
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [MeasurementSummaryComponent] });
    fixture = TestBed.createComponent(MeasurementSummaryComponent);
    const data = emptyDashboardResponse();
    fixture.componentRef.setInput('summary', data.measurements);
    fixture.componentRef.setInput('period', data.period);
  });
  it('renders the six declared quality counts, unknown categories and the supplied ratio without recalculation', () => {
    const summary = emptyDashboardResponse().measurements;
    summary.quality = { total: 22, good: 1, suspect: 2, bad: 3, missing: 4, estimated: 5, other: 7,
      distribution: [{ value: 'good', count: 1 }, { value: 'vendor_quality', count: 7 }, { value: 'null', count: 0 }],
      good_ratio: { numerator: 1, denominator: 22, percentage: 17.89 } };
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    expect([...fixture.nativeElement.querySelectorAll('.quality-counts dd')].map((el: Element) => el.textContent)).toEqual(['1', '2', '3', '4', '5', '7']);
    expect(fixture.nativeElement.querySelector('.kpi-value').textContent).toContain('17,89');
    expect(fixture.nativeElement.textContent).toContain('1 mesures de qualité bonne sur 22');
    expect(fixture.nativeElement.querySelector('table').textContent).toContain('Autres / non reconnus : vendor_quality');
    expect(fixture.nativeElement.querySelector('table').textContent).toContain('Autres / non reconnus : null');
    expect(fixture.componentInstance.qualityLabel('__proto__')).toContain('non reconnus : __proto__');
  });
  it('keeps UTC daily dates and zero counts, with a partial-day explanation', () => {
    const summary = emptyDashboardResponse().measurements;
    summary.daily_volume = [{ date: '2026-10-01', count: 0 }, { date: '2026-10-02', count: 12 }];
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    const table = fixture.nativeElement.querySelectorAll('table')[1];
    expect(table.querySelectorAll('tbody tr')).toHaveLength(2);
    expect(table.querySelector('tbody th').textContent).toBe('2026-10-01');
    expect(table.querySelector('tbody td').textContent).toBe('0');
    expect(table.querySelector('caption').textContent).toContain('Sur la période');
    expect(fixture.nativeElement.textContent).toContain('journées de début et de fin peuvent être partielles');
    const details = fixture.nativeElement.querySelector('.daily-details') as HTMLDetailsElement;
    expect(details.open).toBe(false);
    expect(details.querySelector('summary')!.textContent).toContain('jours à zéro inclus');
    details.open = true;
    expect(details.querySelectorAll('tbody tr')).toHaveLength(2);
  });
  it('presents readable ages with exact API seconds in keyboard-accessible details', () => {
    const data = emptyDashboardResponse();
    data.measurements.last_measurements = [{ sensor_id: 1, sensor_name: 'Pression', sensor_code: 'P1', equipment_id: 42,
      timestamp: '2026-10-01T00:00:00Z', value: 1, unit: 'bar', quality: 'good', age_seconds: 12000 }];
    fixture.componentRef.setInput('summary', data.measurements); fixture.detectChanges();
    const age = fixture.nativeElement.querySelector('.last-readings li').querySelectorAll('dd')[5];
    expect(age.textContent).toContain('3 heures et 20 minutes');
    expect(age.querySelector('details summary').textContent).toBe('Valeur exacte');
    expect(age.querySelector('details').textContent).toContain('12000 secondes');
    expect(data.measurements.last_measurements[0].age_seconds).toBe(12000);
  });
  it('shows out-of-period last readings, raw precision, unknown units and the API age at calculation', () => {
    const data = emptyDashboardResponse();
    data.measurements.last_measurements = [{ sensor_id: 1, sensor_name: 'Pression', sensor_code: 'P-01', equipment_id: 42,
      timestamp: '2026-09-01T12:00:00Z', value: 0.123456, unit: 'vendor/unit', quality: 'vendor_quality', age_seconds: 123.456 }];
    fixture.componentRef.setInput('summary', data.measurements); fixture.detectChanges();
    const text = fixture.nativeElement.querySelector('.last-readings').textContent;
    for (const value of ['Pression', 'P-01', 'Équipement indisponible', '01/09/2026 à 12:00:00 UTC', '0.123456', 'vendor/unit', 'vendor_quality', '123.456']) expect(text).toContain(value);
    expect(fixture.nativeElement.querySelector('.last-readings dd').textContent).not.toContain('42');
    fixture.componentRef.setInput('equipmentLabels', { 42: 'Pompe - P42' }); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.last-readings dd').textContent).toBe('Pompe - P42');
    expect(data.measurements.last_measurements[0].equipment_id).toBe(42);
    fixture.componentRef.setInput('equipmentLabels', { 42: 'Référence indisponible' }); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.last-readings dd').textContent).toBe('Équipement indisponible');
    expect(fixture.nativeElement.querySelector('.last-readings dd').getAttribute('aria-live')).toBe('polite');
    expect(fixture.nativeElement.textContent).toContain('14/10/2026 à 00:00:00 UTC');
    expect(fixture.nativeElement.textContent).toContain('indépendamment de la période sélectionnée');
    expect(fixture.nativeElement.textContent).toContain('n’est pas actualisé automatiquement');
  });
  it('distinguishes no reading, null fields and a real zero value/age', () => {
    const summary = emptyDashboardResponse().measurements;
    const reading = { sensor_id: 1, sensor_name: 'Capteur', sensor_code: 'S-1', equipment_id: 42,
      timestamp: null, value: null, unit: null, quality: null, age_seconds: null };
    summary.last_measurements = [reading, { ...reading, sensor_id: 2, timestamp: '2026-10-01T00:00:00Z', value: 0, age_seconds: 0 }];
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    const items = fixture.nativeElement.querySelectorAll('.last-readings li');
    expect(items[0].textContent).toContain('Aucun relevé disponible au calcul');
    expect(items[0].textContent).toContain('Non renseignée');
    expect(items[0].querySelector('dd span')).toBeNull();
    expect(items[1].querySelectorAll('dd')[2].textContent).toBe('0');
    expect(items[1].querySelectorAll('dd')[5].textContent).toContain('0 s');
  });
  it('renders null ratios and empty collections without inventing rows or a second h1', () => {
    const summary = emptyDashboardResponse().measurements; summary.daily_volume = [];
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.kpi-value').textContent).toBe('Non calculable');
    expect(fixture.nativeElement.textContent).toContain('Aucun volume quotidien fourni');
    expect(fixture.nativeElement.textContent).toContain('Aucun capteur ou relevé fourni');
    expect(fixture.nativeElement.querySelector('h1')).toBeNull();
    expect(fixture.nativeElement.querySelector('table thead th').getAttribute('scope')).toBe('col');
  });
  it('keeps all-zero daily values and quality categories in closed, operable details', () => {
    const summary = emptyDashboardResponse().measurements;
    summary.daily_volume = [{ date: '2026-10-01', count: 0 }, { date: '2026-10-02', count: 0 }];
    summary.quality.distribution = [{ value: 'vendor_quality', count: 0 }];
    const snapshot = JSON.stringify(summary);
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('app-daily-volume-chart svg')).toBeNull();
    expect(fixture.nativeElement.textContent).toContain('Aucune mesure enregistrée sur la période sélectionnée');
    for (const details of fixture.nativeElement.querySelectorAll('.quality-details, .daily-details') as NodeListOf<HTMLDetailsElement>) {
      expect(details.open).toBe(false);
      expect(details.querySelector('summary')!.textContent).toContain('Voir les détails');
      details.querySelector('summary')!.click(); expect(details.open).toBe(true);
      details.querySelector('summary')!.click(); expect(details.open).toBe(false);
    }
    expect(fixture.nativeElement.querySelector('.quality-details').textContent).toContain('vendor_quality');
    expect(fixture.nativeElement.querySelectorAll('.daily-details tbody tr')).toHaveLength(2);
    expect(JSON.stringify(summary)).toBe(snapshot);
  });
});
