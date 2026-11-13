import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Title } from '@angular/platform-browser';
import { Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { vi } from 'vitest';
import { appConfig } from '../../app.config';
import { PREPARATION_ROUTES, routes } from '../../app.routes';
import { ProfessionalLoginComponent } from './pages/professional-login/professional-login.component';
import { PROFESSIONAL_CONNECTION_PREPARATION } from './professional-connection.model';

describe('Professional connection preparation', () => {
  beforeEach(() => TestBed.configureTestingModule({
    providers: [...appConfig.providers, provideHttpClientTesting()],
  }));
  afterEach(() => {
    const http = TestBed.inject(HttpTestingController);
    http.expectNone(() => true);
    http.verify();
    vi.restoreAllMocks();
  });

  it('shows one accessible title, a disabled Google button and its visible explanation', () => {
    const fixture = TestBed.createComponent(ProfessionalLoginComponent);
    fixture.detectChanges();
    const root: HTMLElement = fixture.nativeElement;
    expect(root.querySelectorAll('h1')).toHaveLength(1);
    expect(root.querySelector('h1')?.textContent).toBe('Connexion professionnelle');
    expect(root.querySelector('main')?.getAttribute('aria-labelledby')).toBe('login-title');
    const button = root.querySelector<HTMLButtonElement>('button')!;
    expect(button.textContent).toContain('Continuer avec Google');
    expect(button.type).toBe('button');
    expect(button.disabled).toBe(true);
    expect(button.getAttribute('aria-describedby')).toBe('login-availability');
    expect(root.querySelector('#login-availability')?.textContent).toBe(PROFESSIONAL_CONNECTION_PREPARATION.message);
    expect(root.textContent).toContain('Vous n’êtes pas connecté.');
    expect(root.querySelectorAll('a, form, input, app-sidebar, app-header')).toHaveLength(0);
  });

  it('never creates a session, writes browser storage or calls Google on interaction', () => {
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem');
    const fixture = TestBed.createComponent(ProfessionalLoginComponent);
    fixture.detectChanges();
    const button: HTMLButtonElement = fixture.nativeElement.querySelector('button');
    button.click();
    button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    fixture.detectChanges();
    expect(fixture.componentInstance.preparation.authenticated).toBe(false);
    expect(fixture.componentInstance.preparation.status).toBe('unavailable');
    expect(Object.isFrozen(fixture.componentInstance.preparation)).toBe(true);
    expect(storageWrite).not.toHaveBeenCalled();
    expect(TestBed.inject(Router).url).toBe('/');
  });

  it('opens the explicit page without loading the business shell', async () => {
    const shellLoader = vi.fn(PREPARATION_ROUTES[1].loadComponent!);
    TestBed.inject(Router).resetConfig([
      PREPARATION_ROUTES[0], { ...PREPARATION_ROUTES[1], loadComponent: shellLoader },
    ]);
    const harness = await RouterTestingHarness.create('/connexion');
    harness.fixture.detectChanges();
    expect(harness.routeNativeElement?.querySelector('h1')?.textContent).toBe('Connexion professionnelle');
    expect(TestBed.inject(Title).getTitle()).toBe('Connexion professionnelle | Industrial Predict AI');
    expect(shellLoader).not.toHaveBeenCalled();
  });

  it.each(['/', '/dashboard', '/companies', '/equipments/new', '/equipments/12/edit',
    '/predictions?company_id=1', '/connexion/extra', '/unknown'])(
    'redirects %s to preparation before any business component or API call', async url => {
      const shellLoader = vi.fn(PREPARATION_ROUTES[1].loadComponent!);
      TestBed.inject(Router).resetConfig([
        PREPARATION_ROUTES[0], { ...PREPARATION_ROUTES[1], loadComponent: shellLoader },
      ]);
      const harness = await RouterTestingHarness.create(url);
      harness.fixture.detectChanges();
      expect(TestBed.inject(Router).url).toBe('/connexion');
      expect(harness.routeNativeElement?.querySelector('button')?.disabled).toBe(true);
      expect(shellLoader).not.toHaveBeenCalled();
      expect(PROFESSIONAL_CONNECTION_PREPARATION.authenticated).toBe(false);
    },
  );

  it('also blocks navigation away from the preparation page', async () => {
    const harness = await RouterTestingHarness.create('/connexion');
    await harness.navigateByUrl('/companies');
    expect(TestBed.inject(Router).url).toBe('/connexion');
    expect(harness.routeNativeElement?.querySelector('app-sidebar')).toBeNull();
  });

  it('keeps the existing business configuration and lazy loaders intact behind the guard', () => {
    expect(PREPARATION_ROUTES[1].children).toBe(routes[0].children);
    expect(PREPARATION_ROUTES[1].loadComponent).toBe(routes[0].loadComponent);
    expect(PREPARATION_ROUTES[1].canMatch).toHaveLength(1);
    expect(TestBed.inject(Router).config).toEqual(PREPARATION_ROUTES);
  });
});
