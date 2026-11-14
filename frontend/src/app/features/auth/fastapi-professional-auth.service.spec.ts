import { HttpClient, HttpErrorResponse, HttpInterceptorFn, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { EMPTY, firstValueFrom, of, Subject, throwError } from 'rxjs';
import { vi } from 'vitest';
import {
  AUTH_LOGOUT_PATH, AUTH_ME_PATH, FastApiProfessionalAuthBackend, PROFESSIONAL_AUTH_CONFIGURATION,
  PROFESSIONAL_AUTH_HTTP, PROFESSIONAL_AUTH_READINESS_VERIFIER, ProfessionalAuthConfiguration,
  ProfessionalAuthReadinessVerifier,
} from './fastapi-professional-auth.service';
import { B2B_BROWSER_BRIDGE, PROFESSIONAL_AUTH_BACKEND, PROFESSIONAL_AUTH_WINDOW } from './professional-auth.model';
import { ProfessionalAuthService } from './professional-auth.service';
import { preparationOnlyGuard } from './preparation-only.guard';

const ORIGIN = 'https://industrial.example.test';
const CONFIG = { origin: ORIGIN, bridgeVersion: B2B_BROWSER_BRIDGE } as const;
const TOKEN = 'A'.repeat(43); // Synthetic unit fixture only.
const PROFILE = { userId: 17, displayName: null, companies: [
  { companyId: 9, displayName: 'Entreprise serveur', permissions: ['predictions:read', 'predictions:analyze'] },
] };
const HEADERS = { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' };

describe('FastAPI professional auth adapter and popup integration (HTTP doubles)', () => {
  let http: HttpTestingController;
  let adapter: FastApiProfessionalAuthBackend;
  let service: ProfessionalAuthService;
  let popup: Window;
  let browser: Window;
  let listeners: Set<(event: MessageEvent<unknown>) => void>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-14T12:00:00Z'));
    listeners = new Set();
    popup = { closed: false, close: vi.fn() } as unknown as Window;
    browser = {
      location: { origin: ORIGIN }, open: vi.fn(() => popup),
      addEventListener: (_: string, handler: (event: MessageEvent<unknown>) => void) => listeners.add(handler),
      removeEventListener: (_: string, handler: (event: MessageEvent<unknown>) => void) => listeners.delete(handler),
      setTimeout: (fn: () => void, ms: number) => window.setTimeout(fn, ms),
      clearTimeout: (id: number) => window.clearTimeout(id),
      setInterval: (fn: () => void, ms: number) => window.setInterval(fn, ms),
      clearInterval: (id: number) => window.clearInterval(id),
    } as unknown as Window;
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([]),
      { provide: PROFESSIONAL_AUTH_HTTP, useExisting: HttpClient },
      { provide: PROFESSIONAL_AUTH_BACKEND, useExisting: FastApiProfessionalAuthBackend },
      { provide: PROFESSIONAL_AUTH_WINDOW, useValue: browser },
      { provide: PROFESSIONAL_AUTH_CONFIGURATION, useValue: CONFIG },
      // This proves only unit behavior, never a real backend activation.
      { provide: PROFESSIONAL_AUTH_READINESS_VERIFIER, useValue: { verify: () => of(undefined) } },
    ] });
  });
  function start(): void {
    adapter = TestBed.inject(FastApiProfessionalAuthBackend);
    service = TestBed.inject(ProfessionalAuthService);
    http = TestBed.inject(HttpTestingController);
    service.initialize(); TestBed.tick();
  }
  function message(origin = ORIGIN, source = popup, data: unknown = {
    kind: B2B_BROWSER_BRIDGE, token_type: 'Bearer', session_token: TOKEN,
    absolute_expires_at: '2026-11-14T13:00:00Z',
  }): void {
    const event = { origin, source, ports: [], data } as unknown as MessageEvent<unknown>;
    [...listeners].forEach(listener => listener(event));
  }
  function authenticate(): void {
    expect(TestBed.inject(PROFESSIONAL_AUTH_BACKEND)).toBe(adapter);
    expect(adapter.bridgeVersion).toBe(B2B_BROWSER_BRIDGE);
    expect(service.backendReady()).toBe(true);
    service.login(); message();
    http.expectOne(ORIGIN + AUTH_ME_PATH).flush(PROFILE, { headers: HEADERS });
  }
  afterEach(() => {
    service?.reset();
    http?.verify();
    vi.restoreAllMocks(); vi.useRealTimers();
  });

  it('uses exact me DTO, frozen server grants, and request-local bearer without cookies/cache/redirects', () => {
    start(); let value: unknown;
    adapter.loadProfile(TOKEN).subscribe(result => value = result);
    const req = http.expectOne(ORIGIN + AUTH_ME_PATH);
    expect(req.request.method).toBe('GET');
    expect(req.request.headers.get('Authorization')).toBe('Bearer ' + TOKEN);
    expect(req.request.params.keys()).toEqual([]);
    expect(req.request.credentials).toBe('omit');
    expect(req.request.mode).toBe('same-origin');
    expect(req.request.redirect).toBe('error');
    expect(req.request.cache).toBe('no-store');
    expect(req.request.referrer).toBe(ORIGIN + '/');
    expect(req.request.referrerPolicy).toBe('same-origin');
    expect(req.request.transferCache).toBe(false);
    expect(req.request.headers.has('Origin')).toBe(false); // Supplied by the real browser on POST.
    req.flush(PROFILE, { headers: HEADERS });
    expect(value).toEqual(PROFILE);
    expect(Object.isFrozen(value)).toBe(true);
  });

  it('posts no selectors or bearer body and accepts only an empty 204 logout', () => {
    start(); const result = vi.fn();
    adapter.revokeSession(TOKEN).subscribe(result);
    const req = http.expectOne(ORIGIN + AUTH_LOGOUT_PATH);
    expect(req.request.method).toBe('POST'); expect(req.request.body).toBeNull();
    expect(req.request.headers.get('Authorization')).toBe('Bearer ' + TOKEN);
    expect(req.request.params.keys()).toEqual([]);
    expect(req.request.credentials).toBe('omit'); expect(req.request.redirect).toBe('error');
    req.flush(null, { status: 204, statusText: 'No Content', headers: HEADERS });
    expect(result).toHaveBeenCalledExactlyOnceWith(undefined);
  });

  it.each([401, 403, 503, 500])('sanitizes HTTP %i and withdraws availability only for service failures', status => {
    start(); const error = vi.fn(); adapter.loadProfile(TOKEN).subscribe({ error });
    http.expectOne(ORIGIN + AUTH_ME_PATH).flush({ detail: TOKEN }, { status, statusText: TOKEN });
    const failure: HttpErrorResponse = error.mock.calls[0][0];
    expect(failure.status).toBe(status === 500 ? 503 : status);
    expect(JSON.stringify(failure)).not.toContain(TOKEN);
    expect(adapter.ready()).toBe(status === 401 || status === 403);
  });

  it('maps a network failure without retaining the reflected response', () => {
    start(); const error = vi.fn(); adapter.loadProfile(TOKEN).subscribe({ error });
    http.expectOne(ORIGIN + AUTH_ME_PATH).error(new ProgressEvent('error'));
    expect(error.mock.calls[0][0].status).toBe(0);
    expect(adapter.ready()).toBe(false);
  });

  it.each([
    { body: { ...PROFILE, email: 'user@company.test' }, headers: HEADERS },
    { body: { ...PROFILE, companies: [] }, headers: HEADERS },
    { body: PROFILE, headers: { 'Content-Type': 'application/json' } },
    { body: PROFILE, headers: { ...HEADERS, 'Content-Type': 'text/html' } },
  ])('refuses unexpected profile content or cache contract %#', fixture => {
    start(); const error = vi.fn(); adapter.loadProfile(TOKEN).subscribe({ error });
    http.expectOne(ORIGIN + AUTH_ME_PATH).flush(fixture.body, { headers: fixture.headers as Record<string, string> });
    expect(error.mock.calls[0][0].status).toBe(503); expect(adapter.ready()).toBe(false);
  });

  it('does not treat a logout 200 as confirmed revocation', () => {
    start(); authenticate(); service.logout();
    http.expectOne(ORIGIN + AUTH_LOGOUT_PATH).flush({}, { headers: HEADERS }); TestBed.tick();
    expect(service.state()).toEqual({ status: 'error', reason: 'logout-unconfirmed' });
    expect(service.profile()).toBeNull(); expect(service.canStart()).toBe(false);
  });

  it('rejects a malformed token before any HTTP request', () => {
    start(); const error = vi.fn(); adapter.loadProfile('header.payload.signature').subscribe({ error });
    http.expectNone(() => true); expect(error.mock.calls[0][0].status).toBe(401);
  });

  it('requires configuration AND independent server verification, with no implicit probing', () => {
    TestBed.overrideProvider(PROFESSIONAL_AUTH_READINESS_VERIFIER, { useValue: null });
    start(); service.login();
    expect(adapter.availability()).toBe('closed'); expect(service.canStart()).toBe(false);
    expect(browser.open).not.toHaveBeenCalled(); http.expectNone(() => true);
  });

  it.each([null, { ...CONFIG, origin: 'http://127.0.0.1:4201' },
    { ...CONFIG, origin: 'https://other.test' }, { ...CONFIG, origin: ORIGIN + '/' },
    { ...CONFIG, bridgeVersion: 'invented' }, { ...CONFIG, enabled: true }])(
    'rejects absent or unapproved deployment configuration %#', config => {
      const verify = vi.fn(() => of(undefined));
      TestBed.overrideProvider(PROFESSIONAL_AUTH_CONFIGURATION, { useValue: config });
      TestBed.overrideProvider(PROFESSIONAL_AUTH_READINESS_VERIFIER, { useValue: { verify } });
      start(); service.login();
      expect(verify).not.toHaveBeenCalled(); expect(adapter.ready()).toBe(false);
      expect(browser.open).not.toHaveBeenCalled(); http.expectNone(() => true);
    },
  );

  it.each([EMPTY, throwError(() => new Error(TOKEN)), of(true)])(
    'refuses empty, failed or boolean readiness proof %#', result => {
      TestBed.overrideProvider(PROFESSIONAL_AUTH_READINESS_VERIFIER, { useValue: { verify: () => result } });
      start(); expect(service.state()).toEqual({ status: 'unavailable', reason: 'service' });
      expect(adapter.ready()).toBe(false); expect(service.message()).not.toContain(TOKEN);
    },
  );

  it('waits for independent verification before allowing a user popup', () => {
    const proof = new Subject<void>();
    TestBed.overrideProvider(PROFESSIONAL_AUTH_READINESS_VERIFIER, { useValue: { verify: () => proof } });
    start(); expect(adapter.availability()).toBe('checking'); service.login();
    expect(browser.open).not.toHaveBeenCalled();
    proof.next(); TestBed.tick();
    expect(service.state()).toEqual({ status: 'anonymous', reason: 'initial' });
    expect(service.canStart()).toBe(true); http.expectNone(() => true);
  });

  it('bounds verification without retries or leaking diagnostics', () => {
    const verify = vi.fn(() => new Subject<void>());
    TestBed.overrideProvider(PROFESSIONAL_AUTH_READINESS_VERIFIER, { useValue: { verify } });
    start(); vi.advanceTimersByTime(10_000); TestBed.tick();
    expect(verify).toHaveBeenCalledOnce(); expect(adapter.availability()).toBe('unavailable');
    expect(service.canStart()).toBe(false); http.expectNone(() => true);
  });

  it('completes popup → me → logout only after the respective HTTP confirmations', () => {
    start(); const storageRead = vi.spyOn(Storage.prototype, 'getItem');
    const storageWrite = vi.spyOn(Storage.prototype, 'setItem');
    const cookie = vi.spyOn(Document.prototype, 'cookie', 'set');
    const history = vi.spyOn(window.history, 'pushState');
    service.login(); service.login();
    expect(browser.open).toHaveBeenCalledExactlyOnceWith('/auth/oidc/google/start', '_blank', 'popup,width=520,height=700');
    message(); message(); expect(service.authenticated()).toBe(false);
    http.expectOne(ORIGIN + AUTH_ME_PATH).flush(PROFILE, { headers: HEADERS });
    expect(service.profile()).toEqual(PROFILE);
    const route = TestBed.runInInjectionContext(() => preparationOnlyGuard({} as never, []));
    expect(TestBed.inject(Router).serializeUrl(route as UrlTree)).toBe('/connexion');
    service.logout(); expect(service.state().status).toBe('signing-out'); expect(service.profile()).toBeNull();
    http.expectOne(ORIGIN + AUTH_LOGOUT_PATH).flush(null, { status: 204, statusText: 'No Content', headers: HEADERS });
    expect(service.state()).toEqual({ status: 'anonymous', reason: 'signed-out' });
    expect(storageRead).not.toHaveBeenCalled(); expect(storageWrite).not.toHaveBeenCalled();
    expect(cookie).not.toHaveBeenCalled(); expect(history).not.toHaveBeenCalled();
    expect(JSON.stringify(service.state())).not.toContain(TOKEN);
  });

  it('ignores invalid origins, sources, messages and callbacks outside a login attempt', () => {
    start(); message(); http.expectNone(() => true); service.login();
    message('https://evil.test'); message(ORIGIN, {} as Window);
    message(ORIGIN, popup, { kind: B2B_BROWSER_BRIDGE, session_token: TOKEN, profile: PROFILE });
    http.expectNone(() => true); expect(service.state().status).toBe('connecting');
    Object.defineProperty(popup, 'closed', { value: true }); vi.advanceTimersByTime(300);
    message(); http.expectNone(() => true); expect(service.state().status).toBe('anonymous');
  });

  it.each([401, 403, 503, 0])('clears an established identity after profile HTTP %i', status => {
    start(); authenticate(); service.refreshProfile();
    const req = http.expectOne(ORIGIN + AUTH_ME_PATH);
    if (status === 0) req.error(new ProgressEvent('error'));
    else req.flush({}, { status, statusText: 'Refused' });
    TestBed.tick();
    expect(service.state().status).toBe(status === 401 ? 'expired' : status === 403 ? 'denied' : status === 0 ? 'error' : 'unavailable');
    expect(service.profile()).toBeNull(); service.refreshProfile(); http.expectNone(() => true);
  });

  it('expires in memory at the absolute server deadline', () => {
    start(); authenticate(); vi.advanceTimersByTime(3_600_000);
    expect(service.state().status).toBe('expired'); expect(service.profile()).toBeNull();
    service.logout(); http.expectNone(() => true);
  });

  it('handles revoked logout 401 as already invalid', () => {
    start(); authenticate(); service.logout();
    http.expectOne(ORIGIN + AUTH_LOGOUT_PATH).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(service.state()).toEqual({ status: 'anonymous', reason: 'signed-out' });
  });

  it('times out logout before the outer service deadline and retains the uncertain-revocation warning', () => {
    start(); authenticate(); service.logout(); const req = http.expectOne(ORIGIN + AUTH_LOGOUT_PATH);
    vi.advanceTimersByTime(8_000); TestBed.tick();
    expect(req.cancelled).toBe(true); expect(adapter.ready()).toBe(false);
    expect(service.state()).toEqual({ status: 'error', reason: 'logout-unconfirmed' });
    service.logout(); service.refreshProfile(); http.expectNone(() => true);
  });
});

