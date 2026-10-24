import { Routes } from '@angular/router';

// Internal feature route only; global routing and Equipment navigation wait for UI 9.5.
export const PREDICTION_ROUTES: Routes = [
  { path: '', pathMatch: 'full', title: 'Prédictions | Industrial Predict AI', data: { pageTitle: 'Prédictions' },
    loadComponent: () => import('./pages/predictions-list/predictions-list.component').then(m => m.PredictionsListComponent) }
];
