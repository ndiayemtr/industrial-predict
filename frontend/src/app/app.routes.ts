import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./layout/shell/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' },
      {
        path: 'dashboard',
        title: 'Dashboard | Industrial Predict AI',
        loadComponent: () =>
          import('./features/dashboard/dashboard-placeholder.component').then(
            (m) => m.DashboardPlaceholderComponent
          )
      }
    ]
  }
];
