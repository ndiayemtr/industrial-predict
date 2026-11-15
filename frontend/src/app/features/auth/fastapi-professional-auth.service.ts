import { FetchBackend, HttpClient, HttpErrorResponse, HttpHeaders, HttpResponse } from '@angular/common/http';
import { computed, DestroyRef, inject, Injectable, InjectionToken, signal } from '@angular/core';
import { catchError, defer, map, Observable, Subscription, take, throwError, throwIfEmpty, timeout } from 'rxjs';
import {
  authExactKeys, authJsonRecord, B2B_BROWSER_BRIDGE, isApplicationSessionToken, parseProfessionalProfile,
  PROFESSIONAL_AUTH_WINDOW, ProfessionalAuthBackend, ProfessionalProfile,
} from './professional-auth.model';

export const AUTH_ME_PATH = '/api/v1/auth/me';
export const AUTH_LOGOUT_PATH = '/api/v1/auth/logout';

export interface ProfessionalAuthConfiguration {
  readonly origin: string;
  readonly bridgeVersion: typeof B2B_BROWSER_BRIDGE;
}

/**
 * Trusted integration port for a REAL server qualification, not an enable flag.
 * FastApiAuthReadinessVerifier checks the auth-only server's real readiness
 * contract. Neither /health, OpenAPI nor an unauthenticated /me 401 is proof.
 * The deployment configuration remains absent by default; of(undefined) is
 * only a unit double, never an activation procedure.
 */
export interface ProfessionalAuthReadinessVerifier {
  verify(configuration: Readonly<ProfessionalAuthConfiguration>): Observable<void>;
}

export const PROFESSIONAL_AUTH_CONFIGURATION = new InjectionToken<ProfessionalAuthConfiguration | null>(
  'Explicit professional auth deployment', { providedIn: 'root', factory: () => null },
);
export const PROFESSIONAL_AUTH_READINESS_VERIFIER = new InjectionToken<ProfessionalAuthReadinessVerifier | null>(
  'Qualified server profile verification', { providedIn: 'root', factory: () => null },
);

// Dedicated Fetch transport: no global interceptor sees or spreads this bearer.
// The application's legacy HttpClient/XHR configuration remains unchanged.
export const PROFESSIONAL_AUTH_HTTP = new InjectionToken<HttpClient>('Professional auth HTTP', {
  providedIn: 'root', factory: () => new HttpClient(new FetchBackend()),
});

@Injectable({ providedIn: 'root' })
export class FastApiProfessionalAuthBackend implements ProfessionalAuthBackend {
  get bridgeVersion(): typeof B2B_BROWSER_BRIDGE { return B2B_BROWSER_BRIDGE; }
  private readonly http = inject(PROFESSIONAL_AUTH_HTTP);
  private readonly browser = inject(PROFESSIONAL_AUTH_WINDOW);
  private readonly configured = inject(PROFESSIONAL_AUTH_CONFIGURATION);
  private readonly verifier = inject(PROFESSIONAL_AUTH_READINESS_VERIFIER);
  private readonly current = signal<'closed' | 'checking' | 'ready' | 'unavailable'>('closed');
  private verification: Subscription | null = null;
  readonly availability = this.current.asReadonly();
  readonly ready = computed(() => this.current() === 'ready' && this.configuration() !== null);

  constructor() {
    const config = this.configuration();
    if (config && this.verifier) {
      this.current.set('checking');
      this.verification = defer(() => this.verifier!.verify(config)).pipe(
        take(1), throwIfEmpty(), timeout(10_000),
      ).subscribe({
        next: result => this.current.set(result === undefined ? 'ready' : 'unavailable'),
        error: () => this.current.set('unavailable'),
      });
    }
    inject(DestroyRef).onDestroy(() => { this.verification?.unsubscribe(); this.current.set('closed'); });
  }

  private configuration(): Readonly<ProfessionalAuthConfiguration> | null {
    const value: unknown = this.configured;
    if (!authJsonRecord(value) || !authExactKeys(value, ['origin', 'bridgeVersion']) || value['bridgeVersion'] !== B2B_BROWSER_BRIDGE
      || typeof value['origin'] !== 'string' || !this.browser) return null;
    try {
      const origin = new URL(value['origin']);
      if (origin.protocol !== 'https:' || origin.origin !== value['origin'] || origin.origin !== this.browser.location.origin) return null;
      return Object.freeze({ origin: origin.origin, bridgeVersion: B2B_BROWSER_BRIDGE });
    } catch { return null; }
  }

  loadProfile(sessionToken: string): Observable<ProfessionalProfile> {
    return this.request(sessionToken, AUTH_ME_PATH, (url, headers) => this.http.get<unknown>(url, {
      headers, observe: 'response', credentials: 'omit', mode: 'same-origin', redirect: 'error',
      cache: 'no-store', referrer: new URL(url).origin + '/', referrerPolicy: 'same-origin', transferCache: false,
    }).pipe(map(response => {
      this.response(response, url, 200);
      if (response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== 'application/json') throw new TypeError('Invalid auth response');
      return parseProfessionalProfile(response.body);
    })));
  }

  revokeSession(sessionToken: string): Observable<void> {
    return this.request(sessionToken, AUTH_LOGOUT_PATH, (url, headers) => this.http.post<unknown>(url, null, {
      headers, observe: 'response', credentials: 'omit', mode: 'same-origin', redirect: 'error',
      // Keep the browser-generated same-origin Origin required by logout.
      // A root-only referrer discloses no page path, query or session data.
      cache: 'no-store', referrer: new URL(url).origin + '/', referrerPolicy: 'same-origin', transferCache: false,
    }).pipe(map(response => {
      this.response(response, url, 204);
      if (response.body !== null) throw new TypeError('Invalid logout response');
    })));
  }

  private response(response: HttpResponse<unknown>, url: string, status: number): void {
    if (response.status !== status || response.redirected || (response.url !== null && response.url !== url)
      || !response.headers.get('Cache-Control')?.split(',').some(item => item.trim().toLowerCase() === 'no-store')) {
      throw new TypeError('Invalid auth response');
    }
  }

  private request<T>(sessionToken: string, path: string,
      operation: (url: string, headers: HttpHeaders) => Observable<T>): Observable<T> {
    return defer(() => {
      const config = this.configuration();
      if (!this.ready() || !config) return throwError(() => this.failure(503));
      if (!isApplicationSessionToken(sessionToken)) return throwError(() => this.failure(401));
      const url = new URL(path, config.origin).href;
      // Headers are request-local, never default headers or browser storage.
      const headers = new HttpHeaders({ Authorization: 'Bearer ' + sessionToken, Accept: 'application/json' });
      return operation(url, headers).pipe(timeout(8_000), catchError(error => {
        const status = error instanceof HttpErrorResponse ? error.status : 503;
        if (status !== 401 && status !== 403) this.current.set('unavailable');
        // Do not retain/forward response bodies, headers or diagnostics that
        // could reflect a token, nor redirect URLs chosen by another service.
        return throwError(() => this.failure(status));
      }));
    });
  }

  private failure(status: number): HttpErrorResponse {
    const code = status === 0 ? 0 : status === 401 ? 401 : status === 403 ? 403 : 503;
    return new HttpErrorResponse({ status: code, statusText: code === 401 ? 'AUTHENTICATION_REQUIRED'
      : code === 403 ? 'B2B_FORBIDDEN' : 'B2B_RUNTIME_UNAVAILABLE' });
  }
}
