import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { Title } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule, NbToastrService } from '@nebular/theme';
import { routes } from '../../app.routes';
import { SENSOR_ROUTES } from './sensors.routes';

describe('Sensors lazy routing in the Shell', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({ providers: [{ provide: NbToastrService, useValue: { success: vi.fn() } }, provideRouter(routes), provideHttpClient(), provideHttpClientTesting(), provideNoopAnimations(),
      importProvidersFrom(NbThemeModule.forRoot({ name: 'industrial-predict' },
        [{ name: 'industrial-predict', base: 'default', variables: {} }]), NbSidebarModule.forRoot())] });
  });
  afterEach(() => { try { TestBed.inject(HttpTestingController).verify(); } finally { TestBed.resetTestingModule(); vi.restoreAllMocks(); } });
  it('orders lazy creation and guarded edit before detail', () => {
    expect(SENSOR_ROUTES.map(route => route.path)).toEqual(['', 'new', ':sensorId/edit', ':sensorId']);
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
  it.each(['/sensors/17/edit/extra'])('leaves future write path %s to the global 404 without loading Sensors', async url => {
    const h = await RouterTestingHarness.create(url);
    h.fixture.detectChanges(); await h.fixture.whenStable();
    expect(h.routeNativeElement!.querySelector('app-sensors-list')).toBeNull();
    expect(h.routeNativeElement!.querySelector('app-sensor-detail')).toBeNull();
    expect(TestBed.inject(Title).getTitle()).toBe('Page introuvable | Industrial Predict AI');
    TestBed.inject(HttpTestingController).expectNone(() => true);
  });
  it('opens the lazy detail in the Shell with a dedicated title', async () => {
    const h = await RouterTestingHarness.create('/sensors/17'); h.fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/sensors/17').flush({}, { status: 404, statusText: 'Not found' });
    h.fixture.detectChanges();
    expect(h.routeNativeElement!.querySelector('app-sensor-detail')).not.toBeNull();
    expect(h.routeNativeElement!.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/sensors');
    expect(TestBed.inject(Title).getTitle()).toBe('Détail capteur | Industrial Predict AI');
    http.expectNone(() => true);
  });

  it('loads the lazy creation before parameterized detail without a Sensor GET', async () => {
    const h = await RouterTestingHarness.create('/sensors/new'); h.fixture.detectChanges(); TestBed.tick(); await h.fixture.whenStable(); h.fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne(req => req.url === '/api/v1/companies').flush({ items: [], total: 0, page: 1, page_size: 50, pages: 0 });
    expect(h.routeNativeElement!.querySelector('app-sensor-create')).not.toBeNull();
    expect(h.routeNativeElement!.querySelector('app-sensor-detail')).toBeNull();
    expect(TestBed.inject(Title).getTitle()).toBe('Nouveau capteur industriel | Industrial Predict AI'); http.expectNone(() => true);
  });

  it('opens the guarded lazy edit with its Shell title and active Sidebar', async () => {
    const h = await RouterTestingHarness.create('/sensors/17/edit'); h.fixture.detectChanges();
    const http = TestBed.inject(HttpTestingController);
    http.expectOne('/api/v1/sensors/17').flush({}, { status: 404, statusText: 'Not found' });
    h.fixture.detectChanges();
    expect(h.routeNativeElement!.querySelector('app-sensor-edit')).not.toBeNull();
    expect(TestBed.inject(Title).getTitle()).toBe('Modifier le capteur | Industrial Predict AI');
    expect(h.routeNativeElement!.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/sensors');
    expect(SENSOR_ROUTES[2].canDeactivate).toHaveLength(1);
  });

});
