import { EquipmentCriticality, EquipmentStatus } from '../../../core/models/reference-data.model';

export interface EquipmentCreate {
  site_id: number;
  // SQL limits: name 150, globally unique code 100, free-text type 100 characters.
  // Form validation belongs to UI 5.5; transport never trims or changes case.
  name: string;
  code: string;
  equipment_type: string;
  description?: string | null;
  // Omission retains FastAPI defaults: operational / medium.
  status?: EquipmentStatus;
  criticality?: EquipmentCriticality;
}

// MVP subset of EquipmentUpdate: moving a device to another site is excluded.
// SQL non-nullable fields stay non-nullable here, unlike the Pydantic PATCH schema.
export interface EquipmentUpdate {
  name?: string;
  code?: string;
  equipment_type?: string;
  description?: string | null;
  status?: EquipmentStatus;
  criticality?: EquipmentCriticality;
}
