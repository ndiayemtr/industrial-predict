import { inject } from '@angular/core';
import { CanMatchFn, Router } from '@angular/router';

// UI closure only, not authentication. A future server-backed session guard
// requires separate review; no client flag, domain or token can enable this one.
export const preparationOnlyGuard: CanMatchFn = () => inject(Router).createUrlTree(['/connexion']);
