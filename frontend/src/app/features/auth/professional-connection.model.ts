/** Presentation contract only; never a session or an authorization decision. */
export interface ProfessionalConnectionPreparation {
  readonly status: 'unavailable';
  readonly provider: 'google';
  readonly authenticated: false;
  readonly message: string;
}

export const PROFESSIONAL_CONNECTION_PREPARATION: ProfessionalConnectionPreparation = Object.freeze({
  status: 'unavailable',
  provider: 'google',
  authenticated: false,
  message: 'La connexion professionnelle sera prochainement disponible.',
});
