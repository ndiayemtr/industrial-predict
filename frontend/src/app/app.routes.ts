import { Routes } from '@angular/router';
import { NAVIGATION_ITEMS } from './layout/navigation/navigation.config';
import { NavigableNavigationItem } from './layout/navigation/navigation-item.model';

const availableItems = NAVIGATION_ITEMS.filter(
  (item): item is NavigableNavigationItem => item.status === 'available'
);
const dashboardItem = availableItems.find((item) => item.id === 'dashboard')!;
const loadFeaturePlaceholder = () =>
  import('./shared/pages/feature-placeholder/feature-placeholder.component').then(
    (m) => m.FeaturePlaceholderComponent
  );

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./layout/shell/shell.component').then((m) => m.ShellComponent),
    children: [
      { path: '', redirectTo: dashboardItem.path.slice(1), pathMatch: 'full' },
      ...availableItems.map((item) => ({
        path: item.path.slice(1),
        title: `${item.label} | Industrial Predict AI`,
        data: { pageTitle: item.label },
        ...(item.id === 'companies'
          ? { loadChildren: () => import('./features/companies/companies.routes').then(m => m.COMPANY_ROUTES) }
          : item.id === 'sites'
          ? { loadChildren: () => import('./features/sites/sites.routes').then(m => m.SITE_ROUTES) }
          : item.id === 'equipments'
          ? { loadChildren: () => import('./features/equipments/equipments.routes').then(m => m.EQUIPMENT_ROUTES) }
          : item.id === 'sensors'
          ? { loadChildren: () => import('./features/sensors/sensors.routes').then(m => m.SENSOR_ROUTES) }
          : item.id === 'measurements'
          ? { loadChildren: () => import('./features/measurements/measurements.routes').then(m => m.MEASUREMENT_ROUTES) }
          : item.id === 'maintenance'
          ? { loadChildren: () => import('./features/maintenance/maintenance.routes').then(m => m.MAINTENANCE_ROUTES) }
          : { loadComponent: item.id === 'dashboard'
          ? () => import('./features/dashboard/pages/dashboard/dashboard.component').then(
              (m) => m.DashboardComponent
            )
          : loadFeaturePlaceholder })
      })),
      {
        path: '**',
        title: 'Page introuvable | Industrial Predict AI',
        data: { pageTitle: 'Page introuvable', isNotFound: true },
        loadComponent: () => import('./shared/pages/not-found/not-found.component').then(
          (m) => m.NotFoundComponent
        )
      }
    ]
  }
];
