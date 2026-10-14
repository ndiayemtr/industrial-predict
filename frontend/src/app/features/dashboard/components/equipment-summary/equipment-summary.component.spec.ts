import { ComponentFixture, TestBed } from '@angular/core/testing';
import { emptyDashboardResponse } from '../../testing/dashboard-testing';
import { EquipmentSummaryComponent } from './equipment-summary.component';

describe('EquipmentSummaryComponent', () => {
  let fixture: ComponentFixture<EquipmentSummaryComponent>;
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [EquipmentSummaryComponent] });
    fixture = TestBed.createComponent(EquipmentSummaryComponent);
    const data = emptyDashboardResponse();
    fixture.componentRef.setInput('status', { ...data.equipment_status, total: 9,
      distribution: [{ value: 'operational', count: 0 }, { value: 'vendor_status', count: 9 }],
      operational_ratio: { numerator: 0, denominator: 9, percentage: 12.34 } });
    fixture.componentRef.setInput('criticality', { ...data.equipment_criticality, high_or_critical: 8, high_or_critical_unavailable: 3,
      distribution: [{ value: 'vendor_criticality', count: 2 }] });
    fixture.detectChanges();
  });
  it('uses the supplied percentage even when it differs from numerator / denominator', () => {
    expect(fixture.nativeElement.textContent).toContain('12,34');
    expect(fixture.nativeElement.textContent).toContain('0 équipements opérationnels sur 9');
    const values = [...fixture.nativeElement.querySelectorAll('.kpi-value')].map((el: Element) => el.textContent);
    expect(values[1]).toBe('8'); expect(values[2]).toBe('3');
  });
  it('retains unknown categories and real zero counts in accessible tables', () => {
    const tables = fixture.nativeElement.querySelectorAll('table');
    expect(tables).toHaveLength(2);
    expect(tables[0].textContent).toContain('Autres / non reconnus : vendor_status');
    expect(tables[1].textContent).toContain('Autres / non reconnus : vendor_criticality');
    expect(tables[0].querySelector('tbody td').textContent).toBe('0');
    expect(tables[0].querySelector('caption')).not.toBeNull();
    expect(tables[0].querySelector('tbody th').getAttribute('scope')).toBe('row');
    expect(fixture.nativeElement.querySelector('h1')).toBeNull();
    expect(fixture.componentInstance.categoryLabel('high', 'status')).toContain('non reconnus : high');
    expect(fixture.componentInstance.categoryLabel('__proto__', 'status')).toContain('__proto__');
  });
  it('shows a null ratio as non calculable and does not invent missing distribution rows', () => {
    fixture.componentRef.setInput('status', emptyDashboardResponse().equipment_status); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.kpi-value').textContent).toBe('Non calculable');
    expect(fixture.nativeElement.querySelector('table tbody').textContent).toContain('Aucune catégorie fournie');
  });
});
