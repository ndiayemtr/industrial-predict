"""Prepare and validate a P101 pair in memory; no operational transaction service."""

from dataclasses import asdict
import json
import re
from uuid import UUID

from app.anomaly_detection.p101_canonical import bounded_details, canonical_bytes, manifest_sha256, utc_instant
from app.anomaly_detection.p101_contracts import (
    ASSET, METHOD_VERSION, MODEL_NAME, Abstained, Computed, LogicalPrediction, Statistics,
)
from app.anomaly_detection.p101_core import validate_proposal
from app.p101_persistence.canonical import build_key, canonical_projection
from app.p101_persistence.contracts import (
    CALCULATION_REVISION, FIXTURE_SHA256, AuthorizationDeclaration, AuthorizationTarget,
    CanonicalProjection, ContractError, DestinationDeclaration, DetailsDraft,
    IdempotencyTuple, LogicalIdempotencyKey, PredictionReadPlan, PreparationDossier,
    PreparationPolicy, PreparedTarget, ProvenanceAttestation, RejectedPreparation,
    SqlDependent, TargetIdentity, ValidatedPreparation, ValidationCode as Code,
    ValidationIssue, ValidationResult,
)


def _require(condition: bool, code: Code, field: str) -> None:
    if not condition:
        raise ContractError(code, field)


def _uuid(value: str) -> bool:
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def _digest(value: str) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_destination(destination: DestinationDeclaration) -> None:
    """Validate a declaration's shape only. No connection or effective guard."""
    _require(type(destination) is DestinationDeclaration, Code.DESTINATION_MISMATCH, "destination.type")
    _require(_uuid(destination.instance_uuid), Code.DESTINATION_MISMATCH, "destination.instance_uuid")
    _require(type(destination.host) is str and re.fullmatch(r"[A-Za-z0-9.-]{1,253}", destination.host) is not None,
             Code.DESTINATION_MISMATCH, "destination.host")
    _require(type(destination.port) is int and 1 <= destination.port <= 65535,
             Code.DESTINATION_MISMATCH, "destination.port")
    _require(destination.database == "industrial_predict_ml_sandbox"
             and destination.purpose == "p101-ml-sandbox", Code.DESTINATION_MISMATCH, "destination.database")
    _require(type(destination.role) is str and re.fullmatch(r"p101_[a-z0-9_]{1,48}", destination.role) is not None,
             Code.DESTINATION_MISMATCH, "destination.role")


def _strict_details(prediction: LogicalPrediction) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Non-finite JSON number")

    _require(type(prediction.details_json) is str, Code.INVALID_PROPOSAL, "details.type")
    _require(len(prediction.details_json.encode("utf-8")) <= 6000, Code.JSON_LIMIT, "details.bytes")
    details = json.loads(prediction.details_json, object_pairs_hook=pairs, parse_constant=invalid_constant)
    _require(isinstance(details, dict), Code.INVALID_PROPOSAL, "details.object")
    bounded_details(details)
    return details


def _checked(computed: Computed) -> dict:
    if type(computed) is Abstained:
        raise ContractError(Code.ABSTENTION_REFUSED, "proposal")
    _require(type(computed) is Computed and computed.status == "computed",
             Code.INVALID_PROPOSAL, "proposal.type")
    prediction = computed.prediction
    _require(type(prediction) is LogicalPrediction, Code.INVALID_PROPOSAL, "prediction.type")
    _require(prediction.model_name == MODEL_NAME and prediction.model_version == METHOD_VERSION
             and prediction.prediction_type == "anomaly", Code.VERSION_MISMATCH, "producer")
    _require(prediction.equipment_fixture_id == ASSET["equipment_id"]
             and prediction.sensor_fixture_id == ASSET["sensor_id"]
             and prediction.measurement_fixture_id in tuple(TargetIdentity),
             Code.IDENTITY_MISMATCH, "prediction.identity")
    details = _strict_details(prediction)
    validate_proposal(prediction)
    _require(type(computed.statistics) is Statistics and
             asdict(computed.statistics) == {key: details["statistics"][key] for key in
                 ("mean", "sample_std", "absolute_deviation", "threshold")},
             Code.INVALID_PROPOSAL, "computed.statistics")
    _require(type(computed.reference_ids) is tuple and computed.reference_ids ==
             tuple(row["fixture_id"] for row in details["reference"]["observations"]),
             Code.INVALID_PROPOSAL, "computed.reference_ids")
    _require(_digest(computed.dataset_sha256) and _digest(computed.reference_sha256)
             and computed.dataset_sha256 == details["dataset"]["sha256"]
             and computed.reference_sha256 == details["reference"]["sha256"],
             Code.INVALID_FINGERPRINT, "computed.fingerprints")
    return details


