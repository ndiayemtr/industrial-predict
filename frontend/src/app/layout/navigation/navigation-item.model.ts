export type NavigationItemId =
  | 'dashboard'
  | 'companies'
  | 'sites'
  | 'equipments'
  | 'sensors'
  | 'measurements'
  | 'maintenance'
  | 'predictions'
  | 'recommendations'
  | 'reports'
  | 'administration';

interface NavigationItemBase {
  readonly id: NavigationItemId;
  readonly label: string;
}

export interface NavigableNavigationItem extends NavigationItemBase {
  readonly status: 'available';
  readonly path: `/${string}`;
  readonly match: 'exact' | 'section';
}

export interface ComingSoonNavigationItem extends NavigationItemBase {
  readonly status: 'coming-soon';
}

export type NavigationItem = NavigableNavigationItem | ComingSoonNavigationItem;
