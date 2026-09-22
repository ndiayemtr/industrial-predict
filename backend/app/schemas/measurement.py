from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import MeasurementQuality


class MeasurementBase(BaseModel):
    timestamp: datetime
    value: float
    quality: MeasurementQuality = MeasurementQuality.GOOD

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")

        return value


class MeasurementCreate(MeasurementBase):
    sensor_id: int


class MeasurementUpdate(BaseModel):
    timestamp: datetime | None = None
    value: float | None = None
    quality: MeasurementQuality | None = None

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")

        return value


class MeasurementRead(MeasurementBase):
    id: int
    sensor_id: int

    model_config = ConfigDict(from_attributes=True)
