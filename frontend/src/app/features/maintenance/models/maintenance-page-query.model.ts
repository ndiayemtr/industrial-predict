import { MaintenancePriority, MaintenanceStatus, MaintenanceType } from './maintenance.model';

export interface MaintenancePageQuery {
  equipment_id: number;
  page?: number;
  page_size?: number;
  maintenance_type?: MaintenanceType;
  status?: MaintenanceStatus;
  priority?: MaintenancePriority;
  search?: string;
  /** Inclusive created_at boundary, ISO with offset; preserved verbatim. */
  start_time?: string;
  /** Exclusive created_at boundary, ISO with offset; preserved verbatim. */
  end_time?: string;
}
