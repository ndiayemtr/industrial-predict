import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbSidebarComponent, NbSidebarModule, NbSidebarService, NbThemeModule } from '@nebular/theme';
import { vi } from 'vitest';
import { routes } from '../../app.routes';
import { FeaturePlaceholderComponent } from '../../shared/pages/feature-placeholder/feature-placeholder.component';
import { ShellComponent } from '../shell/shell.component';

describe('Global Header', () => {
  beforeEach(() => {
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes), provideNoopAnimations(),
        importProvidersFrom(
          NbThemeModule.forRoot({ name: 'industrial-predict' },
            [{ name: 'industrial-predict', base: 'default', variables: {} }]),
          NbSidebarModule.forRoot()
        )
      ]
    });
  });
  afterEach(() => vi.restoreAllMocks());

  async function open(url: string) {
    const harness = await RouterTestingHarness.create(url);
    await harness.fixture.whenStable();
    harness.detectChanges();
    return harness;
  }

  it('updates its title when navigating between list and detail routes', async () => {
    const harness = await open('/dashboard');
    const title = () => harness.routeNativeElement!.querySelector('app-header .header-title')!.textContent;
    expect(title()).toBe('Dashboard');
    await harness.navigateByUrl('/equipments');
    expect(title()).toBe('Équipements');
    await harness.navigateByUrl('/equipments/42?tab=sensors');
    expect(title()).toBe('Détail équipement');
    expect(harness.routeNativeElement!.querySelectorAll('nb-layout-header')).toHaveLength(1);
    expect(harness.routeNativeElement!.querySelector('app-header nav')).toBeNull();
  });

  it('uses the deepest primary child metadata and falls back when metadata is absent', async () => {
    TestBed.inject(Router).resetConfig([{
      path: 'test', component: ShellComponent,
      children: [{ path: 'parent', data: { pageTitle: 'Parent' }, children: [
        { path: 'child', component: FeaturePlaceholderComponent, data: { pageTitle: 'Enfant' } }
      ] }, { path: 'fallback', component: FeaturePlaceholderComponent }]
    }]);
    const harness = await open('/test/parent/child');
    expect(harness.routeNativeElement!.querySelector('app-header .header-title')!.textContent).toBe('Enfant');
    await harness.navigateByUrl('/test/fallback');
    expect(harness.routeNativeElement!.querySelector('app-header .header-title')!.textContent).toBe('Espace de travail');
  });

  it('toggles the actual Sidebar state and keeps accessibility in sync with external changes', async () => {
    const harness = await open('/dashboard');
    const root = harness.routeNativeElement!;
    const button = root.querySelector<HTMLButtonElement>('.sidebar-toggle')!;
    const sidebar = harness.routeDebugElement!.query(By.directive(NbSidebarComponent)).componentInstance as NbSidebarComponent;
    const service = TestBed.inject(NbSidebarService);
    expect(button.getAttribute('aria-controls')).toBe(root.querySelector('nb-sidebar')!.id);
    expect(button.getAttribute('aria-expanded')).toBe('true');
    button.click();
    harness.detectChanges();
    expect(sidebar.state).toBe('collapsed');
    expect(button.getAttribute('aria-expanded')).toBe('false');
    expect(root.querySelector('nb-sidebar')!.hasAttribute('inert')).toBe(true);
    button.click();
    harness.detectChanges();
    expect(sidebar.state).toBe('expanded');
    expect(button.getAttribute('aria-expanded')).toBe('true');
    service.collapse('other-sidebar');
    harness.detectChanges();
    expect(sidebar.state).toBe('expanded');
    service.collapse('shell-sidebar');
    harness.detectChanges();
    expect(button.getAttribute('aria-expanded')).toBe('false');
    service.expand('shell-sidebar');
    harness.detectChanges();
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(root.querySelector('nb-sidebar')!.hasAttribute('inert')).toBe(false);
  });

  it('keeps notifications and profile explicitly disabled without a fictitious counter or identity', async () => {
    const harness = await open('/dashboard');
    const header = harness.routeNativeElement!.querySelector('app-header')!;
    const buttons = Array.from(header.querySelectorAll<HTMLButtonElement>('.header-actions button'));
    expect(buttons.map((button) => button.getAttribute('aria-label'))).toEqual([
      'Notifications — À venir', 'Profil utilisateur — À venir'
    ]);
    for (const button of buttons) {
      expect(button.disabled).toBe(true);
      expect(button.textContent).toContain('À venir');
      button.click();
    }
    expect(TestBed.inject(Router).url).toBe('/dashboard');
    expect(header.querySelector('a, nb-badge, img, [role="dialog"]')).toBeNull();
  });
});
