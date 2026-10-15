import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Title } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule } from '@nebular/theme';
import { routes } from '../../app.routes';
import { provideDashboardTesting } from '../dashboard/testing/dashboard-testing';
import { COMPANY_ROUTES } from './companies.routes';

describe('Companies deferred routing in the Shell', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({ providers: [provideRouter(routes), provideNoopAnimations(),
      ...provideDashboardTesting(), importProvidersFrom(
        NbThemeModule.forRoot({ name: 'industrial-predict' },
          [{ name: 'industrial-predict', base: 'default', variables: {} }]), NbSidebarModule.forRoot())] });
  });
  afterEach(() => vi.restoreAllMocks());

  async function open(url: string) {
    const harness = await RouterTestingHarness.create(url);
    harness.fixture.detectChanges();
    TestBed.tick();
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
    return harness;
  }

  it('defers both the feature routes and its list component without premature detail/create routes', () => {
    const parent = routes[0].children!.find(route => route.path === 'companies')!;
    expect(typeof parent.loadChildren).toBe('function');
    expect(parent.loadComponent).toBeUndefined();
    expect(COMPANY_ROUTES).toHaveLength(1);
    expect(COMPANY_ROUTES[0].path).toBe('');
    expect(COMPANY_ROUTES[0].pathMatch).toBe('full');
    expect(typeof COMPANY_ROUTES[0].loadComponent).toBe('function');
    expect(COMPANY_ROUTES[0].component).toBeUndefined();
  });

  it('retains the Shell, Sidebar selection and titles for the actual list page', async () => {
    const harness = await open('/companies');
    const root = harness.routeNativeElement!;
    expect(root.tagName).toBe('APP-SHELL');
    expect(root.querySelector('app-companies-list')).not.toBeNull();
    expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('app-header .header-title')?.textContent).toBe('Entreprises');
    expect(TestBed.inject(Title).getTitle()).toBe('Entreprises | Industrial Predict AI');
    expect(root.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/companies');
  });

  it.each(['/companies/7', '/companies/new', '/companies/inconnu/deep'])
    ('keeps %s on the global 404 without misleading active selection', async url => {
      const harness = await open(url);
      expect(TestBed.inject(Router).url).toBe(url);
      expect(harness.routeNativeElement!.querySelector('main h1')?.textContent).toBe('Page introuvable');
      expect(harness.routeNativeElement!.querySelector('app-sidebar a.is-active')).toBeNull();
    });
});
