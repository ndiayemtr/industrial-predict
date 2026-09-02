from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SensorBase(BaseModel):
    name: str
    code: str
    sensor_type: str
    unit: str | None = None
    description: str | None = None
    status: str = "active"


class SensorCreate(SensorBase):
    equipment_id: int


class SensorUpdate(BaseModel):
    name: str | None = None
    code: str | None = None
    sensor_type: str | None = None
    unit: str | None = None
    description: str | None = None
    status: str | None = None
    equipment_id: int | None = None


class SensorRead(SensorBase):
    id: int
    equipment_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)