def project_content(computed: Computed) -> CanonicalProjection:
    """Deterministic business content, independent of attempt or SQL allocation."""
    try:
        details = _checked(computed)
        details.pop("run_id")
        details.pop("prepared_at")
        details["producer"].pop("revision_status")
        prediction = computed.prediction
        return canonical_projection({
            "schema_version": "p101-business-content-v1",
            "prediction": {
                "equipment_fixture_id": prediction.equipment_fixture_id,
                "sensor_fixture_id": prediction.sensor_fixture_id,
                "measurement_fixture_id": prediction.measurement_fixture_id,
                "prediction_type": prediction.prediction_type, "score": prediction.score,
                "is_alert": prediction.is_alert, "level": prediction.level,
                "horizon_hours": prediction.horizon_hours,
                "model_name": prediction.model_name, "model_version": prediction.model_version,
                "predicted_at": prediction.predicted_at,
            }, "details": details,
        })
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
        raise ContractError(Code.INVALID_PROPOSAL, "content") from exc


def target_key(computed: Computed, destination: DestinationDeclaration) -> LogicalIdempotencyKey:
    """Logical key for a declared instance, without claiming it exists or is safe."""
    try:
        validate_destination(destination)
        d = _checked(computed)
        _require(d["producer"]["code_revision"] == CALCULATION_REVISION,
                 Code.UNATTESTED_PROVENANCE, "producer.code_revision")
        p = computed.prediction
        return build_key(IdempotencyTuple(
            destination.instance_uuid, computed.dataset_sha256,
            d["asset"]["equipment_code"], d["asset"]["sensor_code"],
            p.measurement_fixture_id, p.predicted_at, d["cutoff_utc"],
            p.prediction_type, p.model_name, p.model_version,
            d["producer"]["code_revision"], computed.reference_sha256,
        ))
    except ContractError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
        raise ContractError(Code.INVALID_PROPOSAL, "key.proposal") from exc


def _read_plan(computed: Computed, key: LogicalIdempotencyKey) -> PredictionReadPlan:
    p = computed.prediction
    candidate = p.details
    candidate["producer"].pop("revision_status")
    candidate["idempotency_key"] = key.projection.sha256
    encoded = bounded_details(candidate)
    # Reserve room for 13 future INTEGER mappings. No dummy SQL id is inserted.
    _require(len(encoded.encode("utf-8")) <= 6000 - 1024, Code.JSON_LIMIT, "details.sql_budget")
    return PredictionReadPlan(
        SqlDependent("id"), SqlDependent("equipment_id", p.equipment_fixture_id),
        SqlDependent("sensor_id", p.sensor_fixture_id),
        SqlDependent("measurement_id", p.measurement_fixture_id),
        "anomaly", p.score, None, p.is_alert, MODEL_NAME, METHOD_VERSION, None,
        DetailsDraft(encoded), p.predicted_at, SqlDependent("created_at"),
    )


