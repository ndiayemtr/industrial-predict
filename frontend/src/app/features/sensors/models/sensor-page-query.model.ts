import { ReferencePageQuery } from '../../../core/models/page.model';
import { SensorStatus } from './sensor.model';

export interface SensorPageQuery extends ReferencePageQuery {
  equipment_id: number;
  status?: SensorStatus;
}
