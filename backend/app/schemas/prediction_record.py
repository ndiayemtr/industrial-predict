from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import PredictionType


class PredictionRecordBase(BaseModel):
    equipment_id: int = Field(ge=1)
    sensor_id: int | None = Field(default=None, ge=1)
    measurement_id: int | None = Field(default=None, ge=1)

    prediction_type: PredictionType

    score: float
    level: str | None = None
    is_alert: bool | None = None

    model_name: str | None = None
    model_version: str | None = None
    horizon_hours: float | None = Field(
        default=None,
        gt=0,
    )

    details: dict[str, Any] | None = None
    predicted_at: datetime


class PredictionRecordCreate(PredictionRecordBase):
    pass


class PredictionRecordRead(PredictionRecordBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )