// JSON contract of backend/app/schemas/dashboard.py. Dates remain transport strings.
export interface DashboardScope {
  company_id: number;
  site_id: number | null;
  equipment_id: number | null;
}

export interface DashboardPeriod {
  start_time: string;
  end_time: string;
  calculated_at: string;
}

export interface RatioKPI {
  numerator: number;
  denominator: number;
  percentage: number | null;
}

export interface CategoryCount {
  value: string;
  count: number;
}

export interface AssetOverview {
  sites: number;
  equipments: number;
  sensors: number;
}

export interface EquipmentStatusSummary {
  total: number;
  operational: number;
  maintenance: number;
  out_of_service: number;
  other: number;
  distribution: CategoryCount[];
  operational_ratio: RatioKPI;
}

export interface EquipmentCriticalitySummary {
  total: number;
  low: number;
  medium: number;
  high: number;
  critical: number;
  other: number;
  distribution: CategoryCount[];
  high_or_critical: number;
  high_or_critical_unavailable: number;
}

export interface SensorCoverageSummary {
  equipments_total: number;
  equipments_with_active_sensor: number;
  coverage: RatioKPI;
}

export interface SensorStatusSummary {
  total: number;
  active: number;
  inactive: number;
  other: number;
  distribution: CategoryCount[];
  active_ratio: RatioKPI;
}

export interface MeasurementActivitySummary {
  measurements_total: number;
  active_sensors_total: number;
  active_sensors_with_measurement: number;
  active_sensors_reporting_ratio: RatioKPI;
}

export interface MeasurementQualitySummary {
  total: number;
  good: number;
  suspect: number;
  bad: number;
  missing: number;
  estimated: number;
  other: number;
  distribution: CategoryCount[];
  good_ratio: RatioKPI;
}

export interface DailyMeasurementCount {
  date: string;
  count: number;
}

export interface LastMeasurement {
  sensor_id: number;
  sensor_name: string;
  sensor_code: string;
  equipment_id: number;
  timestamp: string | null;
  value: number | null;
  unit: string | null;
  quality: string | null;
  age_seconds: number | null;
}

export interface MeasurementSummary {
  activity: MeasurementActivitySummary;
  quality: MeasurementQualitySummary;
  daily_volume: DailyMeasurementCount[];
  last_measurements: LastMeasurement[];
}

export interface MaintenancePrioritySummary {
  total: number;
  low: number;
  medium: number;
  high: number;
  critical: number;
  other: number;
  distribution: CategoryCount[];
}

export interface OpenMaintenanceSummary {
  total: number;
  planned: number;
  in_progress: number;
  other: number;
  priorities: MaintenancePrioritySummary;
}

export interface OverdueMaintenanceSummary {
  overdue: number;
  planned_without_planned_at: number;
}

export interface MaintenanceTypeSummary {
  total: number;
  preventive: number;
  corrective: number;
  predictive: number;
  other: number;
  distribution: CategoryCount[];
}

export interface CompletedMaintenanceSummary {
  total: number;
  completed_without_completed_at: number;
  types: MaintenanceTypeSummary;
}

export interface CorrectiveMaintenanceSummary {
  corrective_completed: number;
  completed_total: number;
  ratio: RatioKPI;
}

export interface CoverageSummary {
  valid_values: number;
  eligible_records: number;
  ratio: RatioKPI;
}

export interface DowntimeSummary {
  total_minutes: number | null;
  total_hours: number | null;
  coverage: CoverageSummary;
}

export interface MaintenanceCostSummary {
  total_cost: number | null;
  currency: string | null;
  coverage: CoverageSummary;
}

export interface MaintenanceSummary {
  open: OpenMaintenanceSummary;
  overdue: OverdueMaintenanceSummary;
  completed: CompletedMaintenanceSummary;
  corrective: CorrectiveMaintenanceSummary;
  downtime: DowntimeSummary;
  cost: MaintenanceCostSummary;
}

export interface DashboardRead {
  scope: DashboardScope;
  period: DashboardPeriod;
  assets: AssetOverview;
  equipment_status: EquipmentStatusSummary;
  equipment_criticality: EquipmentCriticalitySummary;
  sensor_coverage: SensorCoverageSummary;
  sensor_status: SensorStatusSummary;
  measurements: MeasurementSummary;
  maintenance: MaintenanceSummary;
}
