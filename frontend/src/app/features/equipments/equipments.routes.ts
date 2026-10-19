import { Routes } from '@angular/router';

export const EQUIPMENT_ROUTES: Routes = [{
  path: '', pathMatch: 'full', title: 'Équipements | Industrial Predict AI',
  data: { pageTitle: 'Équipements' },
  loadComponent: () => import('./pages/equipments-list/equipments-list.component').then(m => m.EquipmentsListComponent)
}];
