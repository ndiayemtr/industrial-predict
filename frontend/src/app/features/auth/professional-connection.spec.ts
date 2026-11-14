import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { Title } from '@angular/platform-browser';
import { Router } from '@angular/router';
import { RouterTestingHarness } from '@angular/router/testing';
import { vi } from 'vitest';
import { appConfig } from '../../app.config';
import { PREPARATION_ROUTES, routes } from '../../app.routes';
import { ProfessionalLoginComponent } from './pages/professional-login/professional-login.component';
import { PROFESSIONAL_CONNECTION_PREPARATION } from './professional-connection.model';
import { B2B_BROWSER_BRIDGE, PROFESSIONAL_AUTH_BACKEND, PROFESSIONAL_AUTH_WINDOW, ProfessionalAuthBackend } from './professional-auth.model';
import { ProfessionalAuthService } from './professional-auth.service';
import { Subject } from 'rxjs';

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
    expect(fixture.componentInstance.auth.authenticated()).toBe(false);
    expect(fixture.componentInstance.auth.state().status).toBe('unavailable');
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

describe('Professional connection states with a server adapter double only', () => {
  let fixture: ComponentFixture<ProfessionalLoginComponent>;
  let profile: Subject<unknown>;
  let revoke: Subject<void>;
  let popup: Window;
  let backend: ProfessionalAuthBackend;
  let listeners: Set<(event: MessageEvent<unknown>) => void>;
  const origin = 'https://industrial.example.test';

  beforeEach(() => {
    profile = new Subject(); revoke = new Subject(); listeners = new Set();
    popup = { closed: false, close: vi.fn() } as unknown as Window;
    backend = { bridgeVersion: B2B_BROWSER_BRIDGE, ready: signal(true),
      loadProfile: vi.fn(() => profile), revokeSession: vi.fn(() => revoke) };
    const browser = {
      location: { origin }, open: vi.fn(() => popup),
      addEventListener: (_: string, handler: (event: MessageEvent<unknown>) => void) => listeners.add(handler),
      removeEventListener: (_: string, handler: (event: MessageEvent<unknown>) => void) => listeners.delete(handler),
      setTimeout: (handler: () => void, ms: number) => window.setTimeout(handler, ms),
      clearTimeout: (id: number) => window.clearTimeout(id),
      setInterval: (handler: () => void, ms: number) => window.setInterval(handler, ms),
      clearInterval: (id: number) => window.clearInterval(id),
    } as unknown as Window;
    TestBed.configureTestingModule({ providers: [...appConfig.providers, provideHttpClientTesting(),
      { provide: PROFESSIONAL_AUTH_BACKEND, useValue: backend }, { provide: PROFESSIONAL_AUTH_WINDOW, useValue: browser }] });
    fixture = TestBed.createComponent(ProfessionalLoginComponent); fixture.detectChanges();
  });
  afterEach(() => {
    fixture.destroy(); TestBed.inject(ProfessionalAuthService).reset();
    TestBed.inject(HttpTestingController).expectNone(() => true);
    TestBed.inject(HttpTestingController).verify();
    vi.restoreAllMocks();
  });
  function root(): HTMLElement { return fixture.nativeElement; }
  function click(text: string): void {
    const button = Array.from(root().querySelectorAll('button')).find(b => b.textContent?.includes(text));
    expect(button).toBeTruthy(); button!.click(); fixture.detectChanges();
  }
  function callback(expiry = new Date(Date.now() + 3_600_000).toISOString()): void {
    const event = { origin, source: popup, ports: [], data: { kind: B2B_BROWSER_BRIDGE,
      token_type: 'Bearer', session_token: 'A'.repeat(43), absolute_expires_at: expiry } } as unknown as MessageEvent<unknown>;
    [...listeners].forEach(listener => listener(event)); fixture.detectChanges();
  }

  it('announces pending connection and allows cancellation without opening business pages', () => {
    expect(root().querySelector<HTMLButtonElement>('.google-button')?.disabled).toBe(false);
    click('Continuer avec Google');
    expect(root().textContent).toContain('Connexion en cours');
    expect(root().querySelector('.connection-panel')?.getAttribute('aria-busy')).toBe('true');
    expect(root().querySelector('[role=status]')?.getAttribute('aria-live')).toBe('polite');
    click('Annuler');
    expect(root().textContent).toContain('Connexion annulée.');
    expect(root().querySelectorAll('a, app-sidebar')).toHaveLength(0);
  });

  it('shows only the server identity and companies, escaped, then clears them during logout', () => {
    click('Continuer avec Google'); callback();
    expect(root().textContent).toContain('Vérification de votre session');
    profile.next({ userId: 1, displayName: '<script>server label</script>', companies: [
      { companyId: 7, displayName: 'Entreprise autorisée', permissions: ['predictions:read'] },
    ] }); fixture.detectChanges();
    expect(root().textContent).toContain('<script>server label</script>');
    expect(root().querySelector('script')).toBeNull();
    expect(root().querySelector('[aria-label="Entreprises autorisées"]')?.textContent).toContain('Entreprise autorisée');
    expect(root().textContent).toContain('Les espaces métier restent fermés');
    click('Se déconnecter');
    expect(root().textContent).toContain('Déconnexion en cours');
    expect(root().textContent).not.toContain('Entreprise autorisée');
    revoke.next(); fixture.detectChanges();
    expect(root().textContent).toContain('Vous êtes déconnecté.');
  });

  it('displays refusal and never shows a connected account on HTTP 403', () => {
    click('Continuer avec Google'); callback(); profile.error(new HttpErrorResponse({ status: 403 }));
    fixture.detectChanges();
    expect(root().textContent).toContain('Authentification refusée');
    expect(root().textContent).toContain('Vous n’êtes pas connecté.');
    expect(root().querySelector('.company-list')).toBeNull();
  });

  it('disables Google when the authentication service returns 503', () => {
    click('Continuer avec Google'); callback(); profile.error(new HttpErrorResponse({ status: 503 }));
    fixture.detectChanges();
    expect(root().textContent).toContain('Service indisponible');
    expect(root().querySelector<HTMLButtonElement>('.google-button')?.disabled).toBe(true);
  });

  it('explains an expired callback and requests no profile', () => {
    click('Continuer avec Google'); callback(new Date(Date.now() - 1_000).toISOString());
    expect(root().textContent).toContain('Votre session a expiré');
    expect(backend.loadProfile).not.toHaveBeenCalled();
  });

  it('keeps the uncertain logout warning visible when transport readiness is withdrawn', () => {
    click('Continuer avec Google'); callback();
    profile.next({ userId: 1, displayName: null, companies: [
      { companyId: 7, displayName: 'Entreprise autorisée', permissions: [] },
    ] }); fixture.detectChanges(); click('Se déconnecter');
    revoke.error(new HttpErrorResponse({ status: 503 }));
    // Same sequence as the HTTP adapter: availability fails before the effect flush.
    Object.assign(backend, { availability: signal('unavailable') });
    (backend.ready as ReturnType<typeof signal<boolean>>).set(false);
    fixture.detectChanges();
    expect(root().textContent).toContain('Service indisponible');
    expect(root().textContent).toContain('la déconnexion serveur n’a pas pu être confirmée');
    expect(root().querySelector<HTMLButtonElement>('.google-button')?.disabled).toBe(true);
    expect(root().textContent).not.toContain('Entreprise autorisée');
  });
});
