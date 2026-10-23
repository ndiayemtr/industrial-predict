import { Routes } from '@angular/router';
export const MAINTENANCE_ROUTES: Routes = [
  { path: '', pathMatch: 'full', title: 'Maintenance | Industrial Predict AI', data: { pageTitle: 'Maintenance' },
    loadComponent: () => import('./pages/maintenance-list/maintenance-list.component').then(m => m.MaintenanceListComponent) },
  { path: ':maintenanceId', pathMatch: 'full', title: 'Détail intervention | Industrial Predict AI', data: { pageTitle: 'Détail intervention' },
    loadComponent: () => import('./pages/maintenance-detail/maintenance-detail.component').then(m => m.MaintenanceDetailComponent) }
];
