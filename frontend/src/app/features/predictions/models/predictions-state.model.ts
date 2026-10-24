import { PredictionPageQuery } from './prediction-page-query.model';
import { PredictionPage } from './prediction.model';

export interface PredictionsQuery extends Omit<PredictionPageQuery, 'equipment_id'> {
  company_id?: number;
  site_id?: number;
  equipment_id?: number;
  page: number;
  page_size: number;
}

export type PredictionsState =
  | { status: 'idle' | 'loading' }
  | { status: 'success' | 'empty' | 'out-of-range'; data: PredictionPage }
  | { status: 'error'; message: string; retryable: boolean };
