export interface CompanyRead {
  id: number;
  name: string;
  code: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface SiteRead extends CompanyRead {
  company_id: number;
}

export type EquipmentStatus = 'operational' | 'maintenance' | 'out_of_service';
export type EquipmentCriticality = 'low' | 'medium' | 'high' | 'critical';

export interface EquipmentRead extends CompanyRead {
  site_id: number;
  equipment_type: string;
  status: EquipmentStatus;
  criticality: EquipmentCriticality;
}
