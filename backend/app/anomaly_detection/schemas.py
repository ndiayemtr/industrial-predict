from datetime import datetime

from pydantic import BaseModel, Field


class AnomalyResult(BaseModel):
    measurement_id: int
    sensor_id: int
    equipment_id: int | None = None
    timestamp: datetime

    anomaly_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    is_anomaly: bool

    method: str
    reason: str | None = None