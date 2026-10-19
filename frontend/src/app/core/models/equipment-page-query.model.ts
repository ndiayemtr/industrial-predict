import { ReferencePageQuery } from './page.model';
import { EquipmentCriticality, EquipmentStatus } from './reference-data.model';

export interface EquipmentPageQuery extends ReferencePageQuery {
  status?: EquipmentStatus;
  criticality?: EquipmentCriticality;
}
