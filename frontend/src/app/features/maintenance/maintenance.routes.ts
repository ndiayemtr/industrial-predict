import { Routes } from '@angular/router';
export const MAINTENANCE_ROUTES: Routes = [
  { path: '', pathMatch: 'full', title: 'Maintenance | Industrial Predict AI', data: { pageTitle: 'Maintenance' },
    loadComponent: () => import('./pages/maintenance-list/maintenance-list.component').then(m => m.MaintenanceListComponent) }
];
