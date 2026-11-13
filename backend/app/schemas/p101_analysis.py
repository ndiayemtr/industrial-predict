"""Non-persisted P101 v1 HTTP contract; provenance is never client supplied."""

from datetime import datetime, timedelta
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.p101_dev.contracts import MODEL_VERSION


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    company_id: int = Field(gt=0, strict=True)
    site_id: int = Field(gt=0, strict=True)
    sensor_id: int = Field(gt=0, strict=True)
    target_measurement_id: int = Field(gt=0, strict=True)
    cutoff_utc: datetime

    @field_validator('cutoff_utc')
    @classmethod
    def utc(cls, value):
        if value.utcoffset() != timedelta(0):
            raise ValueError('UTC cutoff required')
        return value


class AnalysisBase(BaseModel):
    equipment_id: int
    target_measurement_id: int
    protocol_version: str = MODEL_VERSION
    persisted: Literal[False] = False
    provenance_source: str
    synthetic: Literal[False] = False


class ComputedAnalysis(AnalysisBase):
    status: Literal['COMPUTED'] = 'COMPUTED'
    score: Literal[0, 1]
    is_alert: bool
    reference_ids: list[int]
    statistics: dict[str, float]


class AbstainedAnalysis(AnalysisBase):
    status: Literal['ABSTAINED'] = 'ABSTAINED'
    reason: str
    reference_count: int


class RejectedAnalysis(AnalysisBase):
    status: Literal['REJECTED'] = 'REJECTED'
    reason: str
    field: str


AnalysisResponse = Annotated[ComputedAnalysis | AbstainedAnalysis | RejectedAnalysis, Field(discriminator='status')]
