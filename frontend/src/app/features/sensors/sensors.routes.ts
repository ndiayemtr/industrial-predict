import { Routes } from '@angular/router';

export const SENSOR_ROUTES: Routes = [{
  path: '', pathMatch: 'full', title: 'Capteurs | Industrial Predict AI',
  data: { pageTitle: 'Capteurs' },
  loadComponent: () => import('./pages/sensors-list/sensors-list.component').then(m => m.SensorsListComponent)
}, {
  // Future 'new' and ':sensorId/edit' routes must be inserted before this detail route.
  path: ':sensorId', pathMatch: 'full',
  canMatch: [(_route, segments) => segments[0]?.path !== 'new'],
  title: 'Détail capteur | Industrial Predict AI', data: { pageTitle: 'Détail capteur' },
  loadComponent: () => import('./pages/sensor-detail/sensor-detail.component').then(m => m.SensorDetailComponent)
}];
