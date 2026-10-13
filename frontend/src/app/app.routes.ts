import { Routes } from '@angular/router';
import { NAVIGATION_ITEMS } from './layout/navigation/navigation.config';
import { NavigableNavigationItem } from './layout/navigation/navigation-item.model';

const availableItems = NAVIGATION_ITEMS.filter(
  (item): item is NavigableNavigationItem => item.status === 'available'
);
const equipmentItem = availableItems.find((item) => item.id === 'equipments')!;
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
        loadComponent: item.id === 'dashboard'
          ? () => import('./features/dashboard/dashboard-placeholder.component').then(
              (m) => m.DashboardPlaceholderComponent
            )
          : loadFeaturePlaceholder
      })),
      {
        path: `${equipmentItem.path.slice(1)}/:equipmentId`,
        title: 'Détail équipement | Industrial Predict AI',
        data: { pageTitle: 'Détail équipement' },
        loadComponent: loadFeaturePlaceholder
      }
    ]
  }
];