def prepare_batch(proposals: tuple[Computed, ...], manifest: dict, *, policy: PreparationPolicy,
                  provenance: ProvenanceAttestation,
                  authorization: AuthorizationDeclaration) -> ValidationResult:
    """Check supplied review/declaration data against pinned v1 policy, purely.

    This does not authenticate a reviewer, inspect Git, check a server or issue
    any write permission. Such external verification remains mandatory in ML 4.2B.
    """
    try:
        _require(type(proposals) is tuple, Code.INVALID_INPUT, "proposals")
        _require(not any(type(p) is Abstained for p in proposals), Code.ABSTENTION_REFUSED, "proposals")
        _require(len(proposals) == 2, Code.INCOMPLETE_BATCH, "proposals")
        _require(all(type(p) is Computed for p in proposals), Code.INVALID_PROPOSAL, "proposals")
        details = [_checked(p) for p in proposals]
        identities = tuple(p.prediction.measurement_fixture_id for p in proposals)
        _require(len(set(identities)) == 2, Code.DUPLICATE_TARGET, "targets")
        _require(set(identities) == set(TargetIdentity), Code.IDENTITY_MISMATCH, "targets")
        _require(details[0]["run_id"] == details[1]["run_id"]
                 and details[0]["prepared_at"] == details[1]["prepared_at"],
                 Code.INVALID_PROPOSAL, "batch.preparation_context")
        _require(type(policy) is PreparationPolicy and type(provenance) is ProvenanceAttestation,
                 Code.UNATTESTED_PROVENANCE, "review.type")
        validate_destination(policy.destination)
        _require(policy.calculation_revision == CALCULATION_REVISION
                 and policy.fixture_sha256 == FIXTURE_SHA256
                 and provenance.code_revision == policy.calculation_revision
                 and provenance.fixture_sha256 == policy.fixture_sha256
                 and _uuid(policy.approved_review_uuid)
                 and provenance.review_uuid == policy.approved_review_uuid
                 and provenance.attested is True,
                 Code.UNATTESTED_PROVENANCE, "review")
        _require(all(d["producer"]["code_revision"] == provenance.code_revision for d in details),
                 Code.UNATTESTED_PROVENANCE, "producer.code_revision")
        digest = manifest_sha256(manifest)
        _require(digest == FIXTURE_SHA256 and all(p.dataset_sha256 == digest for p in proposals),
                 Code.INVALID_FINGERPRINT, "manifest")
        by_id = {row["fixture_id"]: row for row in manifest["observations"]}
        for p, d in zip(proposals, details):
            expected_target = by_id[p.prediction.measurement_fixture_id]
            for field in ("timestamp", "available_at", "value", "quality", "unit"):
                expected = expected_target[field]
                if field in ("timestamp", "available_at"):
                    expected = utc_instant(expected)
                _require(d["target"][field] == expected, Code.INVALID_PROPOSAL, "target.manifest")
            day = 11 if p.prediction.measurement_fixture_id == TargetIdentity.NORMAL else 12
            _require(d["cutoff_utc"] == f"2026-01-{day:02d}T08:01:00.000000Z",
                     Code.INVALID_PROPOSAL, "target.cutoff")
            expected_ids = tuple(f"DEMO-M-{i:03d}" for i in range(day - 10, day))
            _require(p.reference_ids == expected_ids, Code.INVALID_PROPOSAL, "reference.window")
            reference = {"observations": [by_id[identity] for identity in expected_ids]}
            _require(manifest_sha256(reference) == p.reference_sha256,
                     Code.INVALID_FINGERPRINT, "reference.manifest")
        _require(type(authorization) is AuthorizationDeclaration
                 and _uuid(authorization.declaration_uuid), Code.AUTHORIZATION_MISMATCH, "declaration")
        validate_destination(authorization.destination)
        _require(authorization.destination == policy.destination,
                 Code.DESTINATION_MISMATCH, "declaration.destination")
        _require(authorization.dataset_sha256 == digest
                 and authorization.code_revision == CALCULATION_REVISION,
                 Code.AUTHORIZATION_MISMATCH, "declaration.content")
        _require(type(authorization.targets) is tuple and len(authorization.targets) == 2
                 and all(type(t) is AuthorizationTarget and type(t.identity) is TargetIdentity
                         for t in authorization.targets), Code.AUTHORIZATION_MISMATCH, "declaration.targets")
        _require({t.identity for t in authorization.targets} == set(TargetIdentity),
                 Code.AUTHORIZATION_MISMATCH, "declaration.identities")
        authorized = {t.identity: t for t in authorization.targets}
        prepared = []
        for p in sorted(proposals, key=lambda result: result.prediction.measurement_fixture_id):
            identity = TargetIdentity(p.prediction.measurement_fixture_id)
            key = target_key(p, policy.destination)
            content = project_content(p)
            claim = authorized[identity]
            _require(_digest(claim.reference_sha256) and _digest(claim.content_sha256),
                     Code.INVALID_FINGERPRINT, "declaration.fingerprints")
            _require(utc_instant(claim.cutoff_utc) == p.prediction.details["cutoff_utc"]
                     and claim.reference_sha256 == p.reference_sha256
                     and claim.content_sha256 == content.sha256,
                     Code.AUTHORIZATION_MISMATCH, "declaration.target")
            prepared.append(PreparedTarget(identity, key, content, _read_plan(p, key)))
        return ValidatedPreparation(PreparationDossier(
            policy.destination, provenance, authorization, tuple(prepared),
            canonical_bytes(manifest).decode("utf-8"),
        ))
    except ContractError as exc:
        return RejectedPreparation((ValidationIssue(exc.code, exc.field),))
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError) as exc:
        # Never include input values, DSNs or private declaration text in errors.
        return RejectedPreparation((ValidationIssue(Code.INVALID_PROPOSAL, "preparation"),))
