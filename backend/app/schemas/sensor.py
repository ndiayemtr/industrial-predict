from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import SensorStatus


class SensorBase(BaseModel):
    name: str
    code: str
    sensor_type: str
    unit: str = Field(
        min_length=1,
    )
    description: str | None = None
    status: SensorStatus = SensorStatus.ACTIVE


class SensorCreate(SensorBase):
    equipment_id: int


class SensorUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    sensor_type: str | None = None
    unit: str | None = Field(
        default=None,
        min_length=1,
    )
    description: str | None = None
    status: SensorStatus | None = None
    equipment_id: int | None = None


class SensorRead(SensorBase):
    id: int
    equipment_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
