"""Logical P101 contracts. No SQL identity or persistence is assigned here."""

from dataclasses import dataclass
from enum import StrEnum
import json
from types import MappingProxyType
from typing import Literal


METHOD_VERSION = "p101-stat-v1"
MODEL_NAME = "statistical_deviation"
ASSET = MappingProxyType({
    "company_id": "DEMO-COMP-001", "company_code": "MLDEMO-COMP-P101",
    "site_id": "DEMO-SITE-001", "site_code": "MLDEMO-SITE-P101",
    "equipment_id": "DEMO-EQ-001", "equipment_code": "MLDEMO-EQ-P101",
    "sensor_id": "DEMO-SEN-001", "sensor_code": "MLDEMO-SEN-P101-TEMP",
})


class AbstentionCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    INCONSISTENT_PARENT = "INCONSISTENT_PARENT"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    TARGET_UNAVAILABLE = "TARGET_UNAVAILABLE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    GAP_OR_CADENCE = "GAP_OR_CADENCE"
    INVALID_VALUE = "INVALID_VALUE"
    INVALID_QUALITY = "INVALID_QUALITY"
    ZERO_STD = "ZERO_STD"
    NONFINITE_STATISTIC = "NONFINITE_STATISTIC"


@dataclass(frozen=True)
class Observation:
    fixture_id: str
    timestamp: str
    available_at: str
    asset: tuple[tuple[str, str], ...]
    synthetic: bool
    unit: str
    quality: str
    value: object


@dataclass(frozen=True)
class Statistics:
    mean: float
    sample_std: float
    absolute_deviation: float
    threshold: float


@dataclass(frozen=True)
class LogicalPrediction:
    equipment_fixture_id: str
    sensor_fixture_id: str
    measurement_fixture_id: str
    predicted_at: str
    score: Literal[0, 1]
    is_alert: bool
    details_json: str
    prediction_type: Literal["anomaly"] = "anomaly"
    model_name: str = MODEL_NAME
    model_version: str = METHOD_VERSION
    level: None = None
    horizon_hours: None = None

    @property
    def details(self) -> dict:
        # Return a copy: callers cannot mutate the validated proposal.
        return json.loads(self.details_json)


@dataclass(frozen=True)
class Computed:
    prediction: LogicalPrediction
    reference_ids: tuple[str, ...]
    statistics: Statistics
    dataset_sha256: str
    reference_sha256: str
    status: Literal["computed"] = "computed"


@dataclass(frozen=True)
class Abstained:
    code: AbstentionCode
    target_id: str
    cutoff_utc: str | None
    affected_ids: tuple[str, ...]
    explanation: str
    prediction: None = None
    status: Literal["abstained"] = "abstained"
    method_version: str = METHOD_VERSION


Result = Computed | Abstained
