import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarModule, NbThemeModule } from '@nebular/theme';
import { vi } from 'vitest';
import { routes } from '../../app.routes';
import { provideDashboardTesting } from '../../features/dashboard/testing/dashboard-testing';

describe('Sidebar navigation', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        provideNoopAnimations(),
        ...provideDashboardTesting(),
        importProvidersFrom(
          NbThemeModule.forRoot(
            { name: 'industrial-predict' },
            [{ name: 'industrial-predict', base: 'default', variables: {} }]
          ),
          NbSidebarModule.forRoot()
        )
      ]
    });
  });

  afterEach(() => vi.restoreAllMocks());

  async function open(url = '/dashboard') {
    const harness = await RouterTestingHarness.create(url);
    await harness.fixture.whenStable();
    harness.detectChanges();
    return harness;
  }

  function activeLinks(harness: RouterTestingHarness): HTMLAnchorElement[] {
    return Array.from(harness.routeNativeElement!.querySelectorAll('nav a[aria-current="true"]'));
  }

  it('should render all eleven entries in order inside a single Nebular sidebar', async () => {
    const harness = await open();
    const root = harness.routeNativeElement!;

    expect(root.querySelectorAll('nb-sidebar')).toHaveLength(1);
    expect(root.querySelector('nb-sidebar .main-container-fixed')).toBeNull();
    expect(root.querySelector('nav')?.getAttribute('aria-label')).toBe('Navigation principale');
    expect(Array.from(root.querySelectorAll('nav li')).map(
      (item) => item.querySelector('a, .is-unavailable > span')!.textContent!.trim()
    )).toEqual([
      'Dashboard', 'Entreprises', 'Sites', 'Équipements', 'Capteurs', 'Mesures',
      'Maintenance', 'Prédictions', 'Recommandations', 'Rapports', 'Administration'
    ]);
    expect(root.querySelectorAll('nav a[href]')).toHaveLength(9);
  });

  it('should follow Router navigation and ignore query parameters for the active link', async () => {
    const harness = await open();
    expect(activeLinks(harness).map((link) => link.textContent!.trim())).toEqual(['Dashboard']);

    await harness.navigateByUrl('/sites?company=1');
    await harness.fixture.whenStable();
    harness.detectChanges();

    expect(activeLinks(harness).map((link) => link.textContent!.trim())).toEqual(['Sites']);
    expect(harness.routeNativeElement!.querySelector('main h1')?.textContent).toBe('Sites industriels');
  });

  it('should provide eleven distinct decorative icons while retaining text labels and link focusability', async () => {
    const harness = await open();
    const entries = Array.from(harness.routeNativeElement!.querySelectorAll('nav .navigation-item'));
    const paths = entries.map((entry) => {
      const svg = entry.querySelector('svg')!;
      expect(svg).not.toBeNull();
      expect(svg.getAttribute('aria-hidden')).toBe('true');
      expect(svg.getAttribute('focusable')).toBe('false');
      expect(svg.hasAttribute('tabindex')).toBe(false);
      expect(svg.querySelector('title')).toBeNull();
      expect(entry.querySelector('.navigation-label')?.textContent?.trim()).toBeTruthy();
      if (entry.tagName === 'A') expect((entry as HTMLAnchorElement).tabIndex).toBe(0);
      return svg.querySelector('path')!.getAttribute('d');
    });
    expect(entries).toHaveLength(11);
    expect(new Set(paths).size).toBe(11);
    expect(paths.every(Boolean)).toBe(true);
  });

  it('should keep Équipements active on a detail URL', async () => {
    const harness = await open('/equipments/42?tab=sensors');
    const links = activeLinks(harness);

    expect(links).toHaveLength(1);
    expect(links[0].textContent!.trim()).toBe('Équipements');
    expect(links[0].getAttribute('href')).toBe('/equipments');
    expect(harness.routeNativeElement!.querySelector('main h1')?.textContent).toBe('Détail équipement');
  });

  it('should expose coming-soon entries as disabled without a destination or tab stop', async () => {
    const harness = await open();
    const disabled = Array.from(harness.routeNativeElement!.querySelectorAll('nav [aria-disabled="true"]'));

    expect(disabled.map((item) => item.getAttribute('aria-label'))).toEqual([
      'Rapports - À venir', 'Administration - À venir'
    ]);
    for (const item of disabled) {
      expect(item.tagName).toBe('SPAN');
      expect(item.hasAttribute('href')).toBe(false);
      expect(item.hasAttribute('tabindex')).toBe(false);
      (item as HTMLElement).click();
    }
    expect(TestBed.inject(Router).url).toBe('/dashboard');
  });

  it.each([
    ['/sensors', 'Capteurs'], ['/measurements', 'Mesures'], ['/maintenance', 'Maintenance'],
    ['/predictions', 'Prédictions'], ['/recommendations', 'Recommandations']
  ])('should provide an explicit minimal placeholder for %s', async (path, title) => {
    const harness = await open(path);
    const main = harness.routeNativeElement!.querySelector('main')!;

    expect(main.querySelector('h1')?.textContent).toBe(title);
    expect(main.textContent).toContain('Écran en préparation');
    expect(main.textContent).toContain('Aucune donnée métier');
  });

  it('shows the real Sites page in the Shell while waiting for explicit company selection', async () => {
    const harness = await open('/sites');
    const main = harness.routeNativeElement!.querySelector('main')!;
    expect(main.querySelector('h1')?.textContent).toBe('Sites industriels');
    expect(main.querySelector('app-feature-placeholder')).toBeNull();
    expect(main.textContent).toContain('Sélectionnez une entreprise pour consulter ses sites');
    expect(activeLinks(harness).map(link => link.textContent!.trim())).toEqual(['Sites']);
  });

  it('shows the lazy Equipments list and keeps the Sidebar destination active', async () => {
    const harness = await open('/equipments');
    expect(harness.routeNativeElement!.querySelector('main h1')?.textContent).toBe('Équipements industriels');
    expect(harness.routeNativeElement!.querySelector('app-feature-placeholder')).toBeNull();
    expect(harness.routeNativeElement!.textContent).toContain('Sélectionnez une entreprise puis un site');
    expect(activeLinks(harness).map(link => link.textContent!.trim())).toEqual(['Équipements']);
  });
});
