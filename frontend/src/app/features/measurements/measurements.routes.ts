import { Routes } from '@angular/router';
export const MEASUREMENT_ROUTES: Routes = [{
  path: '', pathMatch: 'full', title: 'Mesures | Industrial Predict AI', data: { pageTitle: 'Mesures' },
  loadComponent: () => import('./pages/measurements-list/measurements-list.component').then(m => m.MeasurementsListComponent)
}, {
  path: ':measurementId', pathMatch: 'full', title: 'Détail mesure | Industrial Predict AI', data: { pageTitle: 'Détail mesure' },
  loadComponent: () => import('./pages/measurement-detail/measurement-detail.component').then(m => m.MeasurementDetailComponent)
}];
