import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { By, Title } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router, RouterOutlet, Routes } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule, NbToastrService } from '@nebular/theme';
import { vi } from 'vitest';
import { routes } from './app.routes';
import { provideDashboardTesting } from './features/dashboard/testing/dashboard-testing';
import { NAVIGATION_ITEMS } from './layout/navigation/navigation.config';
import { EQUIPMENT_ROUTES } from './features/equipments/equipments.routes';

const expectedPages = [
  ['/dashboard', 'Dashboard'], ['/companies', 'Entreprises'], ['/sites', 'Sites industriels'],
  ['/equipments', 'Équipements'], ['/sensors', 'Capteurs'], ['/measurements', 'Mesures'],
  ['/maintenance', 'Maintenance'], ['/predictions', 'Prédictions'], ['/recommendations', 'Recommandations']
] as const;
const children = routes[0].children!;

describe('Routing configuration invariants', () => {
  it('has unique navigation identifiers, labels, destinations and sibling route paths', () => {
    const ids = NAVIGATION_ITEMS.map((item) => item.id);
    const labels = NAVIGATION_ITEMS.map((item) => item.label);
    const paths = NAVIGATION_ITEMS.flatMap((item) => item.status === 'available' ? [item.path] : []);
    expect(new Set(ids).size).toBe(ids.length);
    expect(new Set(labels).size).toBe(labels.length);
    expect(new Set(paths).size).toBe(paths.length);
    function checkSiblings(config: Routes): void {
      const routePaths = config.map((route) => route.path);
      expect(new Set(routePaths).size).toBe(routePaths.length);
      for (const route of config) if (route.children) checkSiblings(route.children);
    }
    checkSiblings(routes);
  });

  it('maps exactly nine documented Sidebar destinations to routes and excludes disabled features', () => {
    expect(routes).toHaveLength(1);
    expect(routes[0].path).toBe('');
    const available = NAVIGATION_ITEMS.filter((item) => item.status === 'available');
    expect(available.map((item) => item.path)).toEqual(expectedPages.map(([path]) => path));
    const pageRoutes = children.filter((route) => route.path && !route.path.includes(':') && route.path !== '**');
    expect(pageRoutes.map((route) => `/${route.path}`)).toEqual(expectedPages.map(([path]) => path));
    for (const item of available) {
      const page = pageRoutes.find((route) => `/${route.path}` === item.path)!;
      expect(page.data?.['pageTitle']).toBe(item.label);
      expect(page.title).toBe(`${item.label} | Industrial Predict AI`);
    }
    const disabled = NAVIGATION_ITEMS.filter((item) => item.status === 'coming-soon');
    expect(disabled.map((item) => item.id)).toEqual(['reports', 'administration']);
    for (const item of disabled) {
      expect('path' in item).toBe(false);
      expect(children.some((route) => route.path === item.id || route.path?.startsWith(`${item.id}/`))).toBe(false);
    }
  });

  it('has a single full-match root redirect targeting Dashboard exactly', () => {
    const redirects = children.filter((route) => route.redirectTo !== undefined);
    expect(redirects).toHaveLength(1);
    expect(redirects[0].path).toBe('');
    expect(redirects[0].pathMatch).toBe('full');
    expect(redirects[0].redirectTo).toBe('dashboard');
  });

  it('places the unique wildcard last with the 404 metadata', () => {
    expect(children.filter((route) => route.path === '**')).toHaveLength(1);
    const wildcard = children.at(-1)!;
    expect(wildcard.path).toBe('**');
    expect(wildcard.redirectTo).toBeUndefined();
    expect(wildcard.data).toEqual({ pageTitle: 'Page introuvable', isNotFound: true });
    expect(wildcard.title).toBe('Page introuvable | Industrial Predict AI');
    expect(children.filter((route) => route.path === 'equipments/:equipmentId')).toHaveLength(0);
  });

  it('declares deferred loaders for Shell and every feature without eager components', () => {
    const componentRoutes = [routes[0], ...children.filter((route) => route.redirectTo === undefined)];
    for (const route of componentRoutes) {
      expect(route.component).toBeUndefined();
      if (route.path === 'companies' || route.path === 'sites' || route.path === 'equipments' || route.path === 'sensors') {
        expect(typeof route.loadChildren).toBe('function');
        expect(route.loadComponent).toBeUndefined();
      } else {
        expect(typeof route.loadComponent).toBe('function');
        expect(route.loadChildren).toBeUndefined();
      }
    }
  });

  it('declares lazy Equipment creation and guarded edit before the full-match detail', () => {
    expect(EQUIPMENT_ROUTES.map(route => route.path)).toEqual(['', 'new', ':equipmentId/edit', ':equipmentId']);
    expect(EQUIPMENT_ROUTES.every(route => route.pathMatch === 'full')).toBe(true);
    expect(typeof EQUIPMENT_ROUTES[2].loadComponent).toBe('function');
    expect(EQUIPMENT_ROUTES[2].component).toBeUndefined();
    expect(EQUIPMENT_ROUTES[1].canDeactivate).toHaveLength(1);
    expect(EQUIPMENT_ROUTES[2].canDeactivate).toHaveLength(1);
  });
});

