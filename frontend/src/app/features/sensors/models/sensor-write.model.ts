import { SensorStatus } from './sensor.model';

export interface SensorCreate {
  equipment_id: number;
  name: string;
  code: string;
  sensor_type: string;
  unit: string;
  description?: string | null;
  // Omission preserves the backend default active; transport adds no default.
  status?: SensorStatus;
}

// MVP subset of the backend PATCH: parent, type and unit are immutable.
// The caller supplies differences only; SQL-required fields cannot be null.
export interface SensorPatch {
  name?: string;
  code?: string;
  status?: SensorStatus;
  description?: string | null;
}
