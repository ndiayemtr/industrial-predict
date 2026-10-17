import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { Title } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { HttpTestingController } from '@angular/common/http/testing';
import { of } from 'rxjs';
import { NbSidebarModule, NbThemeModule, NbToastrService } from '@nebular/theme';
import { routes } from '../../app.routes';
import { provideDashboardTesting } from '../dashboard/testing/dashboard-testing';
import { SITE_ROUTES } from './sites.routes';
import { ReferenceDataApiService } from '../../core/api/reference-data-api.service';

describe('Sites deferred list in the Shell', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({ providers: [provideRouter(routes), provideNoopAnimations(), { provide: NbToastrService, useValue: { success: vi.fn() } },
      ...provideDashboardTesting(), { provide: ReferenceDataApiService, useValue: {
        getCompanies: () => of({ items: [], total: 0, page: 1, page_size: 50, pages: 0 }),
        getCompanyById: () => of({ id: 7, name: 'Entreprise test', code: 'C7' })
      } }, importProvidersFrom(
        NbThemeModule.forRoot({ name: 'industrial-predict' }, [{ name: 'industrial-predict', base: 'default', variables: {} }]),
        NbSidebarModule.forRoot())] });
  });
  afterEach(() => vi.restoreAllMocks());
  async function settle(harness: RouterTestingHarness) {
    harness.fixture.detectChanges(); TestBed.tick(); await harness.fixture.whenStable(); harness.fixture.detectChanges();
  }
  it('defers the list and guarded creation before the dynamic detail without editing or deletion routes', () => {
    expect(typeof routes[0].children!.find(route => route.path === 'sites')?.loadChildren).toBe('function');
    expect(SITE_ROUTES).toHaveLength(3); expect(SITE_ROUTES[0].path).toBe(''); expect(SITE_ROUTES[0].pathMatch).toBe('full');
    expect(SITE_ROUTES[1].path).toBe('new'); expect(SITE_ROUTES[1].canDeactivate).toHaveLength(1);
    expect(SITE_ROUTES[2].path).toBe(':siteId'); expect(typeof SITE_ROUTES[2].loadComponent).toBe('function');
    expect(typeof SITE_ROUTES[0].loadComponent).toBe('function');
  });

  it('opens creation in the Shell with active Sites, title, nine links and main focus without a site detail GET', async () => {
    const harness = await RouterTestingHarness.create('/sites'); await settle(harness);
    await harness.navigateByUrl('/sites/new'); await settle(harness);
    const root = harness.routeNativeElement!;
    expect(root.querySelectorAll('h1')).toHaveLength(1); expect(root.querySelector('app-site-create')).not.toBeNull();
    expect(root.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/sites');
    expect(root.querySelectorAll('app-sidebar a[href]')).toHaveLength(9);
    expect(TestBed.inject(Title).getTitle()).toBe('Nouveau site industriel | Industrial Predict AI');
    expect(document.activeElement).toBe(root.querySelector('main')); TestBed.inject(HttpTestingController).expectNone(() => true);
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
  it('keeps unknown nested URLs on the global 404', async () => {
    const harness = await RouterTestingHarness.create('/sites/3/unknown'); await settle(harness);
    expect(harness.routeNativeElement!.querySelector('app-not-found')).not.toBeNull();
    expect(harness.routeNativeElement!.querySelector('app-sites-list')).toBeNull();
  });

  it('retains Sidebar, document title and main focus on the site detail', async () => {
    const harness = await RouterTestingHarness.create('/sites'); await settle(harness);
    await harness.navigateByUrl('/sites/3');
    TestBed.inject(HttpTestingController).expectOne('/api/v1/sites/3').flush({ id: 3, company_id: 7,
      name: 'Site test', code: 'S3', description: null, created_at: '', updated_at: '' });
    await settle(harness);
    const root = harness.routeNativeElement!;
    expect(root.querySelector('app-site-detail')).not.toBeNull(); expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/sites');
    expect(root.querySelectorAll('app-sidebar a[href]')).toHaveLength(9);
    expect(root.querySelector('app-header .header-title')?.textContent).toBe('Détail du site');
    expect(TestBed.inject(Title).getTitle()).toBe('Détail du site | Industrial Predict AI');
    expect(document.activeElement).toBe(root.querySelector('main')); TestBed.inject(HttpTestingController).verify();
  });
});
