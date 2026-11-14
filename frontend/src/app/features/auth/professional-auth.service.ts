import { HttpErrorResponse } from '@angular/common/http';
import { computed, DestroyRef, effect, inject, Injectable, signal } from '@angular/core';
import { defer, Subscription, take, throwIfEmpty, timeout } from 'rxjs';
import {
  B2B_BROWSER_BRIDGE, GOOGLE_OIDC_START_PATH, PROFESSIONAL_AUTH_BACKEND,
  PROFESSIONAL_AUTH_WINDOW, PROFESSIONAL_PERMISSIONS, ProfessionalAuthState,
  ProfessionalPermission, ProfessionalProfile,
} from './professional-auth.model';
import { PROFESSIONAL_CONNECTION_PREPARATION } from './professional-connection.model';

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    && (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}
function keys(value: Record<string, unknown>, expected: string[]): boolean {
  return Object.keys(value).length === expected.length && expected.every(key => Object.hasOwn(value, key));
}
function positiveId(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value > 0;
}
function label(value: unknown): value is string | null {
  return value === null || (typeof value === 'string' && value.trim().length > 0 && value.length <= 200);
}

function profileProjection(value: unknown): ProfessionalProfile {
  if (!record(value) || !keys(value, ['userId', 'displayName', 'companies'])
    || !positiveId(value['userId']) || !label(value['displayName']) || !Array.isArray(value['companies'])
    || value['companies'].length === 0) throw new TypeError('Invalid server profile');
  const seen = new Set<number>();
  const companies = value['companies'].map((company: unknown) => {
    if (!record(company) || !keys(company, ['companyId', 'displayName', 'permissions'])
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

@Injectable({ providedIn: 'root' })
export class ProfessionalAuthService {
  private readonly backend = inject(PROFESSIONAL_AUTH_BACKEND);
  private readonly browser = inject(PROFESSIONAL_AUTH_WINDOW);
  private readonly current = signal<ProfessionalAuthState>({ status: 'initial' });
  private initialized = false;
  private token: string | null = null;
  private expiresAt = 0;
  private generation = 0;
  private pending: Subscription | null = null;
  private popup: Window | null = null;
  private messageListener: ((event: MessageEvent<unknown>) => void) | null = null;
  private poll: number | null = null;
  private loginDeadline: number | null = null;
  private expiryTimer: number | null = null;

  readonly state = this.current.asReadonly();
  readonly backendReady = computed(() => {
    if (!this.backend || this.backend.bridgeVersion !== B2B_BROWSER_BRIDGE || !this.backend.ready() || !this.browser) return false;
    try {
      const origin = new URL(this.browser.location.origin);
      return origin.protocol === 'https:' && origin.origin === this.browser.location.origin;
    } catch { return false; }
  });
  readonly busy = computed(() => ['connecting', 'loading-profile', 'signing-out'].includes(this.state().status));
  readonly authenticated = computed(() => this.state().status === 'authenticated');
  readonly profile = computed(() => { const state = this.state(); return state.status === 'authenticated' ? state.profile : null; });
  readonly canStart = computed(() => this.backendReady() && !this.busy() && !this.authenticated()
    && !['initial', 'unavailable'].includes(this.state().status));
  readonly message = computed(() => {
    const state = this.state();
    switch (state.status) {
      case 'initial': return 'Préparation de la connexion professionnelle…';
      case 'unavailable': return state.reason === 'preparation' ? PROFESSIONAL_CONNECTION_PREPARATION.message : 'Le service d’authentification est indisponible. Réessayez plus tard.';
      case 'connecting': return 'Terminez la connexion Google dans la fenêtre ouverte.';
      case 'loading-profile': return 'Vérification de votre session et de vos entreprises autorisées…';
      case 'authenticated': return 'Votre session professionnelle est ouverte. Les espaces métier restent fermés.';
      case 'denied': return 'Authentification refusée. Votre compte ou vos autorisations ne permettent pas cet accès.';
      case 'expired': return 'Votre session a expiré. Connectez-vous à nouveau.';
      case 'signing-out': return 'Déconnexion en cours…';
      case 'anonymous': return state.reason === 'cancelled' ? 'Connexion annulée.' : state.reason === 'signed-out' ? 'Vous êtes déconnecté.' : 'Connectez-vous avec votre compte professionnel.';
      case 'error': {
        const messages = {
          network: 'La connexion au service a échoué. Vérifiez votre réseau.',
          'invalid-response': 'La session n’a pas pu être vérifiée. Aucun accès n’a été ouvert.',
          'popup-blocked': 'La fenêtre de connexion a été bloquée. Autorisez les fenêtres de connexion puis réessayez.',
          timeout: 'La connexion a pris trop de temps. Vous pouvez réessayer.',
          'logout-unconfirmed': 'La session locale a été effacée, mais la déconnexion serveur n’a pas pu être confirmée.',
        };
        return messages[state.reason];
      }
    }
  });

  constructor() {
    let previousReady: boolean | null = null;
    effect(() => {
      const ready = this.backendReady();
      const previous = previousReady;
      previousReady = ready;
      if (!ready && this.initialized) {
        this.clear();
        this.current.set({ status: 'unavailable', reason: 'preparation' });
      } else if (ready && previous === false && this.initialized) {
        this.clear();
        this.current.set({ status: 'anonymous', reason: 'initial' });
      }
    });
    inject(DestroyRef).onDestroy(() => this.clear());
  }

  initialize(): void {
    if (this.initialized) return;
    this.initialized = true;
    // Reload starts without a bearer: no cookie bootstrap or persistent storage.
    this.current.set(this.backendReady() ? { status: 'anonymous', reason: 'initial' } : { status: 'unavailable', reason: 'preparation' });
  }

  login(): void {
    this.initialize();
    if (!this.canStart() || !this.browser) return;
    this.clear();
    this.current.set({ status: 'connecting' });
    try {
      // Synchronous within the user's click; never fetch the redirect with HTTP.
      this.popup = this.browser.open(GOOGLE_OIDC_START_PATH, '_blank', 'popup,width=520,height=700');
    } catch { this.popup = null; }
    if (!this.popup) { this.fail({ status: 'error', reason: 'popup-blocked' }); return; }
    this.messageListener = event => this.receive(event);
    this.browser.addEventListener('message', this.messageListener);
    this.poll = this.browser.setInterval(() => {
      if (this.popup?.closed) this.cancelLogin();
    }, 300);
    this.loginDeadline = this.browser.setTimeout(() => this.fail({ status: 'error', reason: 'timeout' }), 120_000);
  }

  cancelLogin(): void {
    if (!['connecting', 'loading-profile'].includes(this.state().status)) return;
    this.fail({ status: 'anonymous', reason: 'cancelled' });
  }

  refreshProfile(): void {
    if (!this.authenticated() || !this.token || !this.backendReady()) return;
    this.fetchProfile(true);
  }

  logout(): void {
    if (!this.authenticated() || !this.token || !this.backend) return;
    const bearer = this.token;
    this.clear(); // Profile and bearer vanish before the network operation.
    this.current.set({ status: 'signing-out' });
    const generation = this.generation;
    const request = new Subscription();
    this.pending = request;
    request.add(defer(() => this.backend!.revokeSession(bearer)).pipe(take(1), throwIfEmpty(), timeout(10_000)).subscribe({
      next: () => {
        if (generation === this.generation) this.fail({ status: 'anonymous', reason: 'signed-out' });
      },
      error: error => {
        if (generation !== this.generation) return;
        this.fail(error instanceof HttpErrorResponse && error.status === 401
          ? { status: 'anonymous', reason: 'signed-out' } : { status: 'error', reason: 'logout-unconfirmed' });
      },
    }));
  }

  /** Clears browser-held state only; never claims server-side revocation. */
  reset(): void {
    this.clear();
    this.current.set(this.backendReady() ? { status: 'anonymous', reason: 'initial' } : { status: 'unavailable', reason: 'preparation' });
  }

  private receive(event: MessageEvent<unknown>): void {
    if (this.state().status !== 'connecting' || !this.popup || !this.browser || !this.backendReady()
      || event.origin !== this.browser.location.origin || event.source !== this.popup || event.ports.length !== 0) return;
    const data = event.data;
    if (!record(data) || data['kind'] !== B2B_BROWSER_BRIDGE) return;
    if (keys(data, ['kind', 'error'])) {
      if (data['error'] === 'denied') this.fail({ status: 'denied' });
      else if (data['error'] === 'cancelled') this.cancelLogin();
      else if (data['error'] === 'unavailable') this.fail({ status: 'unavailable', reason: 'service' });
      return;
    }
    if (!keys(data, ['kind', 'token_type', 'session_token', 'absolute_expires_at']) || data['token_type'] !== 'Bearer'
      || typeof data['session_token'] !== 'string' || !/^[A-Za-z0-9_-]{42}[AEIMQUYcgkosw048]$/.test(data['session_token'])
      || typeof data['absolute_expires_at'] !== 'string' || !/^\d{4}-\d{2}-\d{2}T.+(?:Z|\+00:00)$/.test(data['absolute_expires_at'])) return;
    const expires = Date.parse(data['absolute_expires_at']);
    if (!Number.isFinite(expires)) return;
    if (expires <= Date.now()) { this.fail({ status: 'expired' }); return; }
    this.closePopup(); // One callback per attempt; duplicates cannot replace it.
    this.token = data['session_token'];
    this.expiresAt = expires;
    this.armExpiry();
    this.fetchProfile(false);
  }

  private fetchProfile(wasAuthenticated: boolean): void {
    const bearer = this.token;
    if (!bearer || !this.backend || !this.backendReady()) return;
    const generation = ++this.generation;
    this.pending?.unsubscribe();
    const request = new Subscription();
    this.pending = request;
    this.current.set({ status: 'loading-profile' });
    request.add(defer(() => this.backend!.loadProfile(bearer)).pipe(take(1), throwIfEmpty(), timeout(10_000)).subscribe({
      next: value => {
        if (generation !== this.generation) return;
        if (Date.now() >= this.expiresAt) { this.fail({ status: 'expired' }); return; }
        try {
          this.current.set({ status: 'authenticated', profile: profileProjection(value), expiresAt: new Date(this.expiresAt).toISOString() });
        } catch { this.fail({ status: 'error', reason: 'invalid-response' }); }
      },
      error: error => {
        if (generation !== this.generation) return;
        if (error instanceof HttpErrorResponse) {
          if (error.status === 401) { this.fail(wasAuthenticated ? { status: 'expired' } : { status: 'denied' }); return; }
          if (error.status === 403) { this.fail({ status: 'denied' }); return; }
          if (error.status === 503) { this.fail({ status: 'unavailable', reason: 'service' }); return; }
          if (error.status === 0) { this.fail({ status: 'error', reason: 'network' }); return; }
        }
        this.fail({ status: 'unavailable', reason: 'service' });
      },
    }));
  }

  private armExpiry(): void {
    if (!this.browser) return;
    this.expiryTimer = this.browser.setTimeout(() => {
      if (Date.now() >= this.expiresAt) this.fail({ status: 'expired' });
      else this.armExpiry();
    }, Math.min(this.expiresAt - Date.now(), 2_147_483_647));
  }

  private fail(state: ProfessionalAuthState): void { this.clear(); this.current.set(state); }

  private closePopup(): void {
    if (this.browser && this.messageListener) this.browser.removeEventListener('message', this.messageListener);
    this.messageListener = null;
    if (this.poll !== null) this.browser?.clearInterval(this.poll);
    if (this.loginDeadline !== null) this.browser?.clearTimeout(this.loginDeadline);
    this.poll = this.loginDeadline = null;
    try { this.popup?.close(); } catch { /* Local cleanup cannot revoke a server session. */ }
    this.popup = null;
  }

  private clear(): void {
    ++this.generation;
    this.pending?.unsubscribe();
    this.pending = null;
    this.closePopup();
    if (this.expiryTimer !== null) this.browser?.clearTimeout(this.expiryTimer);
    this.expiryTimer = null;
    this.token = null;
    this.expiresAt = 0;
  }
}
