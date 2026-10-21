import { Page } from '../../../core/models/page.model';

export type MeasurementQuality = 'good' | 'suspect' | 'bad' | 'missing' | 'estimated';

export interface MeasurementRead {
  id: number;
  sensor_id: number;
  // Keep the API offset and microseconds intact; never hydrate this as Date.
  timestamp: string;
  value: number;
  quality: MeasurementQuality;
}

export type MeasurementPage = Page<MeasurementRead>;
