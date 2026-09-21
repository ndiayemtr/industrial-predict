from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DashboardScope(BaseModel):
    company_id: int
    site_id: int | None = None
    equipment_id: int | None = None


class DashboardPeriod(BaseModel):
    start_time: datetime
    end_time: datetime
    calculated_at: datetime


class CountKPI(BaseModel):
    count: int


class RatioKPI(BaseModel):
    numerator: int
    denominator: int
    percentage: float | None


class CategoryCount(BaseModel):
    value: str
    count: int


class AssetOverview(BaseModel):
    sites: int
    equipments: int
    sensors: int


class EquipmentStatusSummary(BaseModel):
    total: int
    operational: int
    maintenance: int
    out_of_service: int
    other: int

    distribution: list[CategoryCount]

    operational_ratio: RatioKPI


class EquipmentCriticalitySummary(BaseModel):
    total: int
    low: int
    medium: int
    high: int
    critical: int
    other: int

    distribution: list[CategoryCount]

    high_or_critical: int
    high_or_critical_unavailable: int


class SensorCoverageSummary(BaseModel):
    equipments_total: int

    equipments_with_active_sensor: int

    coverage: RatioKPI


class SensorStatusSummary(BaseModel):
    total: int
    active: int
    inactive: int
    other: int

    distribution: list[CategoryCount]

    active_ratio: RatioKPI


class MeasurementQualitySummary(BaseModel):
    total: int

    good: int
    suspect: int
    bad: int
    missing: int
    estimated: int
    other: int

    distribution: list[CategoryCount]

    good_ratio: RatioKPI


class MeasurementActivitySummary(BaseModel):
    measurements_total: int

    active_sensors_total: int
    active_sensors_with_measurement: int

    active_sensors_reporting_ratio: RatioKPI


class DailyMeasurementCount(BaseModel):
    date: str
    count: int


class LastMeasurement(BaseModel):
    sensor_id: int
    sensor_name: str
    sensor_code: str

    equipment_id: int

    timestamp: datetime | None

    value: float | None
    unit: str | None
    quality: str | None

    age_seconds: float | None


class MeasurementSummary(BaseModel):
    activity: MeasurementActivitySummary

    quality: MeasurementQualitySummary

    daily_volume: list[DailyMeasurementCount]

    last_measurements: list[LastMeasurement]


class MaintenancePrioritySummary(BaseModel):
    total: int

    low: int
    medium: int
    high: int
    critical: int
    other: int

    distribution: list[CategoryCount]


class OpenMaintenanceSummary(BaseModel):
    total: int

    planned: int
    in_progress: int
    other: int

    priorities: MaintenancePrioritySummary


class OverdueMaintenanceSummary(BaseModel):
    overdue: int

    planned_without_planned_at: int


class MaintenanceTypeSummary(BaseModel):
    total: int

    preventive: int
    corrective: int
    predictive: int
    other: int

    distribution: list[CategoryCount]


class CompletedMaintenanceSummary(BaseModel):
    total: int

    completed_without_completed_at: int

    types: MaintenanceTypeSummary


class CorrectiveMaintenanceSummary(BaseModel):
    corrective_completed: int
    completed_total: int

    ratio: RatioKPI


class CoverageSummary(BaseModel):
    valid_values: int
    eligible_records: int

    ratio: RatioKPI


class DowntimeSummary(BaseModel):
    total_minutes: float | None
    total_hours: float | None

    coverage: CoverageSummary


class MaintenanceCostSummary(BaseModel):
    total_cost: float | None

    currency: str | None

    coverage: CoverageSummary


class MaintenanceSummary(BaseModel):
    open: OpenMaintenanceSummary

    overdue: OverdueMaintenanceSummary

    completed: CompletedMaintenanceSummary

    corrective: CorrectiveMaintenanceSummary

    downtime: DowntimeSummary

    cost: MaintenanceCostSummary


class DashboardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scope: DashboardScope

    period: DashboardPeriod

    assets: AssetOverview

    equipment_status: EquipmentStatusSummary

    equipment_criticality: EquipmentCriticalitySummary

    sensor_coverage: SensorCoverageSummary

    sensor_status: SensorStatusSummary

    measurements: MeasurementSummary

    maintenance: MaintenanceSummary