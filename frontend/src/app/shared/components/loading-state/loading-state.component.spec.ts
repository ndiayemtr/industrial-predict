import { ComponentFixture, TestBed } from '@angular/core/testing';
import { LoadingStateComponent } from './loading-state.component';

describe('LoadingStateComponent', () => {
  let fixture: ComponentFixture<LoadingStateComponent>;
  let root: HTMLElement;

  beforeEach(() => {
    // No HTTP, Router, Nebular or business providers are required.
    TestBed.configureTestingModule({ imports: [LoadingStateComponent] });
    fixture = TestBed.createComponent(LoadingStateComponent);
    fixture.detectChanges();
    root = fixture.nativeElement;
  });

  it('renders the default message without requiring any input or business service', () => {
    expect(root.querySelector('.loading-message')?.textContent).toBe('Chargement des données…');
    expect(root.querySelector('button, a, input, nb-spinner')).toBeNull();
  });

  it('renders a custom message and updates it when the input changes', () => {
    fixture.componentRef.setInput('message', 'Chargement des équipements…');
    fixture.detectChanges();
    expect(root.querySelector('.loading-message')?.textContent).toBe('Chargement des équipements…');
    fixture.componentRef.setInput('message', 'Chargement des capteurs…');
    fixture.detectChanges();
    expect(root.querySelector('.loading-message')?.textContent).toBe('Chargement des capteurs…');
  });

  it.each(['', '   '])('keeps a meaningful announcement for an empty message (%j)', (message) => {
    fixture.componentRef.setInput('message', message);
    fixture.detectChanges();
    expect(root.querySelector('.loading-message')?.textContent).toBe('Chargement des données…');
  });

  it('exposes one polite status region with one readable announcement', () => {
    const status = root.querySelector('[role="status"]')!;
    expect(root.querySelectorAll('[role="status"]')).toHaveLength(1);
    expect(status.getAttribute('aria-atomic')).toBe('true');
    expect(status.textContent?.trim()).toBe('Chargement des données…');
    // role=status already implies aria-live=polite; avoid a second live region.
    expect(root.querySelector('[role="alert"], [aria-live], [tabindex]')).toBeNull();
    expect(status.hasAttribute('aria-hidden')).toBe(false);
  });

  it('provides a decorative visual indicator without duplicating the announcement', () => {
    const indicator = root.querySelector('.loading-indicator')!;
    expect(indicator.getAttribute('aria-hidden')).toBe('true');
    expect(indicator.textContent).toBe('');
    expect(root.querySelectorAll('.loading-message')).toHaveLength(1);
  });

  it('does not rewrite the status when change detection runs with an unchanged message', async () => {
    const status = root.querySelector('[role="status"]')!;
    const changes: MutationRecord[] = [];
    const observer = new MutationObserver((records) => changes.push(...records));
    observer.observe(status, { childList: true, characterData: true, subtree: true });
    try {
      fixture.detectChanges();
      fixture.detectChanges();
      await Promise.resolve();
      expect(changes).toHaveLength(0);
    } finally {
      observer.disconnect();
    }
  });

  it('includes a reduced-motion rule that disables only the indicator animation', () => {
    // jsdom does not run animations or evaluate user media preferences.
    // Verify the actual component CSS emitted by the Angular test builder.
    const styles = Array.from(document.querySelectorAll('style')).map((style) => style.textContent).join('\n');
    expect(styles).toMatch(
      /@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{\s*\.loading-indicator[^\{]*\{[^}]*animation:\s*none/
    );
    expect(root.querySelector('[role="status"]')?.textContent?.trim()).toBe('Chargement des données…');
  });

  it('renders the message as text without interpreting HTML', () => {
    fixture.componentRef.setInput('message', '<strong>Chargement…</strong>');
    fixture.detectChanges();
    expect(root.querySelector('.loading-message')?.textContent).toBe('<strong>Chargement…</strong>');
    expect(root.querySelector('strong')).toBeNull();
  });
});
