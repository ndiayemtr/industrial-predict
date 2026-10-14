import { NavigationItem } from './navigation-item.model';

// Paths and labels are shared by the Sidebar and the application routes.
// Available entries can currently lead to an explicitly marked placeholder.
export const NAVIGATION_ITEMS: readonly NavigationItem[] = [
  { id: 'dashboard', label: 'Dashboard', status: 'available', path: '/dashboard', match: 'exact' },
  { id: 'companies', label: 'Entreprises', status: 'available', path: '/companies', match: 'section' },
  { id: 'sites', label: 'Sites', status: 'available', path: '/sites', match: 'section' },
  { id: 'equipments', label: 'Équipements', status: 'available', path: '/equipments', match: 'section' },
  { id: 'sensors', label: 'Capteurs', status: 'available', path: '/sensors', match: 'section' },
  { id: 'measurements', label: 'Mesures', status: 'available', path: '/measurements', match: 'section' },
  { id: 'maintenance', label: 'Maintenance', status: 'available', path: '/maintenance', match: 'section' },
  { id: 'predictions', label: 'Prédictions', status: 'available', path: '/predictions', match: 'section' },
  { id: 'recommendations', label: 'Recommandations', status: 'available', path: '/recommendations', match: 'section' },
  { id: 'reports', label: 'Rapports', status: 'coming-soon' },
  { id: 'administration', label: 'Administration', status: 'coming-soon' }
];
