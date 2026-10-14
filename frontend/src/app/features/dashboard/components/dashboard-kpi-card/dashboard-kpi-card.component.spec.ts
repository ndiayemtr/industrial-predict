import { ComponentFixture, TestBed } from '@angular/core/testing';
import { DashboardKpiCardComponent } from './dashboard-kpi-card.component';

describe('DashboardKpiCardComponent', () => {
  let fixture: ComponentFixture<DashboardKpiCardComponent>;
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [DashboardKpiCardComponent] });
    fixture = TestBed.createComponent(DashboardKpiCardComponent);
    fixture.componentRef.setInput('label', 'Indicateur API');
    fixture.componentRef.setInput('temporalScope', 'État actuel');
  });
  it.each([0, 1234, 37.29])('formats the real API value %s without a business calculation', value => {
    fixture.componentRef.setInput('value', value); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.kpi-value').textContent).toContain(new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(value));
    expect(fixture.nativeElement.querySelector('h3').textContent).toBe('Indicateur API');
    expect(fixture.nativeElement.querySelector('h1')).toBeNull();
  });
  it.each([null, undefined])('distinguishes an absent value %s from zero', value => {
    fixture.componentRef.setInput('value', value); fixture.componentRef.setInput('unit', '%'); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.kpi-value').textContent).toBe('Non renseignée');
    expect(fixture.nativeElement.querySelector('.unit')).toBeNull();
  });
  it('supports non calculable percentages without a misleading unit', () => {
    fixture.componentRef.setInput('value', 'Non calculable'); fixture.componentRef.setInput('unit', '%'); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.kpi-value').textContent).toBe('Non calculable');
    expect(fixture.nativeElement.querySelector('.unit')).toBeNull();
  });
  it.each(['État actuel', 'Sur la période', 'Au calcul'])('renders temporal context %s and optional information', temporalScope => {
    fixture.componentRef.setInput('value', 0); fixture.componentRef.setInput('unit', '%');
    fixture.componentRef.setInput('temporalScope', temporalScope); fixture.componentRef.setInput('information', '0 sur 12'); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.temporal-scope').textContent).toBe(temporalScope);
    expect(fixture.nativeElement.querySelector('.unit').textContent.trim()).toBe('%');
    expect(fixture.nativeElement.querySelector('.information').textContent).toBe('0 sur 12');
    expect(fixture.nativeElement.querySelector('[role="alert"], [aria-live]')).toBeNull();
  });
});
