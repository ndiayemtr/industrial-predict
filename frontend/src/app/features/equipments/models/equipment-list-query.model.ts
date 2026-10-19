import { EquipmentPageQuery } from '../../../core/models/equipment-page-query.model';

export interface EquipmentListQuery extends EquipmentPageQuery {
  site_id: number;
}
