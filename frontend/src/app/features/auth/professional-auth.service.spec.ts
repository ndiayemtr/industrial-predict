import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { EMPTY, of, Subject } from 'rxjs';
import { vi } from 'vitest';
import { B2B_BROWSER_BRIDGE, PROFESSIONAL_AUTH_BACKEND, PROFESSIONAL_AUTH_WINDOW, ProfessionalAuthBackend } from './professional-auth.model';
import { ProfessionalAuthService } from './professional-auth.service';
import { preparationOnlyGuard } from './preparation-only.guard';
import { provideRouter, Router, UrlTree } from '@angular/router';

const BEARER = 'A'.repeat(43); // Unit fixture only; never provided to the application.
const PROFILE = { userId: 17, displayName: 'Compte de test', companies: [
  { companyId: 9, displayName: 'Entreprise de test', permissions: ['predictions:read', 'predictions:analyze'] },
] };

describe('Professional auth service (isolated integration port)', () => {
  let service: ProfessionalAuthService;
  let ready: ReturnType<typeof signal<boolean>>;
  let profile: Subject<unknown>;
  let revocation: Subject<void>;
  let backend: ProfessionalAuthBackend;
  let popup: Window;
  let browser: Window;
  let listeners: Set<(event: MessageEvent<unknown>) => void>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-14T12:00:00Z'));
    ready = signal(true);
    profile = new Subject<unknown>();
    revocation = new Subject<void>();
    backend = { bridgeVersion: B2B_BROWSER_BRIDGE, ready,
      loadProfile: vi.fn(() => profile), revokeSession: vi.fn(() => revocation) };
    popup = { closed: false, close: vi.fn() } as unknown as Window;
    listeners = new Set();
    browser = {
      location: { origin: 'https://industrial.example.test' },
      open: vi.fn(() => popup),
      addEventListener: vi.fn((_type: string, handler: (event: MessageEvent<unknown>) => void) => listeners.add(handler)),
      removeEventListener: vi.fn((_type: string, handler: (event: MessageEvent<unknown>) => void) => listeners.delete(handler)),
      setTimeout: (handler: () => void, ms: number) => window.setTimeout(handler, ms),
      clearTimeout: (id: number) => window.clearTimeout(id),
      setInterval: (handler: () => void, ms: number) => window.setInterval(handler, ms),
      clearInterval: (id: number) => window.clearInterval(id),
    } as unknown as Window;
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([]),
      { provide: PROFESSIONAL_AUTH_BACKEND, useValue: backend }, { provide: PROFESSIONAL_AUTH_WINDOW, useValue: browser }] });
    service = TestBed.inject(ProfessionalAuthService);
  });

  afterEach(() => {
    service.reset();
    TestBed.inject(HttpTestingController).expectNone(() => true);
    TestBed.inject(HttpTestingController).verify();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  function message(data: unknown = delivery(), origin = browser.location.origin, source: Window = popup): void {
    const event = { data, origin, source, ports: [] } as unknown as MessageEvent<unknown>;
    [...listeners].forEach(listener => listener(event));
  }
  function delivery(expires = '2026-11-14T13:00:00+00:00'): Record<string, unknown> {
    return { kind: B2B_BROWSER_BRIDGE, token_type: 'Bearer', session_token: BEARER, absolute_expires_at: expires };
  }
  function authenticate(): void { service.login(); message(); profile.next(PROFILE); }

  it('starts without a session and never attempts cookie or persistent bootstrap', () => {
    const read = vi.spyOn(Storage.prototype, 'getItem');
    expect(service.state().status).toBe('initial');
    service.initialize(); service.initialize();
    expect(service.state()).toEqual({ status: 'anonymous', reason: 'initial' });
    expect(service.authenticated()).toBe(false);
    expect(backend.loadProfile).not.toHaveBeenCalled();
    expect(read).not.toHaveBeenCalled();
  });

  it('opens only the existing start route synchronously, once per user attempt', () => {
    service.login(); service.login();
    expect(browser.open).toHaveBeenCalledExactlyOnceWith('/auth/oidc/google/start', '_blank', 'popup,width=520,height=700');
    expect(service.state().status).toBe('connecting');
    expect(service.canStart()).toBe(false);
  });

  it.each(['http://industrial.example.test', 'https://other.test', 'null', 'https://industrial.example.test.evil', 'https://industrial.example.test:444'])(
    'ignores callback origin %s', origin => {
      service.login(); message(delivery(), origin);
      expect(service.state().status).toBe('connecting');
      expect(backend.loadProfile).not.toHaveBeenCalled();
    },
  );

  it('rejects a different window even on the approved origin', () => {
    service.login(); message(delivery(), browser.location.origin, {} as Window);
    expect(backend.loadProfile).not.toHaveBeenCalled();
    expect(service.authenticated()).toBe(false);
  });

  it('rejects transferred message channels instead of accepting a second delivery path', () => {
    service.login();
    const event = { data: delivery(), origin: browser.location.origin, source: popup, ports: [{}] } as unknown as MessageEvent<unknown>;
    [...listeners].forEach(listener => listener(event));
    expect(backend.loadProfile).not.toHaveBeenCalled();
    expect(service.state().status).toBe('connecting');
  });

  it.each([
    null, 'success', { kind: 'success', session_token: BEARER },
    { kind: B2B_BROWSER_BRIDGE, profile: PROFILE }, { ...delivery(), profile: PROFILE },
    { ...delivery(), token_type: 'Google' }, { ...delivery(), session_token: 'header.payload.signature' },
    { ...delivery(), session_token: 'A'.repeat(42) + 'B' }, { ...delivery(), absolute_expires_at: 'invalid' },
    { kind: B2B_BROWSER_BRIDGE, error: 'invented-success' },
  ])('ignores malformed/unauthorized callback data %#', data => {
    service.login(); message(data);
    expect(backend.loadProfile).not.toHaveBeenCalled();
    expect(service.state().status).toBe('connecting');
  });

  it('does not authenticate from a callback alone, and consumes it only once', () => {
    service.login(); message();
    expect(service.state().status).toBe('loading-profile');
    expect(service.authenticated()).toBe(false);
    expect(backend.loadProfile).toHaveBeenCalledExactlyOnceWith(BEARER);
    expect(popup.close).toHaveBeenCalledOnce();
    expect(listeners.size).toBe(0);
    message();
    expect(backend.loadProfile).toHaveBeenCalledOnce();
    profile.next(PROFILE);
    expect(service.authenticated()).toBe(true);
    expect(service.profile()).toEqual(PROFILE);
    expect(Object.isFrozen(service.profile()?.companies)).toBe(true);
  });

  it('never writes tokens to storage, public state, URL or document cookies', () => {
    const set = vi.spyOn(Storage.prototype, 'setItem');
    const cookie = vi.spyOn(Document.prototype, 'cookie', 'set');
    const push = vi.spyOn(window.history, 'pushState');
    authenticate(); service.logout(); revocation.next();
    expect(set).not.toHaveBeenCalled(); expect(cookie).not.toHaveBeenCalled(); expect(push).not.toHaveBeenCalled();
    expect(JSON.stringify(service.state())).not.toContain(BEARER);
    expect(JSON.stringify(vi.mocked(browser.open).mock.calls)).not.toContain(BEARER);
    service.refreshProfile();
    expect(backend.loadProfile).toHaveBeenCalledOnce();
    service.logout();
    expect(backend.revokeSession).toHaveBeenCalledOnce();
  });

  it.each([
    { ...PROFILE, companies: [] }, { ...PROFILE, email: 'user@company.test' },
    { ...PROFILE, companies: [PROFILE.companies[0], PROFILE.companies[0]] },
    { ...PROFILE, companies: [{ ...PROFILE.companies[0], permissions: ['admin:*'] }] },
    { ...PROFILE, userId: -1 },
  ])('refuses invalid scope without inferring membership from a domain %#', value => {
    service.login(); message(); profile.next(value);
    expect(service.state()).toEqual({ status: 'error', reason: 'invalid-response' });
    expect(service.profile()).toBeNull(); expect(service.authenticated()).toBe(false);
  });

  it.each([[401, 'denied'], [403, 'denied'], [503, 'unavailable'], [0, 'error'], [500, 'unavailable']])(
    'handles HTTP %i without retaining identity', (status, expected) => {
      service.login(); message(); profile.error(new HttpErrorResponse({ status, error: { detail: BEARER } }));
      expect(service.state().status).toBe(expected);
      expect(service.profile()).toBeNull();
      expect(service.message()).not.toContain(BEARER);
      if (status === 503) expect(service.canStart()).toBe(false);
    },
  );

  it('expires an established session on a refresh 401', () => {
    authenticate();
    const refresh = new Subject<unknown>();
    vi.mocked(backend.loadProfile).mockReturnValue(refresh);
    service.refreshProfile(); refresh.error(new HttpErrorResponse({ status: 401 }));
    expect(service.state().status).toBe('expired'); expect(service.profile()).toBeNull();
  });

  it('expires at the server absolute deadline without any further API call', () => {
    service.login(); message(delivery('2026-11-14T12:00:01Z')); profile.next(PROFILE);
    vi.advanceTimersByTime(1_000);
    expect(service.state().status).toBe('expired'); expect(service.profile()).toBeNull();
    service.logout(); expect(backend.revokeSession).not.toHaveBeenCalled();
  });

  it('rejects an already expired callback', () => {
    service.login(); message(delivery('2026-11-14T11:00:00Z'));
    expect(service.state().status).toBe('expired'); expect(backend.loadProfile).not.toHaveBeenCalled();
  });

  it('clears state immediately on logout and waits for server revocation', () => {
    authenticate(); service.logout(); service.logout();
    expect(service.state().status).toBe('signing-out'); expect(service.profile()).toBeNull();
    expect(backend.revokeSession).toHaveBeenCalledExactlyOnceWith(BEARER);
    revocation.next();
    expect(service.state()).toEqual({ status: 'anonymous', reason: 'signed-out' });
  });

  it.each([0, 403, 503])('does not claim server logout succeeded after HTTP %i', status => {
    authenticate(); service.logout(); revocation.error(new HttpErrorResponse({ status }));
    expect(service.state()).toEqual({ status: 'error', reason: 'logout-unconfirmed' });
    expect(service.profile()).toBeNull(); expect(service.authenticated()).toBe(false);
    service.logout(); expect(backend.revokeSession).toHaveBeenCalledOnce();
  });

  it('accepts logout 401 as an already invalid session', () => {
    authenticate(); service.logout(); revocation.error(new HttpErrorResponse({ status: 401 }));
    expect(service.state()).toEqual({ status: 'anonymous', reason: 'signed-out' });
  });

  it('bounds an uncertain logout without restoring the old bearer or retrying', () => {
    authenticate(); service.logout(); vi.advanceTimersByTime(10_000);
    expect(service.state()).toEqual({ status: 'error', reason: 'logout-unconfirmed' });
    service.refreshProfile(); service.logout();
    expect(backend.loadProfile).toHaveBeenCalledOnce();
    expect(backend.revokeSession).toHaveBeenCalledOnce();
  });

  it('handles a blocked popup without an HTTP request', () => {
    vi.mocked(browser.open).mockReturnValue(null);
    service.login(); expect(service.state()).toEqual({ status: 'error', reason: 'popup-blocked' });
    expect(listeners.size).toBe(0); expect(backend.loadProfile).not.toHaveBeenCalled();
  });

  it('handles a popup closed or cancelled by the user and removes listeners', () => {
    service.login(); Object.defineProperty(popup, 'closed', { value: true });
    vi.advanceTimersByTime(300);
    expect(service.state()).toEqual({ status: 'anonymous', reason: 'cancelled' });
    expect(listeners.size).toBe(0); expect(vi.getTimerCount()).toBe(0);
  });

  it('times out an abandoned popup without retry', () => {
    service.login(); vi.advanceTimersByTime(120_000);
    expect(service.state()).toEqual({ status: 'error', reason: 'timeout' });
    expect(browser.open).toHaveBeenCalledOnce(); expect(listeners.size).toBe(0);
  });

  it.each(['denied', 'cancelled', 'unavailable'])('handles the bounded callback failure %s', error => {
    service.login(); message({ kind: B2B_BROWSER_BRIDGE, error });
    expect(service.state().status).toBe(error === 'cancelled' ? 'anonymous' : error);
    expect(backend.loadProfile).not.toHaveBeenCalled(); expect(listeners.size).toBe(0);
  });

  it('cannot resurrect a session with a late profile result after cancellation', () => {
    service.login(); message(); service.cancelLogin(); profile.next(PROFILE);
    expect(service.state()).toEqual({ status: 'anonymous', reason: 'cancelled' });
    expect(service.profile()).toBeNull();
  });

  it('cleans up expired pending profile loads and empty responses', () => {
    service.login(); message(); vi.advanceTimersByTime(10_000);
    expect(service.state().status).toBe('unavailable'); expect(service.authenticated()).toBe(false);
    service.reset(); vi.mocked(backend.loadProfile).mockReturnValue(EMPTY);
    service.login(); message(); expect(service.authenticated()).toBe(false);
  });

  it('handles synchronous adapter exceptions without leaking private diagnostics', () => {
    vi.mocked(backend.loadProfile).mockImplementation(() => { throw new Error(BEARER); });
    service.login(); message();
    expect(service.state().status).toBe('unavailable'); expect(service.message()).not.toContain(BEARER);
  });

  it('accepts synchronous server responses and ignores stale callback windows', () => {
    vi.mocked(backend.loadProfile).mockReturnValue(of(PROFILE));
    service.login(); const old = popup; service.cancelLogin();
    popup = { closed: false, close: vi.fn() } as unknown as Window;
    vi.mocked(browser.open).mockReturnValue(popup);
    service.login(); message(delivery(), browser.location.origin, old);
    expect(backend.loadProfile).not.toHaveBeenCalled();
    message(); expect(service.authenticated()).toBe(true);
  });

  it('clears sensitive state when readiness is withdrawn', () => {
    service.initialize(); TestBed.tick(); authenticate();
    ready.set(false); TestBed.tick();
    expect(service.state()).toEqual({ status: 'unavailable', reason: 'preparation' });
    expect(service.profile()).toBeNull(); expect(service.canStart()).toBe(false);
  });

  it('never opens historical business routes even with a server-backed unit session', () => {
    authenticate();
    const result = TestBed.runInInjectionContext(() => preparationOnlyGuard({} as never, []));
    expect(result).toBeInstanceOf(UrlTree);
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/connexion');
  });

  it('never enables OIDC on an HTTP origin', () => {
    Object.defineProperty(browser.location, 'origin', { value: 'http://127.0.0.1:4201' });
    service.login();
    expect(service.state().status).toBe('unavailable'); expect(browser.open).not.toHaveBeenCalled();
  });
});

describe('Professional auth default wiring', () => {
  it('remains unavailable without an explicitly implemented backend adapter', () => {
    TestBed.configureTestingModule({});
    const service = TestBed.inject(ProfessionalAuthService);
    const open = vi.spyOn(window, 'open').mockReturnValue(null);
    service.login();
    expect(service.state()).toEqual({ status: 'unavailable', reason: 'preparation' });
    expect(service.authenticated()).toBe(false); expect(open).not.toHaveBeenCalled();
    open.mockRestore();
  });
});
