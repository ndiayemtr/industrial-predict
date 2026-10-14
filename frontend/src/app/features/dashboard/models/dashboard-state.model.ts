import { DashboardFilters } from './dashboard-filters.model';
import { DashboardRead } from './dashboard.model';

export interface DashboardError {
  kind: 'validation' | 'not-found' | 'network' | 'server' | 'unexpected';
  title: string;
  message: string;
  retryable: boolean;
}

export type DashboardState =
  | { status: 'idle' }
  | { status: 'loading'; filters: Readonly<DashboardFilters> }
  | { status: 'success' | 'empty'; filters: Readonly<DashboardFilters>; data: DashboardRead }
  | { status: 'error'; filters: Readonly<DashboardFilters>; error: DashboardError };
