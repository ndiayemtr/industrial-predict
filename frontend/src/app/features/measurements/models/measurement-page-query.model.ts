import { MeasurementQuality } from './measurement.model';

export interface MeasurementPageQuery {
  sensor_id: number;
  page?: number;
  page_size?: number;
  quality?: MeasurementQuality;
  /** ISO instant with an explicit offset, inclusive; sent without conversion. */
  start_time?: string;
  /** ISO instant with an explicit offset, exclusive; sent without conversion. */
  end_time?: string;
}