describe('Routing integration gaps', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({ providers: [
      provideRouter(routes), provideNoopAnimations(),
      { provide: NbToastrService, useValue: { success: vi.fn() } },
      ...provideDashboardTesting(),
      importProvidersFrom(
        NbThemeModule.forRoot({ name: 'industrial-predict' },
          [{ name: 'industrial-predict', base: 'default', variables: {} }]),
        NbSidebarModule.forRoot()
      )
    ] });
  });
  afterEach(() => vi.restoreAllMocks());

  async function settle(harness: RouterTestingHarness): Promise<void> {
    harness.fixture.detectChanges();
    TestBed.tick();
    await harness.fixture.whenStable();
    harness.fixture.detectChanges();
  }

  it.each(expectedPages)('synchronizes Header and document titles on %s', async (path, title) => {
    const harness = await RouterTestingHarness.create(path);
    await settle(harness);
    expect(harness.routeNativeElement!.querySelector('app-header .header-title')?.textContent).toBe(title);
    expect(TestBed.inject(Title).getTitle()).toBe(`${title} | Industrial Predict AI`);
  });

  it('updates equipmentId repeatedly on the same detail component without returning to the list', async () => {
    const harness = await RouterTestingHarness.create('/equipments/1');
    await settle(harness);
    const outlet = harness.routeDebugElement!.query(By.directive(RouterOutlet)).injector.get(RouterOutlet);
    const originalComponent = outlet.component;
    expect(harness.routeNativeElement!.querySelector('app-equipment-detail')).not.toBeNull();
    expect(harness.routeNativeElement!.querySelector('app-feature-placeholder')).toBeNull();
    const identifiers: (string | null)[] = [];
    const subscription = outlet.activatedRoute.paramMap.subscribe((params) => identifiers.push(params.get('equipmentId')));
    try {
      for (const id of ['1', '42', '987654321']) {
        if (id !== '1') {
          await harness.navigateByUrl(`/equipments/${id}?tab=sensors`);
          await settle(harness);
        }
        expect(outlet.component).toBe(originalComponent);
        expect(outlet.activatedRoute.snapshot.paramMap.get('equipmentId')).toBe(id);
        expect(harness.routeNativeElement!.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/equipments');
        expect(harness.routeNativeElement!.querySelector('app-header .header-title')?.textContent).toBe('Détail équipement');
        expect(TestBed.inject(Title).getTitle()).toBe('Détail équipement | Industrial Predict AI');
      }
      expect(identifiers).toEqual(['1', '42', '987654321']);
    } finally {
      subscription.unsubscribe();
    }
  });

  it('loads the creation page before the generic Equipment detail with Shell and Sidebar intact', async () => {
    const harness = await RouterTestingHarness.create('/equipments/new'); await settle(harness);
    expect(TestBed.inject(Title).getTitle()).toBe('Nouvel équipement industriel | Industrial Predict AI');
    expect(harness.routeNativeElement!.querySelector('app-equipment-create')).not.toBeNull();
    expect(harness.routeNativeElement!.querySelector('app-equipment-detail')).toBeNull();
    expect(harness.routeNativeElement!.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/equipments');
  });
  it('loads Equipment edit with its title, Shell and active Sidebar', async () => {
    const harness = await RouterTestingHarness.create('/equipments/12/edit'); await settle(harness);
    expect(TestBed.inject(Title).getTitle()).toBe('Modifier l’équipement | Industrial Predict AI');
    expect(harness.routeNativeElement!.querySelector('app-equipment-edit')).not.toBeNull();
    expect(harness.routeNativeElement!.querySelector('app-sidebar a.is-active')?.getAttribute('href')).toBe('/equipments');
    expect(harness.routeNativeElement!.querySelector('app-header .header-title')?.textContent).toBe('Modifier l’équipement');
  });
  it.each(['/equipments/12/extra', '/equipments/12/edit/extra'])(
    'keeps future or unknown Equipment path %s on the global 404', async path => {
      const harness = await RouterTestingHarness.create(path); await settle(harness);
      expect(TestBed.inject(Title).getTitle()).toBe('Page introuvable | Industrial Predict AI');
      expect(harness.routeNativeElement!.querySelector('app-equipment-detail')).toBeNull();
      expect(harness.routeNativeElement!.querySelectorAll('nav a[href]')).toHaveLength(9);
    });

  it('calls only visited component loaders and reuses them for same-page navigation', async () => {
    const shellLoader = vi.fn(routes[0].loadComponent!);
    const trackedChildren = children.map((route) => ({
      ...route,
      ...(route.loadComponent ? { loadComponent: vi.fn(route.loadComponent) } : {}),
      ...(route.loadChildren ? { loadChildren: vi.fn(route.loadChildren) } : {})
    }));
    TestBed.inject(Router).resetConfig([{ ...routes[0], loadComponent: shellLoader, children: trackedChildren }]);
    const harness = await RouterTestingHarness.create('/dashboard');
    await settle(harness);
    const loader = (path: string) => {
      const route = trackedChildren.find(route => route.path === path)!;
      return route.loadComponent ?? route.loadChildren!;
    };
    expect(shellLoader).toHaveBeenCalledTimes(1);
    expect(loader('dashboard')).toHaveBeenCalledTimes(1);
    for (const route of trackedChildren) {
      if (route.loadComponent && route.path !== 'dashboard') expect(route.loadComponent).not.toHaveBeenCalled();
    }
    await harness.navigateByUrl('/sites');
    await settle(harness);
    expect(loader('sites')).toHaveBeenCalledTimes(1);
    await harness.navigateByUrl('/sites?company=2');
    await settle(harness);
    expect(loader('sites')).toHaveBeenCalledTimes(1);
    await harness.navigateByUrl('/inconnu');
    await settle(harness);
    expect(loader('**')).toHaveBeenCalledTimes(1);
    expect(shellLoader).toHaveBeenCalledTimes(1);
    for (const route of trackedChildren) {
      if (route.loadComponent && !['dashboard', 'sites', '**'].includes(route.path!)) {
        expect(route.loadComponent).not.toHaveBeenCalled();
      }
    }
  });
});
