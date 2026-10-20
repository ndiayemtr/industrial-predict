import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { Title } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule } from '@nebular/theme';
import { routes } from '../../app.routes';
import { SENSOR_ROUTES } from './sensors.routes';

describe('Sensors lazy routing in the Shell', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({ providers: [provideRouter(routes), provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations(),
      importProvidersFrom(NbThemeModule.forRoot({ name: 'industrial-predict' },
        [{ name: 'industrial-predict', base: 'default', variables: {} }]), NbSidebarModule.forRoot())] });
  });
  afterEach(() => { try { TestBed.inject(HttpTestingController).verify(); } finally { TestBed.resetTestingModule(); vi.restoreAllMocks(); } });
  it('declares only the full-match lazy list, with no detail or write route', () => {
    expect(SENSOR_ROUTES.map(route => route.path)).toEqual(['']);
    expect(SENSOR_ROUTES[0].pathMatch).toBe('full'); expect(SENSOR_ROUTES[0].component).toBeUndefined();
    expect(typeof SENSOR_ROUTES[0].loadComponent).toBe('function');
    expect(typeof routes[0].children?.find(route => route.path === 'sensors')?.loadChildren).toBe('function');
  });
  it('replaces the placeholder and keeps the Shell, title and active Sidebar destination', async () => {
    const h = await RouterTestingHarness.create('/sensors'); h.fixture.detectChanges(); TestBed.tick(); await h.fixture.whenStable(); h.fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne(req => req.url === '/api/v1/companies').flush({ items: [], total: 0, page: 1, page_size: 50, pages: 0 });
    h.fixture.detectChanges();
    expect(h.routeNativeElement!.querySelector('app-sensors-list')).not.toBeNull();
    expect(h.routeNativeElement!.querySelector('app-feature-placeholder')).toBeNull();
    expect(h.routeNativeElement!.querySelector('h1')?.textContent).toBe('Capteurs');
    expect(h.routeNativeElement!.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/sensors');
    expect(TestBed.inject(Title).getTitle()).toBe('Capteurs | Industrial Predict AI'); http.expectNone(() => true);
  });
  it('leaves future detail and create paths to the global 404 without loading Sensors', async () => {
    const h = await RouterTestingHarness.create('/sensors/17');
    h.fixture.detectChanges(); await h.fixture.whenStable();
    expect(h.routeNativeElement!.querySelector('app-sensors-list')).toBeNull();
    expect(TestBed.inject(Title).getTitle()).toBe('Page introuvable | Industrial Predict AI');
    TestBed.inject(HttpTestingController).expectNone(() => true);
  });
});
