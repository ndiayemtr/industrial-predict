import { Routes } from '@angular/router';

export const EQUIPMENT_ROUTES: Routes = [{
  path: '', pathMatch: 'full', title: 'Équipements | Industrial Predict AI',
  data: { pageTitle: 'Équipements' },
  loadComponent: () => import('./pages/equipments-list/equipments-list.component').then(m => m.EquipmentsListComponent)
}, {
  path: 'new', pathMatch: 'full',
  title: 'Nouvel équipement industriel | Industrial Predict AI',
  data: { pageTitle: 'Nouvel équipement industriel' },
  canDeactivate: [(component: { canLeave(): boolean }) => component.canLeave()],
  loadComponent: () => import('./pages/equipment-create/equipment-create.component').then(m => m.EquipmentCreateComponent)
}, {
  // Add the future ':equipmentId/edit' page before this detail route.
  path: ':equipmentId', pathMatch: 'full',
  title: 'Détail équipement | Industrial Predict AI',
  data: { pageTitle: 'Détail équipement' },
  loadComponent: () => import('./pages/equipment-detail/equipment-detail.component').then(m => m.EquipmentDetailComponent)
}];
