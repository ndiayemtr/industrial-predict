import { Page } from '../../../core/models/page.model';

export type SensorStatus = 'active' | 'inactive';

export interface SensorRead {
  id: number;
  name: string;
  code: string;
  sensor_type: string;
  unit: string;
  description: string | null;
  status: SensorStatus;
  equipment_id: number;
  created_at: string;
  updated_at: string;
}

export type SensorPage = Page<SensorRead>;
