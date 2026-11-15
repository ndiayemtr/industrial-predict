import { HttpClient, HttpResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { of } from 'rxjs';
import { vi } from 'vitest';
import { AUTH_READINESS_PATH, FastApiAuthReadinessVerifier } from './fastapi-auth-readiness.service';
import {
  FastApiProfessionalAuthBackend, PROFESSIONAL_AUTH_CONFIGURATION, PROFESSIONAL_AUTH_HTTP,
  PROFESSIONAL_AUTH_READINESS_VERIFIER,
} from './fastapi-professional-auth.service';
import { B2B_BROWSER_BRIDGE, PROFESSIONAL_AUTH_BACKEND, PROFESSIONAL_AUTH_WINDOW } from './professional-auth.model';
import { ProfessionalAuthService } from './professional-auth.service';

const ORIGIN = 'https://login.test';
const CONFIG = { origin: ORIGIN, bridgeVersion: B2B_BROWSER_BRIDGE } as const;
const PROOF = { status: 'ready', profile: 'auth-only', bridgeVersion: B2B_BROWSER_BRIDGE };
const HEADERS = { 'Cache-Control': 'no-store', 'Content-Type': 'application/json' };

describe('ACT-1 server-qualified readiness (synthetic HTTP only)', () => {
  let http: HttpTestingController;
  let auth: ProfessionalAuthService;
  let browser: Window;

  beforeEach(() => {
    browser = { location: { origin: ORIGIN }, open: vi.fn(() => null) } as unknown as Window;
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting(),
      { provide: PROFESSIONAL_AUTH_HTTP, useExisting: HttpClient },
      { provide: PROFESSIONAL_AUTH_WINDOW, useValue: browser },
      { provide: PROFESSIONAL_AUTH_CONFIGURATION, useValue: CONFIG },
      { provide: PROFESSIONAL_AUTH_BACKEND, useExisting: FastApiProfessionalAuthBackend },
      { provide: PROFESSIONAL_AUTH_READINESS_VERIFIER, useExisting: FastApiAuthReadinessVerifier },
    ] });
  });
  function start(): void {
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(ProfessionalAuthService); auth.initialize(); TestBed.tick();
  }
  afterEach(() => { auth?.reset(); http?.verify(); vi.restoreAllMocks(); });

  it('remains completely closed without explicit deployment configuration', () => {
    TestBed.overrideProvider(PROFESSIONAL_AUTH_CONFIGURATION, { useValue: null });
    start(); auth.login();
    http.expectNone(() => true); expect(browser.open).not.toHaveBeenCalled();
    expect(auth.backendReady()).toBe(false); expect(auth.authenticated()).toBe(false);
  });

  it('requires a fresh exact server response before enabling a user-initiated popup', () => {
    start(); expect(auth.canStart()).toBe(false); auth.login();
    expect(browser.open).not.toHaveBeenCalled();
    const req = http.expectOne(ORIGIN + AUTH_READINESS_PATH);
    expect(req.request.method).toBe('GET'); expect(req.request.body).toBeNull();
    expect(req.request.params.keys()).toEqual([]);
    expect(req.request.headers.has('Authorization')).toBe(false);
    expect(req.request.headers.has('Cookie')).toBe(false);
    expect(req.request.credentials).toBe('omit'); expect(req.request.mode).toBe('same-origin');
    expect(req.request.redirect).toBe('error'); expect(req.request.cache).toBe('no-store');
    expect(req.request.transferCache).toBe(false); expect(req.request.referrer).toBe(ORIGIN + '/');
    req.flush(PROOF, { headers: HEADERS }); TestBed.tick();
    expect(auth.backendReady()).toBe(true); expect(auth.canStart()).toBe(true);
    expect(auth.authenticated()).toBe(false); expect(auth.profile()).toBeNull();
    expect(browser.open).not.toHaveBeenCalled();
    auth.login();
    expect(browser.open).toHaveBeenCalledExactlyOnceWith('/auth/oidc/google/start', '_blank', 'popup,width=520,height=700');
    http.expectNone(() => true);
  });

  it.each([401, 403, 404, 503])('keeps Google closed on server HTTP %i without a fallback', status => {
    start(); http.expectOne(ORIGIN + AUTH_READINESS_PATH).flush({ detail: 'private-server-diagnostic' },
      { status, statusText: 'Failure' }); TestBed.tick();
    expect(auth.state()).toEqual({ status: 'unavailable', reason: 'service' });
    auth.login(); expect(browser.open).not.toHaveBeenCalled(); http.expectNone(() => true);
    expect(auth.message()).not.toContain('private-server-diagnostic');
  });

  it('handles network failure without a retry or bearer bootstrap', () => {
    start(); http.expectOne(ORIGIN + AUTH_READINESS_PATH).error(new ProgressEvent('error')); TestBed.tick();
    expect(auth.canStart()).toBe(false); expect(auth.profile()).toBeNull(); http.expectNone(() => true);
  });

  it.each([true, { status: 'healthy' }, { ...PROOF, profile: 'b2b-preparation' },
    { ...PROOF, bridgeVersion: 'other' }, { ...PROOF, userId: 17 }, { ...PROOF, status: 'unavailable' }])(
    'does not mistake a flag, health response or incompatible profile for readiness %#', body => {
      start(); http.expectOne(ORIGIN + AUTH_READINESS_PATH).flush(body, { headers: HEADERS }); TestBed.tick();
      expect(auth.backendReady()).toBe(false); expect(auth.authenticated()).toBe(false);
    },
  );

  it('rejects a cached response even when its payload claims readiness', () => {
    start(); http.expectOne(ORIGIN + AUTH_READINESS_PATH).flush(PROOF, { headers: { 'Content-Type': 'application/json' } });
    TestBed.tick(); expect(auth.canStart()).toBe(false);
  });

  it.each(['https://foreign.test', 'http://login.test'])('refuses origin %s before any request', origin => {
    TestBed.overrideProvider(PROFESSIONAL_AUTH_CONFIGURATION, { useValue: { ...CONFIG, origin } });
    start(); http.expectNone(() => true); expect(auth.canStart()).toBe(false);
  });

  it('redacts a verifier response whose redirect/URL does not match the approved request', () => {
    TestBed.overrideProvider(PROFESSIONAL_AUTH_HTTP, { useValue: { get: () => of(new HttpResponse({
      status: 200, body: PROOF, headers: undefined, redirected: true, url: 'https://foreign.test/private',
    })) } });
    start(); TestBed.tick(); expect(auth.backendReady()).toBe(false); expect(auth.profile()).toBeNull();
    expect(auth.message()).not.toContain('private');
  });
});
