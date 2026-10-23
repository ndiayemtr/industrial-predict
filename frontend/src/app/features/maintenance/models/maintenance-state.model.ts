import { MaintenancePageQuery } from './maintenance-page-query.model';
import { MaintenancePage } from './maintenance.model';

export interface MaintenanceQuery extends Omit<MaintenancePageQuery, 'equipment_id'> {
  company_id?: number;
  site_id?: number;
  equipment_id?: number;
  page: number;
  page_size: number;
}
export type MaintenanceState =
  | { status: 'idle' | 'loading' }
  | { status: 'success' | 'empty'; data: MaintenancePage }
  | { status: 'error'; message: string; retryable: boolean };
