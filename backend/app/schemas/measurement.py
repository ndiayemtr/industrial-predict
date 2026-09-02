from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MeasurementBase(BaseModel):
    timestamp: datetime
    value: float
    quality: str = "good"


class MeasurementCreate(MeasurementBase):
    sensor_id: int


class MeasurementUpdate(BaseModel):
    timestamp: datetime | None = None
    value: float | None = None
    quality: str | None = None


class MeasurementRead(MeasurementBase):
    id: int
    sensor_id: int

    model_config = ConfigDict(from_attributes=True)