import { MeasurementPage, MeasurementQuality } from './measurement.model';
export interface MeasurementsQuery {
  company_id?: number;
  site_id?: number;
  equipment_id?: number;
  sensor_id?: number;
  quality?: MeasurementQuality;
  start_time?: string;
  end_time?: string;
  page: number;
  page_size: number;
}
export type MeasurementsState = { status: 'idle' | 'loading' }
  | { status: 'success' | 'empty'; data: MeasurementPage }
  | { status: 'error'; message: string; retryable: boolean };
