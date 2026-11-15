import { HttpErrorResponse } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { catchError, defer, map, Observable, throwError, timeout } from 'rxjs';
import { authExactKeys, authJsonRecord, B2B_BROWSER_BRIDGE, PROFESSIONAL_AUTH_WINDOW } from './professional-auth.model';
import { PROFESSIONAL_AUTH_HTTP } from './fastapi-professional-auth.service';
import type { ProfessionalAuthConfiguration, ProfessionalAuthReadinessVerifier } from './fastapi-professional-auth.service';

export const AUTH_READINESS_PATH = '/api/v1/auth/readiness';

/** A fresh local server qualification, never a frontend enable flag or a /me 401. */
@Injectable({ providedIn: 'root' })
export class FastApiAuthReadinessVerifier implements ProfessionalAuthReadinessVerifier {
  private readonly http = inject(PROFESSIONAL_AUTH_HTTP);
  private readonly browser = inject(PROFESSIONAL_AUTH_WINDOW);

  verify(configuration: Readonly<ProfessionalAuthConfiguration>): Observable<void> {
    return defer(() => {
      if (!authJsonRecord(configuration) || !authExactKeys(configuration, ['origin', 'bridgeVersion'])
        || configuration.bridgeVersion !== B2B_BROWSER_BRIDGE || !this.browser) throw new TypeError();
      const origin = new URL(configuration.origin);
      if (origin.protocol !== 'https:' || origin.origin !== configuration.origin
        || origin.origin !== this.browser.location.origin) throw new TypeError();
      const url = new URL(AUTH_READINESS_PATH, origin).href;
      return this.http.get<unknown>(url, {
        observe: 'response', headers: { Accept: 'application/json' }, credentials: 'omit', mode: 'same-origin',
        redirect: 'error', cache: 'no-store', transferCache: false,
        referrer: origin.origin + '/', referrerPolicy: 'same-origin',
      }).pipe(timeout(8_000), map(response => {
        const body = response.body;
        if (response.status !== 200 || response.redirected || response.url !== url
          || response.headers.get('Content-Type')?.split(';')[0].trim().toLowerCase() !== 'application/json'
          || !response.headers.get('Cache-Control')?.split(',').some(item => item.trim().toLowerCase() === 'no-store')
          || !authJsonRecord(body) || !authExactKeys(body, ['status', 'profile', 'bridgeVersion'])
          || body['status'] !== 'ready' || body['profile'] !== 'auth-only' || body['bridgeVersion'] !== B2B_BROWSER_BRIDGE) {
          throw new TypeError();
        }
      }));
    }).pipe(catchError(() => throwError(() => new HttpErrorResponse({ status: 503, statusText: 'B2B_RUNTIME_UNAVAILABLE' }))));
  }
}
