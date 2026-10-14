import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PageHeaderComponent } from './page-header.component';

@Component({
  standalone: true,
  imports: [PageHeaderComponent],
  template: `
    <main>
      <app-page-header [title]="title" [description]="description">
        <button type="button" (click)="activations = activations + 1">Ajouter un équipement</button>
        <a href="#filters">Afficher les filtres</a>
      </app-page-header>
    </main>
  `
})
class TestPageComponent {
  title = 'Équipements';
  description: string | undefined = 'Inventaire des actifs industriels';
  activations = 0;
}

describe('PageHeaderComponent', () => {
  let fixture: ComponentFixture<PageHeaderComponent>;
  let root: HTMLElement;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [PageHeaderComponent, TestPageComponent] });
    fixture = TestBed.createComponent(PageHeaderComponent);
    fixture.componentRef.setInput('title', 'Équipements');
    fixture.detectChanges();
    root = fixture.nativeElement;
  });

  it('requires the title input before rendering', () => {
    const missingTitle = TestBed.createComponent(PageHeaderComponent);
    expect(() => missingTitle.detectChanges()).toThrowError(/NG0950/);
  });

  it('renders exactly one semantic h1 with the supplied title', () => {
    expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('h1')?.textContent).toBe('Équipements');
    expect(root.querySelector('h1')?.hasAttribute('aria-hidden')).toBe(false);
    expect(root.querySelector('[role="banner"]')).toBeNull();
    expect(root.querySelector('[tabindex]')).toBeNull();
  });

  it('updates the title when the consumer changes the input', () => {
    fixture.componentRef.setInput('title', 'Détail équipement');
    fixture.detectChanges();
    expect(root.querySelector('h1')?.textContent).toBe('Détail équipement');
  });

  it.each([undefined, '', '   ', '\n\t'])
    ('omits the description when it is not populated (%j)', (description) => {
      fixture.componentRef.setInput('description', description);
      fixture.detectChanges();
      expect(root.querySelector('p')).toBeNull();
    });

  it('renders and removes an optional description as the input changes', () => {
    fixture.componentRef.setInput('description', 'Inventaire des actifs industriels');
    fixture.detectChanges();
    expect(root.querySelector('p')?.textContent).toBe('Inventaire des actifs industriels');
    fixture.componentRef.setInput('description', undefined);
    fixture.detectChanges();
    expect(root.querySelector('p')).toBeNull();
  });

  it('renders the title as text rather than interpreting HTML', () => {
    fixture.componentRef.setInput('title', '<em>Équipements</em>');
    fixture.detectChanges();
    expect(root.querySelector('h1')?.textContent).toBe('<em>Équipements</em>');
    expect(root.querySelector('em')).toBeNull();
  });

  it('does not invent actions when no content is projected', () => {
    expect(root.querySelector('.page-header-actions')?.children).toHaveLength(0);
    expect(root.querySelector('button, a')).toBeNull();
  });

  it('projects accessible actions and leaves their behavior with the consumer', () => {
    const page = TestBed.createComponent(TestPageComponent);
    page.detectChanges();
    const pageRoot: HTMLElement = page.nativeElement;
    const button = pageRoot.querySelector<HTMLButtonElement>('.page-header-actions button')!;
    const link = pageRoot.querySelector<HTMLAnchorElement>('.page-header-actions a')!;
    expect(button.textContent).toBe('Ajouter un équipement');
    expect(button.type).toBe('button');
    expect(button.tabIndex).toBe(0);
    expect(link.tabIndex).toBe(0);
    button.focus();
    expect(document.activeElement).toBe(button);
    button.click();
    expect(page.componentInstance.activations).toBe(1);
    expect(pageRoot.querySelectorAll('h1')).toHaveLength(1);
  });

  it('keeps text before actions in one structure for responsive reflow and reading order', () => {
    const page = TestBed.createComponent(TestPageComponent);
    page.detectChanges();
    const pageRoot: HTMLElement = page.nativeElement;
    const header = pageRoot.querySelector('header')!;
    expect(Array.from(header.children).map((child) => child.className)).toEqual([
      'page-header-text', 'page-header-actions'
    ]);
    expect(pageRoot.querySelectorAll('.page-header-actions button')).toHaveLength(1);
    expect(pageRoot.querySelector('.page-header-text h1 + p')).not.toBeNull();
  });
});
