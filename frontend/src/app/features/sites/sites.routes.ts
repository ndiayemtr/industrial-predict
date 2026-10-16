import { Routes } from '@angular/router';

export const SITE_ROUTES: Routes = [{
  path: '', pathMatch: 'full',
  title: 'Sites industriels | Industrial Predict AI',
  data: { pageTitle: 'Sites industriels' },
  loadComponent: () => import('./pages/sites-list/sites-list.component').then(m => m.SitesListComponent)
}, {
  path: ':siteId',
  title: 'Détail du site | Industrial Predict AI',
  data: { pageTitle: 'Détail du site' },
  loadComponent: () => import('./pages/site-detail/site-detail.component').then(m => m.SiteDetailComponent)
}];
