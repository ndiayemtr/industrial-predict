import { Routes } from '@angular/router';

export const SENSOR_ROUTES: Routes = [{
  path: '', pathMatch: 'full', title: 'Capteurs | Industrial Predict AI',
  data: { pageTitle: 'Capteurs' },
  loadComponent: () => import('./pages/sensors-list/sensors-list.component').then(m => m.SensorsListComponent)
}];
