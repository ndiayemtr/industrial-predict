import { Page } from '../../../core/models/page.model';
import { EquipmentRead } from '../../../core/models/reference-data.model';
import { EquipmentPageQuery } from '../../../core/models/equipment-page-query.model';

export interface EquipmentsQuery extends EquipmentPageQuery {
  company_id?: number;
  site_id?: number;
  page: number;
  page_size: number;
}

export type EquipmentsState =
  | { status: 'idle' | 'loading' }
  | { status: 'success' | 'empty'; data: Page<EquipmentRead> }
  | { status: 'error'; message: string; retryable: boolean };
