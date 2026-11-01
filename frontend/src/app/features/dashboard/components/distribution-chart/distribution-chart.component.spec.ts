import { TestBed } from '@angular/core/testing';
import { DistributionChartComponent } from './distribution-chart.component';

describe('DistributionChartComponent', () => {
  it.each([[null, 'Non renseigné'], [undefined, 'Non renseigné'], [0, '0'], [12, '12'], [NaN, 'NaN']])('preserves the visible counter %s as %s', (value, expected) => {
    const fixture = TestBed.createComponent(DistributionChartComponent);
    fixture.componentRef.setInput('title', 'Statuts');
    fixture.componentRef.setInput('items', [{ label: 'Catégorie API', count: value }]); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('strong').textContent).toBe(expected);
  });
  it('renders exact accessible labels and counts; bar lengths do not claim a business percentage', () => {
    const fixture = TestBed.createComponent(DistributionChartComponent);
    const items = [{ label: 'Opérationnel', count: 8 }, { label: 'Inconnu API', count: 4 }, { label: 'En maintenance', count: 0 }];
    const snapshot = JSON.stringify(items);
    fixture.componentRef.setInput('title', 'Statuts'); fixture.componentRef.setInput('items', items);
    fixture.detectChanges();
    const rows = fixture.nativeElement.querySelectorAll('li');
    expect(rows).toHaveLength(3);
    expect(rows[1].textContent).toContain('Inconnu API');
    expect([...rows].map((row: Element) => row.querySelector('strong')!.textContent)).toEqual(['8', '4', '0']);
    expect(rows[0].querySelector('.bar-track').getAttribute('aria-hidden')).toBe('true');
    expect(rows[1].querySelector('.bar-track span').style.width).toBe('50%');
    expect(rows[2].querySelector('.bar-track span').style.width).toBe('0%');
    expect([...rows].map((row: Element) => row.querySelector('.category-marker')!.textContent)).toEqual(['1', '2', '3']);
    expect(fixture.nativeElement.querySelector('.chart-legend').open).toBe(false);
    expect(fixture.nativeElement.querySelector('.chart-note').textContent).toContain('sans indiquer une gravité');
    expect(JSON.stringify(items)).toBe(snapshot);
  });
  it('does not describe an unknown effectif as zero', () => {
    const fixture = TestBed.createComponent(DistributionChartComponent);
    fixture.componentRef.setInput('title', 'Statuts');
    fixture.componentRef.setInput('items', [{ label: 'Inconnu', count: null }]); fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('strong').textContent).toBe('Non renseigné');
    expect(fixture.nativeElement.textContent).not.toContain('Aucun effectif');
  });
  it('keeps empty and all-zero distributions distinct without invalid geometry', () => {
    const fixture = TestBed.createComponent(DistributionChartComponent);
    fixture.componentRef.setInput('title', 'Statuts'); fixture.componentRef.setInput('items', []); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Aucune catégorie');
    fixture.componentRef.setInput('items', [{ label: 'Actif', count: 0 }]); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Aucun effectif');
    expect(fixture.componentInstance.width(0)).toBe(0);
  });
});
