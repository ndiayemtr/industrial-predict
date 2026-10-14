import { ComponentFixture, TestBed } from '@angular/core/testing';
import { emptyDashboardResponse } from '../../testing/dashboard-testing';
import { MaintenanceSummaryComponent } from './maintenance-summary.component';

describe('MaintenanceSummaryComponent', () => {
  let fixture: ComponentFixture<MaintenanceSummaryComponent>;
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [MaintenanceSummaryComponent] });
    fixture = TestBed.createComponent(MaintenanceSummaryComponent);
    fixture.componentRef.setInput('summary', emptyDashboardResponse().maintenance);
  });
  it('renders current open statuses, priorities, overdue and missing dates separately from completed period data', () => {
    const summary = emptyDashboardResponse().maintenance;
    summary.open = { ...summary.open, total: 6, planned: 2, in_progress: 3, other: 1,
      priorities: { ...summary.open.priorities, total: 6, distribution: [{ value: 'high', count: 4 }, { value: 'vendor_priority', count: 2 }] } };
    summary.overdue = { overdue: 2, planned_without_planned_at: 1 };
    summary.completed = { ...summary.completed, total: 5, completed_without_completed_at: 3,
      types: { ...summary.completed.types, distribution: [{ value: 'corrective', count: 1 }, { value: 'vendor_type', count: 4 }] } };
    summary.corrective.ratio = { numerator: 1, denominator: 5, percentage: 37.12 };
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    const tables = fixture.nativeElement.querySelectorAll('table');
    expect([...tables[0].querySelectorAll('tbody td')].map((el: Element) => el.textContent)).toEqual(['2', '3', '1']);
    expect(tables[1].textContent).toContain('vendor_priority'); expect(tables[2].textContent).toContain('vendor_type');
    expect(fixture.nativeElement.textContent).toContain('37,12');
    expect(fixture.nativeElement.textContent).toContain('1 interventions correctives sur 5');
    expect(fixture.nativeElement.textContent).toContain('hors décompte de période faute de date de fin');
    const cards = fixture.nativeElement.querySelectorAll('app-dashboard-kpi-card');
    expect([...cards].slice(0, 6).map((el: Element) => el.querySelector('.kpi-value')!.textContent!.trim())).toEqual(['6', '2', '1', '5', '37,12 %', '3']);
    expect(cards[1].textContent).toContain('Au calcul'); expect(cards[2].textContent).toContain('État actuel');
    expect(cards[3].textContent).toContain('Sur la période'); expect(cards[5].textContent).toContain('État actuel');
    expect(fixture.componentInstance.categoryLabel('predictive', 'priority')).toContain('non reconnus : predictive');
  });
  it('shows partial downtime coverage and preserves the provided sums and percentage', () => {
    const summary = emptyDashboardResponse().maintenance;
    summary.downtime = { total_minutes: 90, total_hours: 1.5,
      coverage: { valid_values: 2, eligible_records: 5, ratio: { numerator: 2, denominator: 5, percentage: 40 } } };
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('90 min'); expect(fixture.nativeElement.textContent).toContain('1,5 h');
    expect(fixture.nativeElement.textContent).toContain('40 %'); expect(fixture.nativeElement.textContent).toContain('2 durées valides sur 5');
    expect(fixture.nativeElement.querySelector('.coverage-context').textContent).toContain('Couverture partielle');
  });
  it('keeps a declared zero with full coverage distinct from missing durations', () => {
    const summary = emptyDashboardResponse().maintenance;
    summary.downtime = { total_minutes: 0, total_hours: 0,
      coverage: { valid_values: 2, eligible_records: 2, ratio: { numerator: 2, denominator: 2, percentage: 100 } } };
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('0 min'); expect(fixture.nativeElement.textContent).toContain('0 h');
    expect(fixture.nativeElement.querySelector('.coverage-context').textContent).toContain('Couverture complète');
    summary.downtime = { total_minutes: null, total_hours: null,
      coverage: { valid_values: 0, eligible_records: 2, ratio: { numerator: 0, denominator: 2, percentage: 0 } } };
    fixture.componentRef.setInput('summary', { ...summary }); fixture.detectChanges();
    const values = [...fixture.nativeElement.querySelectorAll('.kpi-value')].map((el: Element) => el.textContent);
    expect(values.slice(-3)).toEqual(['Non renseignée', 'Non renseignée', '0 %']);
    expect(fixture.nativeElement.querySelector('.coverage-context').textContent).toContain('Aucune durée valide renseignée');
  });
  it('explains no eligible intervention with zero sums and null ratios', () => {
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Aucune intervention terminée éligible');
    expect(fixture.nativeElement.textContent).toContain('0 min');
    expect(fixture.nativeElement.textContent).toContain('Non calculable');
    expect(fixture.nativeElement.querySelector('h1')).toBeNull();
    expect(fixture.nativeElement.querySelector('table tbody th').getAttribute('scope')).toBe('row');
  });
  it.each([null, 'USD'])('does not display a monetary amount or currency (%s) in V1', currency => {
    const summary = emptyDashboardResponse().maintenance; summary.cost = { ...summary.cost, total_cost: 987654.32, currency };
    fixture.componentRef.setInput('summary', summary); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).not.toContain('987');
    expect(fixture.nativeElement.textContent).not.toContain('USD');
    expect(fixture.nativeElement.textContent).toContain('Affichage monétaire différé');
  });
});
