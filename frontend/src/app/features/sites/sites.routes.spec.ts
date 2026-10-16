import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Title } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule } from '@nebular/theme';
import { routes } from '../../app.routes';
import { provideDashboardTesting } from '../dashboard/testing/dashboard-testing';
import { SITE_ROUTES } from './sites.routes';

describe('Sites deferred list in the Shell', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({ providers: [provideRouter(routes), provideNoopAnimations(),
      ...provideDashboardTesting(), importProvidersFrom(
        NbThemeModule.forRoot({ name: 'industrial-predict' }, [{ name: 'industrial-predict', base: 'default', variables: {} }]),
        NbSidebarModule.forRoot())] });
  });
  afterEach(() => vi.restoreAllMocks());
  async function settle(harness: RouterTestingHarness) {
    harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges();
  }
  it('defers only the available list and declares no future detail or write routes', () => {
    expect(typeof routes[0].children!.find(route => route.path === 'sites')?.loadChildren).toBe('function');
    expect(SITE_ROUTES).toHaveLength(1); expect(SITE_ROUTES[0].pathMatch).toBe('full');
    expect(typeof SITE_ROUTES[0].loadComponent).toBe('function');
  });
  it('retains Sidebar selection, nine links, titles and accessible main focus', async () => {
    const harness = await RouterTestingHarness.create('/dashboard'); await settle(harness);
    await harness.navigateByUrl('/sites'); await settle(harness);
    const root = harness.routeNativeElement!;
    expect(root.querySelector('app-sites-list')).not.toBeNull(); expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/sites');
    expect(root.querySelectorAll('app-sidebar a[href]')).toHaveLength(9);
    expect(root.querySelector('app-header .header-title')?.textContent).toBe('Sites industriels');
    expect(TestBed.inject(Title).getTitle()).toBe('Sites industriels | Industrial Predict AI');
    expect(document.activeElement).toBe(root.querySelector('main'));
  });
  it('keeps a future detail URL on the global 404 until it is implemented', async () => {
    const harness = await RouterTestingHarness.create('/sites/3'); await settle(harness);
    expect(harness.routeNativeElement!.querySelector('app-not-found')).not.toBeNull();
    expect(harness.routeNativeElement!.querySelector('app-sites-list')).toBeNull();
  });
});
