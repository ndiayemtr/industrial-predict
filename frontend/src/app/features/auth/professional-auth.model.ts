import { InjectionToken, Signal, inject } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { Observable } from 'rxjs';

// These two paths exist in b2b_login.py. The callback belongs to FastAPI,
// not to the Angular router. Never forward its code/state from Angular.
export const GOOGLE_OIDC_START_PATH = '/auth/oidc/google/start';
export const GOOGLE_OIDC_CALLBACK_PATH = '/auth/oidc/google/callback';

// Emitted by FastAPI only with the explicitly qualified browser auth profile.
export const B2B_BROWSER_BRIDGE = 'industrial-predict:b2b-session:v1';
export const PROFESSIONAL_PERMISSIONS = [
  'companies:read', 'assets:read', 'measurements:read', 'predictions:read',
  'predictions:analyze', 'maintenance:write', 'memberships:manage',
] as const;
export type ProfessionalPermission = typeof PROFESSIONAL_PERMISSIONS[number];

/** Exact /api/v1/auth/me DTO; names can be null. Grants come only from the server. */
export interface ProfessionalProfile {
  readonly userId: number;
  readonly displayName: string | null;
  readonly companies: readonly {
    readonly companyId: number;
    readonly displayName: string | null;
    readonly permissions: readonly ProfessionalPermission[];
  }[];
}

export type ProfessionalAuthState =
  | { readonly status: 'initial' }
  | { readonly status: 'unavailable'; readonly reason: 'preparation' | 'service' }
  | { readonly status: 'anonymous'; readonly reason: 'initial' | 'cancelled' | 'signed-out' }
  | { readonly status: 'connecting' | 'loading-profile' | 'signing-out' }
  | { readonly status: 'authenticated'; readonly profile: ProfessionalProfile; readonly expiresAt: string }
  | { readonly status: 'denied' | 'expired' }
  | { readonly status: 'error'; readonly reason: 'network' | 'invalid-response' | 'popup-blocked' | 'timeout' | 'logout-unconfirmed' };

/**
 * No callback data or email domain may supply identity/companies/permissions.
 * The concrete adapter uses only the two qualified FastAPI auth routes.
 */
export interface ProfessionalAuthBackend {
  readonly bridgeVersion: typeof B2B_BROWSER_BRIDGE;
  readonly ready: Signal<boolean>;
  readonly availability?: Signal<'closed' | 'checking' | 'ready' | 'unavailable'>;
  loadProfile(sessionToken: string): Observable<unknown>;
  revokeSession(sessionToken: string): Observable<void>;
}

// No runtime flag, URL parameter, storage entry or healthy /health can enable OIDC.
export const PROFESSIONAL_AUTH_BACKEND = new InjectionToken<ProfessionalAuthBackend | null>(
  'Professional auth backend', { providedIn: 'root', factory: () => null },
);
export const PROFESSIONAL_AUTH_WINDOW = new InjectionToken<Window | null>(
  'Professional auth window', { providedIn: 'root', factory: () => inject(DOCUMENT).defaultView },
);

export function authJsonRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}
export function authExactKeys(value: Record<string, unknown>, expected: string[]): boolean {
  return Object.keys(value).length === expected.length && expected.every(key => Object.hasOwn(value, key));
}
export function isApplicationSessionToken(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]$/.test(value);
}
function positiveId(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}
function label(value: unknown): value is string | null {
  return value === null || (typeof value === 'string' && value.trim().length > 0 && value.length <= 200);
}
export function parseProfessionalProfile(value: unknown): ProfessionalProfile {
  if (!authJsonRecord(value) || !authExactKeys(value, ['userId', 'displayName', 'companies'])
    || !positiveId(value['userId']) || !label(value['displayName']) || !Array.isArray(value['companies'])
    || value['companies'].length === 0) throw new TypeError('Invalid server profile');
  const seen = new Set<number>();
  const companies = value['companies'].map((company: unknown) => {
    if (!authJsonRecord(company) || !authExactKeys(company, ['companyId', 'displayName', 'permissions'])
      || !positiveId(company['companyId']) || seen.has(company['companyId']) || !label(company['displayName'])
      || !Array.isArray(company['permissions'])
      || company['permissions'].some((p: unknown) => !PROFESSIONAL_PERMISSIONS.some(allowed => p === allowed))
      || new Set(company['permissions']).size !== company['permissions'].length) throw new TypeError('Invalid server scope');
    seen.add(company['companyId']);
    return Object.freeze({ companyId: company['companyId'], displayName: company['displayName'],
      permissions: Object.freeze([...company['permissions']] as ProfessionalPermission[]) });
  });
  return Object.freeze({ userId: value['userId'], displayName: value['displayName'], companies: Object.freeze(companies) });
}
