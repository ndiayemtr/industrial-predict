import { SensorPage, SensorStatus } from './sensor.model';

export interface SensorsQuery {
  company_id?: number;
  site_id?: number;
  equipment_id?: number;
  status?: SensorStatus;
  search?: string;
  page: number;
  page_size: number;
}

export type SensorsState =
  | { status: 'idle' | 'loading' }
  | { status: 'success' | 'empty'; data: SensorPage }
  | { status: 'error'; message: string; retryable: boolean };
