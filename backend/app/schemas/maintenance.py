from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    downtime_minutes: int | None = Field(
        default=None,
        ge=0,
    )

    cost: float | None = Field(
        default=None,
        ge=0,
    )

    @field_validator(
        "planned_at",
        "started_at",
        "completed_at",
    )
    @classmethod
    def validate_timezone(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return value

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must include timezone information")

        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.started_at > self.completed_at
        ):
            raise ValueError("started_at must be before or equal to completed_at")

        return self


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

    downtime_minutes: int | None = Field(
        default=None,
        ge=0,
    )

    cost: float | None = Field(
        default=None,
        ge=0,
    )

    @field_validator(
        "planned_at",
        "started_at",
        "completed_at",
    )
    @classmethod
    def validate_timezone(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return value

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must include timezone information")

        return value

    @model_validator(mode="after")
    def validate_dates(self):
        if (
            self.started_at is not None
            and self.completed_at is not None
            and self.started_at > self.completed_at
        ):
            raise ValueError("started_at must be before or equal to completed_at")

        return self


class MaintenanceRead(MaintenanceBase):
    id: int
    equipment_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
