import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { HttpTestingController } from '@angular/common/http/testing';
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

  it('defers all Companies pages with the static creation route before the identifier', () => {
    const parent = routes[0].children!.find(route => route.path === 'companies')!;
    expect(typeof parent.loadChildren).toBe('function');
    expect(parent.loadComponent).toBeUndefined();
    expect(COMPANY_ROUTES).toHaveLength(3);
    expect(COMPANY_ROUTES[0].path).toBe('');
    expect(COMPANY_ROUTES[0].pathMatch).toBe('full');
    expect(typeof COMPANY_ROUTES[0].loadComponent).toBe('function');
    expect(COMPANY_ROUTES[0].component).toBeUndefined();
    expect(COMPANY_ROUTES[1].path).toBe('new');
    expect(COMPANY_ROUTES[1].canDeactivate).toHaveLength(1);
    expect(COMPANY_ROUTES[2].path).toBe(':companyId');
    expect(typeof COMPANY_ROUTES[1].loadComponent).toBe('function');
    expect(COMPANY_ROUTES[1].component).toBeUndefined();
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

  it('opens creation in the Shell with correct titles and no initial detail or write request', async () => {
    const harness = await open('/companies/new?page=2&search=Test');
    const root = harness.routeNativeElement!;
    expect(root.querySelector('app-company-form-page')).not.toBeNull();
    expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('app-header .header-title')?.textContent).toBe('Nouvelle entreprise');
    expect(TestBed.inject(Title).getTitle()).toBe('Nouvelle entreprise | Industrial Predict AI');
    expect(root.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/companies');
    TestBed.inject(HttpTestingController).expectNone(() => true);
  });

  it('keeps detail in the Shell with Companies active, route titles and accessible main focus', async () => {
    const harness = await open('/companies');
    await harness.navigateByUrl('/companies/7?page=2&search=Test');
    harness.fixture.detectChanges();
    TestBed.tick();
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
    const root = harness.routeNativeElement!;
    TestBed.inject(HttpTestingController).expectOne('/api/v1/companies/7').flush({ id: 7,
      name: 'Test', code: 'TEST', description: null, created_at: '2026-10-01T12:00:00', updated_at: '2026-10-01T12:00:00' });
    harness.fixture.detectChanges();
    expect(root.querySelector('app-company-detail')).not.toBeNull();
    expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('app-header .header-title')?.textContent).toBe('Détail entreprise');
    expect(TestBed.inject(Title).getTitle()).toBe('Détail entreprise | Industrial Predict AI');
    expect(root.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/companies');
    expect(document.activeElement).toBe(root.querySelector('main#main-content'));
    TestBed.inject(HttpTestingController).verify();
  });

  it.each(['/companies/7/edit', '/companies/inconnu/deep'])
    ('keeps %s on the global 404 without misleading active selection', async url => {
      const harness = await open(url);
      expect(TestBed.inject(Router).url).toBe(url);
      expect(harness.routeNativeElement!.querySelector('main h1')?.textContent).toBe('Page introuvable');
      expect(harness.routeNativeElement!.querySelector('app-sidebar a.is-active')).toBeNull();
    });
});
