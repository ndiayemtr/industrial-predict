import { Page } from '../../../core/models/page.model';

export type PredictionType = 'anomaly' | 'failure_risk' | 'health_score' | 'rul';

export type JsonValue = string | number | boolean | null | JsonValue[] | JsonObject;
export interface JsonObject { [key: string]: JsonValue }

// The backend Read schema has fourteen fields. Nullable fields are required keys.
export interface PredictionRead {
  id: number;
  equipment_id: number;
  sensor_id: number | null;
  measurement_id: number | null;
  prediction_type: PredictionType;
  // Meaning and scale depend on the producer; no probability is inferred here.
  score: number;
  level: string | null;
  is_alert: boolean | null;
  model_name: string | null;
  model_version: string | null;
  horizon_hours: number | null;
  details: JsonObject | null;
  predicted_at: string;
  created_at: string;
}

export type PredictionPage = Page<PredictionRead>;
