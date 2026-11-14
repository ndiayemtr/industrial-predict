import { InjectionToken, Signal, inject } from '@angular/core';
import { DOCUMENT } from '@angular/common';
import { Observable } from 'rxjs';

// These two paths exist in b2b_login.py. The callback belongs to FastAPI,
// not to the Angular router. Never forward its code/state from Angular.
export const GOOGLE_OIDC_START_PATH = '/auth/oidc/google/start';
export const GOOGLE_OIDC_CALLBACK_PATH = '/auth/oidc/google/callback';

// Proposed browser bridge contract, NOT currently emitted by FastAPI.
export const B2B_BROWSER_BRIDGE = 'industrial-predict:b2b-session:v1';
export const PROFESSIONAL_PERMISSIONS = [
  'companies:read', 'assets:read', 'measurements:read', 'predictions:read',
  'predictions:analyze', 'maintenance:write', 'memberships:manage',
] as const;
export type ProfessionalPermission = typeof PROFESSIONAL_PERMISSIONS[number];

/** Frontend projection supplied exclusively by a future authenticated server adapter. */
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
 * Integration port, not an existing API. No guessed /me or /logout endpoint.
 * A future adapter must map actual server DTOs and use the bearer only for its
 * explicitly approved HTTPS auth requests. Neither callback data nor email
 * domains may supply identity/companies/permissions.
 */
export interface ProfessionalAuthBackend {
  readonly bridgeVersion: typeof B2B_BROWSER_BRIDGE;
  readonly ready: Signal<boolean>;
  loadProfile(sessionToken: string): Observable<unknown>;
  revokeSession(sessionToken: string): Observable<void>;
}

// No runtime flag, URL parameter, storage entry or healthy /health can enable OIDC.
export const PROFESSIONAL_AUTH_BACKEND = new InjectionToken<ProfessionalAuthBackend | null>(
  'Professional auth backend (not yet available)', { providedIn: 'root', factory: () => null },
);
export const PROFESSIONAL_AUTH_WINDOW = new InjectionToken<Window | null>(
  'Professional auth window', { providedIn: 'root', factory: () => inject(DOCUMENT).defaultView },
);
