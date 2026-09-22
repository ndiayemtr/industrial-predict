from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.enums import (
    MaintenancePriority,
    MaintenanceStatus,
    MaintenanceType,
)


class MaintenanceBase(BaseModel):
    maintenance_type: MaintenanceType
    status: MaintenanceStatus = MaintenanceStatus.PLANNED
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    title: str
    description: str | None = None
    failure_code: str | None = None
    root_cause: str | None = None
    action_taken: str | None = None
    technician: str | None = None
    planned_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    downtime_minutes: int | None = None
    cost: float | None = None


class MaintenanceCreate(MaintenanceBase):
    equipment_id: int


class MaintenanceUpdate(BaseModel):
    maintenance_type: MaintenanceType | None = None
    status: MaintenanceStatus | None = None
    priority: MaintenancePriority | None = None
    title: str | None = None
    description: str | None = None
    failure_code: str | None = None
    root_cause: str | None = None
    action_taken: str | None = None
    technician: str | None = None
    planned_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    downtime_minutes: int | None = None
    cost: float | None = None
    equipment_id: int | None = None


class MaintenanceRead(MaintenanceBase):
    id: int
    equipment_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)