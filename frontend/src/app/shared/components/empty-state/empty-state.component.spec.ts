import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { IconComponent } from '../../ui/icon/icon.component';
import { EmptyStateComponent } from './empty-state.component';

@Component({
  standalone: true,
  imports: [EmptyStateComponent],
  template: `
    <main>
      <h1>Équipements</h1>
      <app-empty-state title="Aucun équipement" message="Ajoutez un équipement pour commencer." icon="equipments">
        <button type="button" (click)="activations = activations + 1">Ajouter un équipement</button>
        <a href="#filters">Modifier les filtres</a>
      </app-empty-state>
    </main>
  `
})
class TestPageComponent {
  activations = 0;
}

describe('EmptyStateComponent', () => {
  let fixture: ComponentFixture<EmptyStateComponent>;
  let root: HTMLElement;

  beforeEach(() => {
    // No API, Router, Nebular or business providers are needed.
    TestBed.configureTestingModule({ imports: [EmptyStateComponent, TestPageComponent] });
    fixture = TestBed.createComponent(EmptyStateComponent);
    fixture.componentRef.setInput('title', 'Aucune mesure');
    fixture.componentRef.setInput('message', 'Aucune donnée ne correspond aux filtres sélectionnés.');
    fixture.detectChanges();
    root = fixture.nativeElement;
  });

  it.each(['title', 'message'])('requires the %s input before rendering', (missing) => {
    const incomplete = TestBed.createComponent(EmptyStateComponent);
    if (missing !== 'title') incomplete.componentRef.setInput('title', 'Aucune mesure');
    if (missing !== 'message') incomplete.componentRef.setInput('message', 'Aucune donnée disponible.');
    expect(() => incomplete.detectChanges()).toThrowError(/NG0950/);
  });

  it('renders the supplied title and message with a semantic h2 and no h1', () => {
    expect(root.querySelectorAll('h2')).toHaveLength(1);
    expect(root.querySelector('h2')?.textContent).toBe('Aucune mesure');
    expect(root.querySelector('p')?.textContent).toBe('Aucune donnée ne correspond aux filtres sélectionnés.');
    expect(root.querySelector('h1')).toBeNull();
    expect(root.querySelector('h2')?.hasAttribute('aria-hidden')).toBe(false);
  });

  it('updates the displayed text when the consumer changes the inputs', () => {
    fixture.componentRef.setInput('title', 'Aucun capteur');
    fixture.componentRef.setInput('message', 'Ajoutez un capteur pour commencer.');
    fixture.detectChanges();
    expect(root.querySelector('h2')?.textContent).toBe('Aucun capteur');
    expect(root.querySelector('p')?.textContent).toBe('Ajoutez un capteur pour commencer.');
  });

  it('does not invent an icon or an action when optional content is absent', () => {
    expect(root.querySelector('app-icon')).toBeNull();
    expect(root.querySelector('.empty-state-actions')?.children).toHaveLength(0);
    expect(root.querySelector('button, a')).toBeNull();
  });

  it('uses an existing local SVG icon as decoration and removes it when unset', () => {
    fixture.componentRef.setInput('icon', 'measurements');
    fixture.detectChanges();
    const icon = fixture.debugElement.query(By.directive(IconComponent));
    expect(icon.componentInstance.name()).toBe('measurements');
    expect(root.querySelector('app-icon')?.getAttribute('aria-hidden')).toBe('true');
    const svg = root.querySelector('svg')!;
    expect(svg.getAttribute('aria-hidden')).toBe('true');
    expect(svg.getAttribute('focusable')).toBe('false');
    expect(svg.querySelector('path')?.getAttribute('d')).toBeTruthy();
    fixture.componentRef.setInput('icon', undefined);
    fixture.detectChanges();
    expect(root.querySelector('svg')).toBeNull();
  });

  it('projects actions and leaves execution with the consuming page', () => {
    const page = TestBed.createComponent(TestPageComponent);
    page.detectChanges();
    const pageRoot: HTMLElement = page.nativeElement;
    const button = pageRoot.querySelector<HTMLButtonElement>('.empty-state-actions button')!;
    const link = pageRoot.querySelector<HTMLAnchorElement>('.empty-state-actions a')!;
    expect(button.textContent).toBe('Ajouter un équipement');
    expect(button.type).toBe('button');
    expect(button.tabIndex).toBe(0);
    expect(link.tabIndex).toBe(0);
    button.focus();
    expect(document.activeElement).toBe(button);
    button.click();
    expect(page.componentInstance.activations).toBe(1);
    expect(pageRoot.querySelectorAll('h1')).toHaveLength(1);
    expect(pageRoot.querySelectorAll('h2')).toHaveLength(1);
  });

  it('does not mark empty data as an error, a loading status or an interactive region', () => {
    expect(root.querySelector('[role="alert"], [role="status"], [aria-live], [aria-busy]')).toBeNull();
    expect(root.querySelector('[tabindex]')).toBeNull();
    expect(root.querySelector('.empty-state-message')?.hasAttribute('aria-hidden')).toBe(false);
  });

  it('escapes title and message rather than interpreting supplied HTML', () => {
    fixture.componentRef.setInput('title', '<em>Aucune mesure</em>');
    fixture.componentRef.setInput('message', '<strong>Aucune donnée</strong>');
    fixture.detectChanges();
    expect(root.querySelector('h2')?.textContent).toBe('<em>Aucune mesure</em>');
    expect(root.querySelector('p')?.textContent).toBe('<strong>Aucune donnée</strong>');
    expect(root.querySelector('em, strong')).toBeNull();
  });
});
