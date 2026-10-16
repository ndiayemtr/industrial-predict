import { Routes } from '@angular/router';

export const SITE_ROUTES: Routes = [{
  path: '', pathMatch: 'full',
  title: 'Sites industriels | Industrial Predict AI',
  data: { pageTitle: 'Sites industriels' },
  loadComponent: () => import('./pages/sites-list/sites-list.component').then(m => m.SitesListComponent)
}];
