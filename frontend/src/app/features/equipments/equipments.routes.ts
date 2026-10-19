import { Routes } from '@angular/router';

export const EQUIPMENT_ROUTES: Routes = [{
  path: '', pathMatch: 'full', title: 'Équipements | Industrial Predict AI',
  data: { pageTitle: 'Équipements' },
  loadComponent: () => import('./pages/equipments-list/equipments-list.component').then(m => m.EquipmentsListComponent)
}, {
  // Add future 'new' and ':equipmentId/edit' pages before this detail route.
  // Until then, 'new' and nested paths belong to the global 404.
  path: ':equipmentId', pathMatch: 'full',
  canMatch: [(_route, segments) => segments[0]?.path !== 'new'],
  title: 'Détail équipement | Industrial Predict AI',
  data: { pageTitle: 'Détail équipement' },
  loadComponent: () => import('./pages/equipment-detail/equipment-detail.component').then(m => m.EquipmentDetailComponent)
}];
