"""Immutable data for a logical preparation, never permission to write."""

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Literal


CALCULATION_REVISION = "b6b4d521b9c9456c160433e9343efd48d3c0168d"
FIXTURE_SHA256 = "6c8eed59fb2c8b6328899646f93b5191a88c6698be48c51a73b414ce3560dc3a"


class TargetIdentity(StrEnum):
    NORMAL = "DEMO-M-011"
    ANOMALY = "DEMO-M-012"


class ValidationCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    ABSTENTION_REFUSED = "ABSTENTION_REFUSED"
    INCOMPLETE_BATCH = "INCOMPLETE_BATCH"
    DUPLICATE_TARGET = "DUPLICATE_TARGET"
    INVALID_PROPOSAL = "INVALID_PROPOSAL"
    IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    INVALID_FINGERPRINT = "INVALID_FINGERPRINT"
    UNATTESTED_PROVENANCE = "UNATTESTED_PROVENANCE"
    DESTINATION_MISMATCH = "DESTINATION_MISMATCH"
    AUTHORIZATION_MISMATCH = "AUTHORIZATION_MISMATCH"
    JSON_LIMIT = "JSON_LIMIT"


class ContractError(ValueError):
    def __init__(self, code: ValidationCode, field: str):
        self.code = code
        self.field = field
        super().__init__(f"{code.value}: {field}")


@dataclass(frozen=True)
class DestinationDeclaration:
    instance_uuid: str
    host: str
    port: int
    database: str
    role: str
    purpose: Literal["p101-ml-sandbox"] = "p101-ml-sandbox"


@dataclass(frozen=True)
class ProvenanceAttestation:
    code_revision: str
    fixture_sha256: str
    review_uuid: str
    attested: bool


@dataclass(frozen=True)
class PreparationPolicy:
    destination: DestinationDeclaration
    approved_review_uuid: str
    calculation_revision: str = CALCULATION_REVISION
    fixture_sha256: str = FIXTURE_SHA256


@dataclass(frozen=True)
class IdempotencyTuple:
    instance_uuid: str
    dataset_sha256: str
    equipment_code: str
    sensor_code: str
    target_id: str
    predicted_at: str
    cutoff_utc: str
    prediction_type: str
    model_name: str
    model_version: str
    code_revision: str
    reference_sha256: str
    window_count: int = 10
    ddof: int = 1
    cadence_seconds: int = 86400
    multiplier: int = 3
    comparison: str = "absolute_deviation>threshold"
    schema_version: str = "p101-idempotency-v1"


@dataclass(frozen=True)
class CanonicalProjection:
    canonical_json: str
    sha256: str


@dataclass(frozen=True)
class LogicalIdempotencyKey:
    components: IdempotencyTuple
    projection: CanonicalProjection


@dataclass(frozen=True)
class AuthorizationTarget:
    identity: TargetIdentity
    cutoff_utc: str
    reference_sha256: str
    content_sha256: str


@dataclass(frozen=True)
class AuthorizationDeclaration:
    """Claim to compare with policy/content; not a credential or SQL grant."""
    declaration_uuid: str
    destination: DestinationDeclaration
    dataset_sha256: str
    code_revision: str
    targets: tuple[AuthorizationTarget, ...]


@dataclass(frozen=True)
class SqlDependent:
    field: str
    logical_identity: str | None = None


@dataclass(frozen=True)
class DetailsDraft:
    candidate_json: str
    reserved_sql_bytes: int = 1024

    @property
    def candidate(self) -> dict:
        return json.loads(self.candidate_json)


@dataclass(frozen=True)
class PredictionReadPlan:
    """Fourteen conceptual fields; deliberately not a PredictionRecordRead DTO."""
    id: SqlDependent
    equipment_id: SqlDependent
    sensor_id: SqlDependent
    measurement_id: SqlDependent
    prediction_type: Literal["anomaly"]
    score: Literal[0, 1]
    level: None
    is_alert: bool
    model_name: str
    model_version: str
    horizon_hours: None
    details: DetailsDraft
    predicted_at: str
    created_at: SqlDependent


@dataclass(frozen=True)
class PreparedTarget:
    identity: TargetIdentity
    key: LogicalIdempotencyKey
    content: CanonicalProjection
    read_plan: PredictionReadPlan


@dataclass(frozen=True)
class PreparationDossier:
    destination: DestinationDeclaration
    provenance: ProvenanceAttestation
    authorization: AuthorizationDeclaration
    targets: tuple[PreparedTarget, ...]
    manifest_canonical_json: str

    @property
    def destination_verified(self) -> Literal[False]:
        return False

    @property
    def write_authorized(self) -> Literal[False]:
        return False

    @property
    def persistence_ready(self) -> Literal[False]:
        return False


@dataclass(frozen=True)
class ValidationIssue:
    code: ValidationCode
    field: str


@dataclass(frozen=True)
class ValidatedPreparation:
    dossier: PreparationDossier
    status: Literal["validated_offline"] = "validated_offline"


@dataclass(frozen=True)
class RejectedPreparation:
    issues: tuple[ValidationIssue, ...]
    dossier: None = None
    status: Literal["rejected"] = "rejected"


ValidationResult = ValidatedPreparation | RejectedPreparation


class RetryDisposition(StrEnum):
    IDENTICAL_RETRY = "IDENTICAL_RETRY"
    CONTENT_CONFLICT = "CONTENT_CONFLICT"
    DIFFERENT_KEY = "DIFFERENT_KEY"
