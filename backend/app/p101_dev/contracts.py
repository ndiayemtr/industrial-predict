"""Immutable declarations and outcomes; constructors do not validate authority."""

from dataclasses import dataclass, field
from enum import StrEnum
import json
from typing import Literal


MODEL_NAME = "statistical_deviation"
MODEL_VERSION = "p101-dev-stat-v1"
DETAIL_SCHEMA = "p101-dev-anomaly-details-v1"
AVAILABILITY_LIMIT = (
    "Retrospective snapshot only: availability at the historical target time is not attested."
)


@dataclass(frozen=True)
class AssetIdentity:
    """Already-resolved SQL references; no database lookup or authorization proof."""

    company_id: int
    site_id: int
    equipment_id: int
    sensor_id: int


@dataclass(frozen=True)
class Measurement:
    measurement_id: int
    asset: AssetIdentity
    timestamp: str
    value: float
    quality: str
    unit: str


@dataclass(frozen=True)
class EvidenceReference:
    """An available attestation reference, not a verified cryptographic proof."""

    kind: Literal["operator_declaration", "source_manifest", "review"]
    reference: str
    sha256: str | None = None


@dataclass(frozen=True)
class DeclaredProvenance:
    source_id: str
    declaration_ref: str
    synthetic: bool
    evidence: tuple[EvidenceReference, ...] = ()
    code_revision: str | None = None


@dataclass(frozen=True)
class StatisticalPolicy:
    reference_count: int = 10
    cadence_seconds: int = 86400
    tolerance_seconds: int = 0
    ddof: int = 1
    multiplier: int = 3
    selection: str = "exact_daily_preceding_target"
    availability_mode: str = "snapshot_only"


@dataclass(frozen=True)
class EvaluationInput:
    asset: AssetIdentity
    sensor_type: str
    target: Measurement
    references: tuple[Measurement, ...]
    event_cutoff_utc: str
    snapshot_observed_at: str
    provenance: DeclaredProvenance
    policy: StatisticalPolicy = field(default_factory=StatisticalPolicy)


class RejectionCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_IDENTITY = "INVALID_IDENTITY"
    INCONSISTENT_IDENTITY = "INCONSISTENT_IDENTITY"
    INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
    INVALID_TIME_CONTEXT = "INVALID_TIME_CONTEXT"
    INVALID_PROVENANCE = "INVALID_PROVENANCE"
    UNSUPPORTED_POLICY = "UNSUPPORTED_POLICY"
    INPUT_LIMIT = "INPUT_LIMIT"
    JSON_LIMIT = "JSON_LIMIT"


class AbstentionCode(StrEnum):
    SENSOR_TYPE_MISMATCH = "SENSOR_TYPE_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    INVALID_QUALITY = "INVALID_QUALITY"
    INVALID_VALUE = "INVALID_VALUE"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    TARGET_AFTER_CUTOFF = "TARGET_AFTER_CUTOFF"
    FUTURE_REFERENCE = "FUTURE_REFERENCE"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    REFERENCE_COUNT_MISMATCH = "REFERENCE_COUNT_MISMATCH"
    GAP_OR_CADENCE = "GAP_OR_CADENCE"
    ZERO_STD = "ZERO_STD"
    NONFINITE_STATISTIC = "NONFINITE_STATISTIC"


@dataclass(frozen=True)
class Rejected:
    code: RejectionCode
    field: str
    status: Literal["rejected"] = field(default="rejected", init=False)


@dataclass(frozen=True)
class Abstained:
    code: AbstentionCode
    target_measurement_id: int
    reference_count: int
    affected_ids: tuple[int, ...] = ()
    diagnostic: str = "No prediction produced; no observations were replaced or discarded."
    status: Literal["abstained"] = field(default="abstained", init=False)
    prediction: None = field(default=None, init=False)


@dataclass(frozen=True)
class ReferenceStatistics:
    mean: float
    sample_std: float
    absolute_deviation: float
    threshold: float


@dataclass(frozen=True)
class Computed:
    asset: AssetIdentity
    target: Measurement
    references: tuple[Measurement, ...]
    policy: StatisticalPolicy
    provenance: DeclaredProvenance
    score: Literal[0, 1]
    is_alert: bool
    statistics: ReferenceStatistics
    input_sha256: str
    details_json: str
    details_sha256: str
    model_name: str = field(default=MODEL_NAME, init=False)
    model_version: str = field(default=MODEL_VERSION, init=False)
    status: Literal["computed"] = field(default="computed", init=False)

    @property
    def reference_ids(self) -> tuple[int, ...]:
        return tuple(row.measurement_id for row in self.references)

    @property
    def details(self) -> dict:
        return json.loads(self.details_json)  # A fresh copy, never mutable shared state.


@dataclass(frozen=True)
class PreparedEvaluation:
    """Internal normalized input. evaluate() always validates the original input."""

    value: EvaluationInput
    input_sha256: str


Result = Computed | Abstained | Rejected
