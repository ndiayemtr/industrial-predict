import { Routes } from '@angular/router';

// List only: unknown detail paths fall through to the application's global 404.
export const PREDICTION_ROUTES: Routes = [
  { path: '', pathMatch: 'full', title: 'Prédictions | Industrial Predict AI', data: { pageTitle: 'Prédictions' },
    loadComponent: () => import('./pages/predictions-list/predictions-list.component').then(m => m.PredictionsListComponent) }
];
