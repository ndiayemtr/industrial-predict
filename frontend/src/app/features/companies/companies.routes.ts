import { Routes } from '@angular/router';

export const COMPANY_ROUTES: Routes = [{
  path: '',
  pathMatch: 'full',
  title: 'Entreprises | Industrial Predict AI',
  data: { pageTitle: 'Entreprises' },
  loadComponent: () => import('./pages/companies-list/companies-list.component').then(m => m.CompaniesListComponent)
}];
