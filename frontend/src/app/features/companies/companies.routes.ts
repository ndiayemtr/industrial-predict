import { Routes } from '@angular/router';

export const COMPANY_ROUTES: Routes = [{
  path: '',
  pathMatch: 'full',
  title: 'Entreprises | Industrial Predict AI',
  data: { pageTitle: 'Entreprises' },
  loadComponent: () => import('./pages/companies-list/companies-list.component').then(m => m.CompaniesListComponent)
}, {
  path: 'new',
  title: 'Nouvelle entreprise | Industrial Predict AI',
  data: { pageTitle: 'Nouvelle entreprise' },
  canDeactivate: [(component: { canLeave(): boolean }) => component.canLeave()],
  loadComponent: () => import('./pages/company-form/company-form-page.component').then(m => m.CompanyFormPageComponent)
}, {
  path: ':companyId',
  title: 'Détail entreprise | Industrial Predict AI',
  data: { pageTitle: 'Détail entreprise' },
  loadComponent: () => import('./pages/company-detail/company-detail.component').then(m => m.CompanyDetailComponent)
}];
