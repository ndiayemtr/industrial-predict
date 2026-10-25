import { Component, ElementRef, Type, importProvidersFrom, viewChild } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { NavigationStart, provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule } from '@nebular/theme';
import { vi } from 'vitest';
import { routes } from '../../app.routes';
import { provideDashboardTesting } from '../../features/dashboard/testing/dashboard-testing';

@Component({ standalone: true, template: '<input #field aria-label="Focus owned by page" />' })
class FocusClaimingPage {
  private readonly field = viewChild.required<ElementRef<HTMLInputElement>>('field');
  ngAfterViewInit(): void { this.field().nativeElement.focus(); }
}

describe('Shell navigation focus', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({ providers: [
      provideRouter(routes), provideNoopAnimations(),
      ...provideDashboardTesting(),
      importProvidersFrom(
        NbThemeModule.forRoot({ name: 'industrial-predict' },
          [{ name: 'industrial-predict', base: 'default', variables: {} }]),
        NbSidebarModule.forRoot()
      )
    ] });
  });
  afterEach(() => vi.restoreAllMocks());

  async function settle(harness: RouterTestingHarness) {
    harness.fixture.detectChanges();
    TestBed.tick();
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
  }

  async function open(url = '/dashboard') {
    const harness = await RouterTestingHarness.create(url);
    await settle(harness);
    return harness;
  }

  it.each(['/dashboard', '/equipments', '/equipments/42', '/predictions', '/inconnu'])
    ('skip link focuses main on %s without navigation or URL changes', async (path) => {
      const url = `${path}?source=test#existing-fragment`;
      const harness = await open(url);
      const root = harness.routeNativeElement!;
      const main = root.querySelector<HTMLElement>('#main-content')!;
      const link = root.querySelector<HTMLAnchorElement>('.skip-link')!;
      const router = TestBed.inject(Router);
      const navigationStarted = vi.fn();
      const subscription = router.events.subscribe((event) => {
        if (event instanceof NavigationStart) navigationStarted();
      });
      link.focus();
      const click = new MouseEvent('click', { bubbles: true, cancelable: true });
      link.dispatchEvent(click);
      await settle(harness);
      expect(click.defaultPrevented).toBe(true);
      expect(document.activeElement).toBe(main);
      expect(main.getAttribute('tabindex')).toBe('-1');
      expect(link.getAttribute('aria-controls')).toBe(main.id);
      expect(link.getAttribute('href')).toBe(url);
      expect(router.url).toBe(url);
      expect(navigationStarted).not.toHaveBeenCalled();
      subscription.unsubscribe();
    });

  it.each(['/equipments', '/equipments/42', '/predictions', '/inconnu', '/dashboard'])
    ('focuses the rendered main after a page change to %s', async (url) => {
      const harness = await open(url === '/dashboard' ? '/equipments' : '/dashboard');
      harness.routeNativeElement!.querySelector<HTMLButtonElement>('.sidebar-toggle')!.focus();
      await harness.navigateByUrl(url);
      await settle(harness);
      expect(document.activeElement).toBe(harness.routeNativeElement!.querySelector('main'));
      expect(harness.routeNativeElement!.querySelector('main h1')).not.toBeNull();
      expect(TestBed.inject(Router).url).toBe(url);
    });

  it('keeps focus during initial loading, query-only changes and fragment destinations', async () => {
    const harness = await open('/dashboard');
    expect(document.activeElement).not.toBe(harness.routeNativeElement!.querySelector('main'));
    const button = harness.routeNativeElement!.querySelector<HTMLButtonElement>('.sidebar-toggle')!;
    button.focus();
    await harness.navigateByUrl('/dashboard?filter=active');
    await settle(harness);
    expect(document.activeElement).toBe(button);
    await harness.navigateByUrl('/equipments/42?tab=sensors#feature-title');
    await settle(harness);
    expect(document.activeElement).toBe(button);
    expect(TestBed.inject(Router).url).toBe('/equipments/42?tab=sensors#feature-title');
  });

  it('respects focus explicitly claimed by a newly activated page', async () => {
    const router = TestBed.inject(Router);
    router.resetConfig([{ ...routes[0], children: [
      ...routes[0].children!.slice(0, -1),
      { path: 'focus-test', component: FocusClaimingPage }, routes[0].children!.at(-1)!
    ] }]);
    const harness = await open();
    await harness.navigateByUrl('/focus-test');
    await settle(harness);
    expect(document.activeElement).toBe(harness.routeNativeElement!.querySelector('input'));
  });

  it('does not steal focus after an interaction during deferred loading', async () => {
    const router = TestBed.inject(Router);
    let resolvePage!: (component: Type<unknown>) => void;
    let loadingStarted!: () => void;
    const started = new Promise<void>((resolve) => { loadingStarted = resolve; });
    const deferredPage = new Promise<Type<unknown>>((resolve) => { resolvePage = resolve; });
    router.resetConfig([{ ...routes[0], children: [
      ...routes[0].children!.slice(0, -1),
      { path: 'slow-test', loadComponent: () => { loadingStarted(); return deferredPage; } },
      routes[0].children!.at(-1)!
    ] }]);
    const harness = await open();
    const button = harness.routeNativeElement!.querySelector<HTMLButtonElement>('.sidebar-toggle')!;
    button.focus();
    const navigation = router.navigateByUrl('/slow-test');
    await started;
    button.dispatchEvent(new Event('pointerdown', { bubbles: true }));
    // Use a page that makes no focus claim, so the interaction guard is exercised.
    const page = await import('../../shared/pages/feature-placeholder/feature-placeholder.component');
    resolvePage(page.FeaturePlaceholderComponent);
    await navigation;
    await settle(harness);
    expect(document.activeElement).toBe(button);
  });

  it('preserves focus owned by a view outside the Shell, such as a dialog', async () => {
    const harness = await open();
    const externalView = TestBed.createComponent(FocusClaimingPage);
    externalView.detectChanges();
    const field = externalView.nativeElement.querySelector('input');
    expect(document.activeElement).toBe(field);
    await harness.navigateByUrl('/equipments');
    await settle(harness);
    expect(document.activeElement).toBe(field);
    externalView.destroy();
  });
});
