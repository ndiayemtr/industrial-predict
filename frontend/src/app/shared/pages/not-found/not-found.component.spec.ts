import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { Title } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router, RouterOutlet } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule } from '@nebular/theme';
import { vi } from 'vitest';
import { routes } from '../../../app.routes';
import { provideDashboardTesting } from '../../../features/dashboard/testing/dashboard-testing';
import { NotFoundComponent } from './not-found.component';

describe('Not-found routing inside the Shell', () => {
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

  async function open(url: string) {
    const harness = await RouterTestingHarness.create(url);
    harness.fixture.detectChanges();
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
    return harness;
  }

  it.each(['/inconnu', '/reports', '/administration', '/equipments/42/inconnu'])
    ('keeps %s and displays the 404 with consistent titles and no active navigation', async (url) => {
      const harness = await open(url);
      const shell = harness.routeDebugElement!;
      const root = harness.routeNativeElement!;
      expect(TestBed.inject(Router).url).toBe(url);
      expect(root.tagName).toBe('APP-SHELL');
      expect(shell.query(By.directive(RouterOutlet)).injector.get(RouterOutlet).component).toBeInstanceOf(NotFoundComponent);
      expect(root.querySelectorAll('nb-sidebar')).toHaveLength(1);
      expect(root.querySelectorAll('nb-layout-header')).toHaveLength(1);
      expect(root.querySelectorAll('app-sidebar nav a')).toHaveLength(9);
      expect(root.querySelector('main .error-code')?.textContent).toBe('404');
      expect(root.querySelector('main h1')?.textContent).toBe('Page introuvable');
      expect(root.querySelector('app-header .header-title')?.textContent).toBe('Page introuvable');
      expect(TestBed.inject(Title).getTitle()).toBe('Page introuvable | Industrial Predict AI');
      expect(root.querySelector('app-sidebar .is-active, app-sidebar [aria-current]')).toBeNull();
      expect(root.querySelector('app-feature-placeholder')).toBeNull();
      expect(root.querySelector('main section')?.getAttribute('aria-labelledby')).toBe('not-found-title');
      const link = root.querySelector<HTMLAnchorElement>('main .dashboard-link')!;
      expect(link.textContent).toBe('Retour au Dashboard');
      expect(link.getAttribute('href')).toBe('/dashboard');
      expect(link.tabIndex).toBe(0);
    });

  it('returns to Dashboard through RouterLink without replacing the Shell', async () => {
    const harness = await open('/inconnu?source=test#section');
    const shell = harness.routeDebugElement!.componentInstance;
    expect(TestBed.inject(Router).url).toBe('/inconnu?source=test#section');
    harness.routeNativeElement!.querySelector<HTMLAnchorElement>('.dashboard-link')!.click();
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
    expect(TestBed.inject(Router).url).toBe('/dashboard');
    expect(harness.routeDebugElement!.componentInstance).toBe(shell);
    expect(harness.routeNativeElement!.querySelector('main h1')?.textContent).toBe('Dashboard');
    expect(harness.routeNativeElement!.querySelector('app-sidebar a[aria-current="true"]')?.textContent?.trim()).toBe('Dashboard');
  });

  it('clears and restores Equipment selection when moving between valid details and a 404', async () => {
    const harness = await open('/equipments/42');
    const active = () => harness.routeNativeElement!.querySelector('app-sidebar a.is-active');
    expect(active()?.getAttribute('href')).toBe('/equipments');
    await harness.navigateByUrl('/equipments/42/inconnu');
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
    expect(active()).toBeNull();
    expect(harness.routeNativeElement!.querySelector('app-sidebar [aria-current]')).toBeNull();
    await harness.navigateByUrl('/equipments/43?tab=sensors');
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
    expect(active()?.getAttribute('href')).toBe('/equipments');
    expect(active()?.getAttribute('aria-current')).toBe('true');
    expect(harness.routeNativeElement!.querySelector('app-header .header-title')?.textContent).toBe('Détail équipement');
  });
});
