import { Page } from '../../../core/models/page.model';

export type MaintenanceType = 'preventive' | 'corrective' | 'predictive';
export type MaintenanceStatus = 'planned' | 'in_progress' | 'completed' | 'cancelled';
export type MaintenancePriority = 'low' | 'medium' | 'high' | 'critical';

export interface MaintenanceRead {
  id: number;
  equipment_id: number;
  maintenance_type: MaintenanceType;
  status: MaintenanceStatus;
  priority: MaintenancePriority;
  title: string;
  description: string | null;
  failure_code: string | null;
  root_cause: string | null;
  action_taken: string | null;
  technician: string | null;
  // Original ISO strings, including offsets and microseconds; no Date hydration.
  planned_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  downtime_minutes: number | null;
  // Declared amount only: the API supplies no currency.
  cost: number | null;
  // An offset is not guaranteed. Keep naive timestamps explicitly distinguishable.
  created_at: string;
  updated_at: string;
}

export type MaintenancePage = Page<MaintenanceRead>;