describe('Native auth Fetch transport isolation (no live network)', () => {
  afterEach(() => { vi.restoreAllMocks(); });

  it('bypasses global interceptors and sends no bearer to historical HTTP calls', async () => {
    const interceptor = vi.fn<HttpInterceptorFn>((req, next) => next(req));
    TestBed.configureTestingModule({ providers: [provideHttpClient(withInterceptors([interceptor])), provideHttpClientTesting(),
      { provide: PROFESSIONAL_AUTH_WINDOW, useValue: { location: { origin: ORIGIN } } },
      { provide: PROFESSIONAL_AUTH_CONFIGURATION, useValue: CONFIG satisfies ProfessionalAuthConfiguration },
      { provide: PROFESSIONAL_AUTH_READINESS_VERIFIER, useValue: {
        verify: () => of(undefined),
      } satisfies ProfessionalAuthReadinessVerifier },
    ] });
    const response = new Response(JSON.stringify(PROFILE), { status: 200, headers: HEADERS });
    Object.defineProperty(response, 'url', { value: ORIGIN + AUTH_ME_PATH });
    const fetch = vi.spyOn(globalThis, 'fetch').mockResolvedValue(response);
    const adapter = TestBed.inject(FastApiProfessionalAuthBackend);
    expect(await firstValueFrom(adapter.loadProfile(TOKEN))).toEqual(PROFILE);
    expect(interceptor).not.toHaveBeenCalled();
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe(ORIGIN + AUTH_ME_PATH); expect(String(url)).not.toContain(TOKEN);
    expect(options).toMatchObject({ credentials: 'omit', mode: 'same-origin', redirect: 'error', cache: 'no-store',
      referrer: ORIGIN + '/', referrerPolicy: 'same-origin' });
    const logout = new Response(null, { status: 204, headers: HEADERS });
    Object.defineProperty(logout, 'url', { value: ORIGIN + AUTH_LOGOUT_PATH });
    fetch.mockResolvedValueOnce(logout);
    expect(await firstValueFrom(adapter.revokeSession(TOKEN))).toBeUndefined();
    expect(fetch.mock.calls[1][0]).toBe(ORIGIN + AUTH_LOGOUT_PATH);
    expect(fetch.mock.calls[1][1]).toMatchObject({ method: 'POST', body: null, credentials: 'omit',
      mode: 'same-origin', redirect: 'error', referrer: ORIGIN + '/', referrerPolicy: 'same-origin' });
    expect(interceptor).not.toHaveBeenCalled();
    TestBed.inject(HttpClient).get('/api/v1/companies').subscribe();
    const http = TestBed.inject(HttpTestingController);
    const legacy = http.expectOne('/api/v1/companies');
    expect(legacy.request.headers.has('Authorization')).toBe(false); legacy.flush([]); http.verify();
    expect(interceptor).toHaveBeenCalledOnce();
  });
});
