import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule } from '@nebular/theme';
import { vi } from 'vitest';
import { routes } from '../../app.routes';
import { provideDashboardTesting } from '../../features/dashboard/testing/dashboard-testing';

describe('Shell responsive navigation', () => {
  let width: number;

  beforeEach(() => {
    width = 1024;
    vi.spyOn(window, 'innerWidth', 'get').mockImplementation(() => width);
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

  afterEach(() => {
    TestBed.resetTestingModule();
    vi.restoreAllMocks();
  });

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

  const sidebar = (h: RouterTestingHarness) => h.routeNativeElement!.querySelector<HTMLElement>('nb-sidebar')!;
  const toggle = (h: RouterTestingHarness) => h.routeNativeElement!.querySelector<HTMLButtonElement>('.sidebar-toggle')!;

  async function resize(h: RouterTestingHarness, nextWidth: number) {
    width = nextWidth;
    window.dispatchEvent(new Event('resize'));
    await settle(h);
  }

  async function expand(h: RouterTestingHarness) {
    toggle(h).click();
    await settle(h);
  }

  it.each([1440, 1024, 1023, 768, 390, 320])
    ('initializes the correct mode at %i px, with 1024 included in desktop', async (initialWidth) => {
      width = initialWidth;
      const h = await open();
      const mobile = width < 1024;
      expect(h.routeNativeElement!.querySelector('.shell-mobile') !== null).toBe(mobile);
      expect(sidebar(h).classList.contains(mobile ? 'collapsed' : 'expanded')).toBe(true);
      expect(toggle(h).getAttribute('aria-expanded')).toBe(String(!mobile));
      expect(toggle(h).getAttribute('aria-controls')).toBe(sidebar(h).id);
      expect(sidebar(h).hasAttribute('inert')).toBe(mobile);
      expect(sidebar(h).getAttribute('aria-hidden')).toBe(mobile ? 'true' : null);
      expect(h.routeNativeElement!.querySelector('.sidebar-backdrop')).toBeNull();
    });

  it('opens a mobile dialog, hides the background and focuses its accessible close control', async () => {
    width = 390;
    const h = await open();
    await expand(h);
    expect(toggle(h).getAttribute('aria-expanded')).toBe('true');
    expect(sidebar(h).getAttribute('role')).toBe('dialog');
    expect(sidebar(h).getAttribute('aria-modal')).toBe('true');
    expect(sidebar(h).hasAttribute('inert')).toBe(false);
    expect(h.routeNativeElement!.querySelector('nb-layout-column')?.hasAttribute('inert')).toBe(true);
    expect(h.routeNativeElement!.querySelector('nb-layout-header')?.hasAttribute('inert')).toBe(true);
    expect(document.activeElement).toBe(h.routeNativeElement!.querySelector('.drawer-close'));
    expect(h.routeNativeElement!.querySelector('.sidebar-backdrop')).not.toBeNull();
  });

  it.each(['escape', 'close-button', 'backdrop'])
    ('closes via %s and restores focus without navigating', async (action) => {
      width = 390;
      const h = await open();
      await expand(h);
      const root = h.routeNativeElement!;
      if (action === 'escape') {
        root.querySelector('.drawer-close')!.dispatchEvent(new KeyboardEvent('keydown', {
          key: 'Escape', bubbles: true, cancelable: true
        }));
      } else {
        root.querySelector<HTMLButtonElement>(action === 'backdrop' ? '.sidebar-backdrop' : '.drawer-close')!.click();
      }
      await settle(h);
      expect(sidebar(h).classList.contains('collapsed')).toBe(true);
      expect(toggle(h).getAttribute('aria-expanded')).toBe('false');
      expect(sidebar(h).hasAttribute('inert')).toBe(true);
      expect(root.querySelector('.sidebar-backdrop')).toBeNull();
      expect(root.querySelector('nb-layout-column')?.hasAttribute('inert')).toBe(false);
      expect(document.activeElement).toBe(toggle(h));
      expect(TestBed.inject(Router).url).toBe('/dashboard');
    });

  it('crosses the boundary both ways without leaving a backdrop or a hidden focus target', async () => {
    const h = await open();
    h.routeNativeElement!.querySelector<HTMLAnchorElement>('app-sidebar a')!.focus();
    await resize(h, 1023);
    expect(toggle(h).getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(toggle(h));
    await expand(h);
    await resize(h, 1024);
    expect(toggle(h).getAttribute('aria-expanded')).toBe('true');
    expect(sidebar(h).getAttribute('role')).toBe('complementary');
    expect(sidebar(h).getAttribute('aria-modal')).toBeNull();
    expect(h.routeNativeElement!.querySelector('.sidebar-backdrop')).toBeNull();
    expect(h.routeNativeElement!.querySelector('nb-layout-column')?.hasAttribute('inert')).toBe(false);
    expect(document.activeElement).toBe(toggle(h));
    await resize(h, 320);
    expect(toggle(h).getAttribute('aria-expanded')).toBe('false');
  });

  it('preserves a manual desktop collapse and an open mobile drawer within the same mode', async () => {
    const h = await open();
    toggle(h).click();
    await settle(h);
    await resize(h, 1440);
    expect(toggle(h).getAttribute('aria-expanded')).toBe('false');
    await resize(h, 390);
    await expand(h);
    await resize(h, 768);
    expect(toggle(h).getAttribute('aria-expanded')).toBe('true');
  });

  it.each(['/equipments', '/equipments/42', '/predictions', '/inconnu'])
    ('closes after navigation to %s and retains the main focus policy', async (url) => {
      width = 390;
      const h = await open();
      await expand(h);
      await h.navigateByUrl(url);
      await settle(h);
      expect(toggle(h).getAttribute('aria-expanded')).toBe('false');
      expect(document.activeElement).toBe(h.routeNativeElement!.querySelector('main'));
      expect(h.routeNativeElement!.querySelector('main h1')).not.toBeNull();
      expect(TestBed.inject(Router).url).toBe(url);
    });

  it('keeps an open drawer after a cancelled navigation', async () => {
    width = 390;
    const h = await open();
    const router = TestBed.inject(Router);
    router.resetConfig([{ ...routes[0], children: [
      { path: 'blocked', canActivate: [() => false], children: [] }, ...routes[0].children!
    ] }]);
    await expand(h);
    expect(await router.navigateByUrl('/blocked')).toBe(false);
    await settle(h);
    expect(toggle(h).getAttribute('aria-expanded')).toBe('true');
  });

  it('preserves the skip link URL including query and fragment on mobile', async () => {
    width = 320;
    const url = '/equipments/42?tab=sensors#feature-title';
    const h = await open(url);
    const link = h.routeNativeElement!.querySelector<HTMLAnchorElement>('.skip-link')!;
    link.focus();
    link.click();
    await settle(h);
    expect(link.getAttribute('href')).toBe(url);
    expect(TestBed.inject(Router).url).toBe(url);
    expect(document.activeElement).toBe(h.routeNativeElement!.querySelector('main'));
  });

  it('closes for a fragment destination without focusing a now-hidden menu link', async () => {
    width = 390;
    const h = await open();
    await expand(h);
    h.routeNativeElement!.querySelector<HTMLAnchorElement>('app-sidebar a')!.focus();
    await h.navigateByUrl('/equipments/42#feature-title');
    await settle(h);
    expect(toggle(h).getAttribute('aria-expanded')).toBe('false');
    expect(document.activeElement).toBe(toggle(h));
  });

  it('removes the viewport listener when the Shell is destroyed', async () => {
    const h = await open();
    const shell = h.routeDebugElement!.componentInstance;
    h.fixture.destroy();
    width = 390;
    window.dispatchEvent(new Event('resize'));
    expect(shell.mobile()).toBe(false);
  });
});
