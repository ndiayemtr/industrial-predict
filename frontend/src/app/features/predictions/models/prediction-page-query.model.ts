import { PredictionType } from './prediction.model';

export interface PredictionPageQuery {
  equipment_id: number;
  page?: number;
  page_size?: number;
  prediction_type?: PredictionType;
  level?: string;
  is_alert?: boolean;
  start_time?: string;
  end_time?: string;
}
