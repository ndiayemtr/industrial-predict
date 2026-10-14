import { importProvidersFrom } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { vi } from 'vitest';
import { By } from '@angular/platform-browser';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { provideRouter, Router, RouterOutlet } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { NbLayoutHeaderComponent, NbSidebarModule, NbThemeModule, NbThemeService } from '@nebular/theme';
import { routes } from '../../app.routes';
import { DashboardComponent } from '../../features/dashboard/pages/dashboard/dashboard.component';
import { provideDashboardTesting } from '../../features/dashboard/testing/dashboard-testing';
import { ShellComponent } from './shell.component';

describe('Shell routing', () => {
  beforeEach(() => {
    // jsdom does not implement scrolling; keep this stub local to this suite.
    vi.spyOn(window, 'scrollTo').mockImplementation(() => {});
    TestBed.configureTestingModule({
      providers: [
        provideRouter(routes),
        ...provideDashboardTesting(),
        provideNoopAnimations(),
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

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render the Shell and redirect the root to the child Dashboard outlet', async () => {
    const harness = await RouterTestingHarness.create('/');
    const shell = harness.routeDebugElement!;
    const outlet = shell.query(By.directive(RouterOutlet)).injector.get(RouterOutlet);

    expect(TestBed.inject(Router).url).toBe('/dashboard');
    expect(shell.componentInstance).toBeInstanceOf(ShellComponent);
    expect(outlet.isActivated).toBe(true);
    expect(outlet.component).toBeInstanceOf(DashboardComponent);
    expect(shell.nativeElement.querySelector('nb-sidebar').textContent).toContain('Industrial Predict');
    expect(shell.nativeElement.querySelector('nb-layout-header .header-title').textContent).toBe('Dashboard');
    expect(shell.nativeElement.querySelector('main h1').textContent).toBe('Dashboard');
    expect(shell.nativeElement.querySelector('main').textContent).toContain('Sélectionnez une entreprise');
  });

  it('should use a non-fixed subheader beside the sidebar and a single selected theme', async () => {
    const harness = await RouterTestingHarness.create('/dashboard');
    const shell = harness.routeDebugElement!;
    const header = shell.query(By.directive(NbLayoutHeaderComponent))
      .componentInstance as NbLayoutHeaderComponent;

    expect(header.subheaderValue).toBe(true);
    expect(header.fixedValue).toBe(false);
    expect(shell.nativeElement.querySelector('.content > nb-layout-header')).not.toBeNull();
    expect(shell.nativeElement.querySelector('nb-layout-column main router-outlet')).not.toBeNull();
    expect(TestBed.inject(NbThemeService).currentTheme).toBe('industrial-predict');
  });
});
