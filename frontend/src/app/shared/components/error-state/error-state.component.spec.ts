import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { ErrorStateComponent } from './error-state.component';

describe('ErrorStateComponent', () => {
  let fixture: ComponentFixture<ErrorStateComponent>;
  let root: HTMLElement;

  beforeEach(() => {
    // No HTTP, Router, Nebular or business providers are required.
    TestBed.configureTestingModule({ imports: [ErrorStateComponent] });
    fixture = TestBed.createComponent(ErrorStateComponent);
    fixture.componentRef.setInput('title', 'Chargement impossible');
    fixture.componentRef.setInput('message', 'Les données ne peuvent pas être affichées actuellement.');
    fixture.detectChanges();
    root = fixture.nativeElement;
  });

  it.each(['title', 'message'])('requires the %s input before rendering', (missing) => {
    const incomplete = TestBed.createComponent(ErrorStateComponent);
    if (missing !== 'title') incomplete.componentRef.setInput('title', 'Chargement impossible');
    if (missing !== 'message') incomplete.componentRef.setInput('message', 'Veuillez réessayer.');
    expect(() => incomplete.detectChanges()).toThrowError(/NG0950/);
  });

  it('renders the supplied title as an h2 and the message without another h1', () => {
    expect(root.querySelectorAll('h2')).toHaveLength(1);
    expect(root.querySelector('h2')?.textContent).toBe('Chargement impossible');
    expect(root.querySelector('p')?.textContent).toBe('Les données ne peuvent pas être affichées actuellement.');
    expect(root.querySelector('h1')).toBeNull();
  });

  it('hides the retry button by default and when retryable is explicitly false', () => {
    expect(fixture.componentInstance.retryable()).toBe(false);
    expect(root.querySelector('button')).toBeNull();
    fixture.componentRef.setInput('retryable', false);
    fixture.detectChanges();
    expect(root.querySelector('button')).toBeNull();
  });

  it('shows a native labelled button only while retryable is true', () => {
    fixture.componentRef.setInput('retryable', true);
    fixture.detectChanges();
    const button = root.querySelector<HTMLButtonElement>('button')!;
    expect(button.textContent).toBe('Réessayer');
    expect(button.type).toBe('button');
    expect(button.tabIndex).toBe(0);
    expect(button.disabled).toBe(false);
    button.focus();
    expect(document.activeElement).toBe(button);
    fixture.componentRef.setInput('retryable', false);
    fixture.detectChanges();
    expect(root.querySelector('button')).toBeNull();
  });

  it('emits one void retry event per click without performing the retry itself', () => {
    const listener = vi.fn();
    fixture.componentInstance.retry.subscribe(listener);
    fixture.componentRef.setInput('retryable', true);
    fixture.detectChanges();
    root.querySelector<HTMLButtonElement>('button')!.click();
    expect(listener).toHaveBeenCalledTimes(1);
    expect(listener).toHaveBeenCalledWith(undefined);
    expect(root.querySelector('p')?.textContent).toBe('Les données ne peuvent pas être affichées actuellement.');
    expect(root.querySelector('button')).not.toBeNull();
  });

  it.each(['Enter', ' '])('does not double-emit during native keyboard activation (%j)', (key) => {
    const listener = vi.fn();
    fixture.componentInstance.retry.subscribe(listener);
    fixture.componentRef.setInput('retryable', true);
    fixture.detectChanges();
    const button = root.querySelector<HTMLButtonElement>('button')!;
    button.focus();
    button.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true }));
    button.dispatchEvent(new KeyboardEvent('keyup', { key, bubbles: true }));
    expect(listener).not.toHaveBeenCalled();
    // jsdom does not synthesize the browser's native click for Enter/Space.
    // Supply that click; no additional key handler may duplicate the event.
    button.click();
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it('never emits automatically on rendering, input changes or change detection', () => {
    const listener = vi.fn();
    fixture.componentInstance.retry.subscribe(listener);
    fixture.componentRef.setInput('message', 'Le service est temporairement indisponible.');
    fixture.componentRef.setInput('retryable', true);
    fixture.detectChanges();
    fixture.detectChanges();
    fixture.componentRef.setInput('retryable', false);
    fixture.detectChanges();
    expect(listener).not.toHaveBeenCalled();
    expect(root.querySelector('p')?.textContent).toBe('Le service est temporairement indisponible.');
  });

  it('announces the error in one alert while keeping the action outside the live region', () => {
    fixture.componentRef.setInput('retryable', true);
    fixture.detectChanges();
    const alert = root.querySelector('[role="alert"]')!;
    expect(root.querySelectorAll('[role="alert"]')).toHaveLength(1);
    expect(alert.getAttribute('aria-atomic')).toBe('true');
    expect(alert.querySelectorAll('h2, p')).toHaveLength(2);
    expect(alert.querySelector('button')).toBeNull();
    expect(root.querySelector('[aria-live], [role="status"]')).toBeNull();
    expect(alert.hasAttribute('aria-hidden')).toBe(false);
  });

  it('does not rewrite the announcement during unchanged rendering or retry visibility changes', async () => {
    const alert = root.querySelector('[role="alert"]')!;
    const changes: MutationRecord[] = [];
    const observer = new MutationObserver((records) => changes.push(...records));
    observer.observe(alert, { childList: true, characterData: true, subtree: true });
    try {
      fixture.detectChanges();
      fixture.componentRef.setInput('retryable', true);
      fixture.detectChanges();
      await Promise.resolve();
      expect(changes).toHaveLength(0);
    } finally {
      observer.disconnect();
    }
  });

  it('renders supplied text without interpreting HTML', () => {
    fixture.componentRef.setInput('title', '<em>Erreur</em>');
    fixture.componentRef.setInput('message', '<strong>Indisponible</strong>');
    fixture.detectChanges();
    expect(root.querySelector('h2')?.textContent).toBe('<em>Erreur</em>');
    expect(root.querySelector('p')?.textContent).toBe('<strong>Indisponible</strong>');
    expect(root.querySelector('em, strong')).toBeNull();
  });
});
