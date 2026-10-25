"""Offline persistence preparation; no SQL fixtures, engine, HTTP or training."""

import ast
import builtins
from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, fields, replace
import hashlib
import json
from pathlib import Path
import socket

import pytest

from app.anomaly_detection.p101_contracts import Computed, LogicalPrediction
from app.anomaly_detection.p101_core import evaluate
from app.p101_persistence.canonical import build_key, canonical_projection, compare_retry
from app.p101_persistence.contracts import (
    CALCULATION_REVISION, FIXTURE_SHA256, AuthorizationDeclaration, AuthorizationTarget,
    CanonicalProjection, ContractError, DestinationDeclaration, PreparationPolicy,
    ProvenanceAttestation, RejectedPreparation, RetryDisposition, SqlDependent,
    TargetIdentity, ValidatedPreparation, ValidationCode as Code,
)
from app.p101_persistence.preparation import prepare_batch, project_content, target_key


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "p101_anomaly" / "fixtures" / "p101-temperature-v1.json"
RUN = "00000000-0000-4000-8000-000000000001"
NEW_RUN = "00000000-0000-4000-8000-000000000002"
REVIEW = "00000000-0000-4000-8000-000000000003"
INSTANCE = "00000000-0000-4000-8000-000000000004"


@pytest.fixture(autouse=True)
def forbid_external_access(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("SQL/network/training/artifact access is forbidden")

    original = builtins.__import__

    def guarded(name, *args, **kwargs):
        if name.split(".")[0] in {"sqlalchemy", "psycopg", "httpx", "requests", "joblib", "sklearn"}:
            forbidden()
        if name.startswith(("app.core.database", "app.core.config", "app.models", "app.services", "app.ml")):
            forbidden()
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


def authorize(proposals, destination):
    return AuthorizationDeclaration(NEW_RUN, destination, FIXTURE_SHA256,
        CALCULATION_REVISION, tuple(AuthorizationTarget(
            TargetIdentity(p.prediction.measurement_fixture_id),
            p.prediction.details["cutoff_utc"], p.reference_sha256, project_content(p).sha256,
        ) for p in proposals))


@pytest.fixture
def context():
    manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
    proposals = tuple(evaluate(manifest, f"DEMO-M-{day:03d}",
        cutoff=f"2026-01-{day:02d}T08:01:00Z", prepared_at="2026-02-01T00:00:00Z",
        run_id=RUN, code_revision=CALCULATION_REVISION) for day in (11, 12))
    assert all(type(p) is Computed for p in proposals)
    # These are fictitious declaration values, never connection parameters used.
    destination = DestinationDeclaration(INSTANCE, "sandbox.invalid", 55432,
                                         "industrial_predict_ml_sandbox", "p101_pilot")
    return dict(proposals=proposals, manifest=manifest,
                policy=PreparationPolicy(destination, REVIEW),
                provenance=ProvenanceAttestation(CALCULATION_REVISION, FIXTURE_SHA256, REVIEW, True),
                authorization=authorize(proposals, destination))


def assert_rejected(result, code=None):
    assert isinstance(result, RejectedPreparation)
    assert result.status == "rejected" and result.dossier is None
    assert len(result.issues) == 1
    if code is not None:
        assert result.issues[0].code == code


def change_details(proposal, change):
    details = proposal.prediction.details
    change(details)
    return replace(proposal, prediction=replace(proposal.prediction, details_json=json.dumps(details)))


def test_nominal_batch_and_fourteen_conceptual_fields(context):
    result = prepare_batch(**context)
    assert isinstance(result, ValidatedPreparation)
    dossier = result.dossier
    assert not dossier.write_authorized and not dossier.destination_verified and not dossier.persistence_ready
    assert [target.identity for target in dossier.targets] == [TargetIdentity.NORMAL, TargetIdentity.ANOMALY]
    assert [target.read_plan.score for target in dossier.targets] == [0, 1]
    expected_fields = {"id", "equipment_id", "sensor_id", "measurement_id", "prediction_type", "score",
        "level", "is_alert", "model_name", "model_version", "horizon_hours", "details", "predicted_at", "created_at"}
    for target in dossier.targets:
        plan = target.read_plan
        assert {f.name for f in fields(plan)} == expected_fields
        assert all(type(getattr(plan, name)) is SqlDependent for name in
                   ("id", "equipment_id", "sensor_id", "measurement_id", "created_at"))
        assert plan.prediction_type == "anomaly" and plan.model_name == "statistical_deviation"
        assert plan.model_version == "p101-stat-v1" and plan.level is plan.horizon_hours is None
        assert type(plan.is_alert) is bool and plan.is_alert == bool(plan.score)
        assert len(plan.details.candidate_json.encode()) <= 6000 - 1024
        candidate = plan.details.candidate
        assert candidate["idempotency_key"] == target.key.projection.sha256
        assert candidate["producer"] == {"method_version": "p101-stat-v1", "code_revision": CALCULATION_REVISION}
        assert len(candidate["reference"]["observations"]) == 10
        assert "measurement_id" not in candidate["target"]
        assert candidate["asset"]["equipment_id"] == "DEMO-EQ-001"  # logical, never numeric SQL


def test_immutability_and_order(context):
    before = deepcopy(context)
    result = prepare_batch(**context)
    assert context == before
    shuffled = dict(context, proposals=tuple(reversed(context["proposals"])))
    shuffled["manifest"] = dict(reversed(list(context["manifest"].items())))
    shuffled["manifest"]["observations"] = list(reversed(context["manifest"]["observations"]))
    assert prepare_batch(**shuffled) == result
    with pytest.raises(FrozenInstanceError):
        result.dossier.targets = ()
    candidate = result.dossier.targets[0].read_plan.details.candidate
    candidate["synthetic"] = False
    assert result.dossier.targets[0].read_plan.details.candidate["synthetic"] is True
    assert context["proposals"][0].prediction.details["producer"]["revision_status"] == "requires_validation"


def test_abstention_refused(context):
    abstained = evaluate(context["manifest"], "DEMO-M-001", cutoff="2026-01-01T08:01:00Z",
                         prepared_at="2026-02-01T00:00:00Z", run_id=RUN)
    context["proposals"] = (abstained, context["proposals"][1])
    assert_rejected(prepare_batch(**context), Code.ABSTENTION_REFUSED)


@pytest.mark.parametrize("count", [0, 1, 3])
def test_incomplete_batch(context, count):
    context["proposals"] = (context["proposals"] * 2)[:count]
    assert_rejected(prepare_batch(**context), Code.INCOMPLETE_BATCH)


def test_duplicate_target(context):
    context["proposals"] = (context["proposals"][0],) * 2
    assert_rejected(prepare_batch(**context), Code.DUPLICATE_TARGET)


@pytest.mark.parametrize("partial", [{}, {"status": "computed"}, None])
def test_partial_proposal(context, partial):
    context["proposals"] = (partial, context["proposals"][1])
    assert_rejected(prepare_batch(**context), Code.INVALID_PROPOSAL)


@pytest.mark.parametrize("field,value", [("equipment_fixture_id", "OTHER-EQ"),
    ("sensor_fixture_id", "OTHER-SENSOR"), ("measurement_fixture_id", "DEMO-M-010")])
def test_wrong_identity(context, field, value):
    first, second = context["proposals"]
    context["proposals"] = (replace(first, prediction=replace(first.prediction, **{field: value})), second)
    assert_rejected(prepare_batch(**context), Code.IDENTITY_MISMATCH)


@pytest.mark.parametrize("field,value", [("prediction_type", "rul"), ("model_name", "other"),
    ("model_version", "p101-stat-v2")])
def test_wrong_version(context, field, value):
    first, second = context["proposals"]
    context["proposals"] = (replace(first, prediction=replace(first.prediction, **{field: value})), second)
    assert_rejected(prepare_batch(**context), Code.VERSION_MISMATCH)


@pytest.mark.parametrize("field,value", [("attested", False), ("attested", 1),
    ("code_revision", "a" * 40), ("code_revision", "invalid"),
    ("fixture_sha256", "0" * 64), ("review_uuid", NEW_RUN)])
def test_unattested_provenance(context, field, value):
    context["provenance"] = replace(context["provenance"], **{field: value})
    assert_rejected(prepare_batch(**context), Code.UNATTESTED_PROVENANCE)


def test_pending_calculation_revision(context):
    context["proposals"] = tuple(change_details(p, lambda d: d["producer"].update(
        code_revision=None, revision_status="pending_commit")) for p in context["proposals"])
    assert_rejected(prepare_batch(**context), Code.UNATTESTED_PROVENANCE)


@pytest.mark.parametrize("field", ["dataset_sha256", "reference_sha256"])
@pytest.mark.parametrize("value", ["invalid", "0"*64])
def test_invalid_computed_fingerprints(context, field, value):
    first, second = context["proposals"]
    context["proposals"] = (replace(first, **{field: value}), second)
    assert_rejected(prepare_batch(**context), Code.INVALID_FINGERPRINT)


def test_fixture_mismatch(context):
    context["manifest"]["observations"][0]["value"] = 66
    assert_rejected(prepare_batch(**context), Code.INVALID_FINGERPRINT)


def test_stable_canonicalization_and_numeric_unicode_rules():
    first = canonical_projection({"z": 65.0, "label": "e\u0301", "score": 0,
        "is_alert": False, "level": None, "cutoff_utc": "2026-01-11T09:01:00+01:00"})
    second = canonical_projection({"level": None, "is_alert": False, "score": 0.0,
        "cutoff_utc": "2026-01-11T08:01:00.000000Z", "label": "é", "z": 65})
    assert first == second
    assert first.canonical_json == ('{"cutoff_utc":"2026-01-11T08:01:00.000000Z",'
        '"is_alert":false,"label":"é","level":null,"score":"0","z":"65"}')
    assert hashlib.sha256(first.canonical_json.encode()).hexdigest() == first.sha256
    assert not first.canonical_json.encode().startswith(b"\xef\xbb\xbf")
    with pytest.raises(ContractError):
        canonical_projection({"e\u0301": 1, "é": 2})


def test_retry_new_run_and_preparation_time(context):
    original = prepare_batch(**context).dossier
    updated = tuple(change_details(p, lambda d: d.update(
        run_id=NEW_RUN, prepared_at="2026-03-01T00:00:00.000000Z")) for p in context["proposals"])
    context["proposals"] = updated
    retry = prepare_batch(**context).dossier
    for old, new in zip(original.targets, retry.targets):
        assert old.key == new.key and old.content == new.content
        assert old.read_plan.details != new.read_plan.details
        assert compare_retry(old.key, old.content, new.key, new.content) == RetryDisposition.IDENTICAL_RETRY
        assert not {"run_id", "prepared_at", "created_at", "equipment_id", "sensor_id", "measurement_id"} & asdict(new.key.components).keys()


def test_content_conflict_and_forged_digest(context):
    target = prepare_batch(**context).dossier.targets[0]
    altered = json.loads(target.content.canonical_json)
    altered["prediction"]["score"] = "1"
    content = canonical_projection(altered)
    assert compare_retry(target.key, target.content, target.key, content) == RetryDisposition.CONTENT_CONFLICT
    with pytest.raises(ContractError) as error:
        compare_retry(target.key, target.content, target.key, replace(content, sha256="0"*64))
    assert error.value.code == Code.INVALID_FINGERPRINT


@pytest.mark.parametrize("changes", [{"model_version": "p101-stat-v2"},
    {"cutoff_utc": "2026-01-11T08:02:00Z"}, {"reference_sha256": "0"*64},
    {"code_revision": "a"*40}, {"instance_uuid": NEW_RUN}])
def test_key_identity_change_is_not_retry(context, changes):
    target = prepare_batch(**context).dossier.targets[0]
    key = build_key(replace(target.key.components, **changes))
    assert target.key.projection.sha256 != key.projection.sha256
    assert compare_retry(target.key, target.content, key, target.content) == RetryDisposition.DIFFERENT_KEY


def test_changed_cutoff_rejected_by_batch_contract(context):
    first, second = context["proposals"]
    changed = change_details(first, lambda d: d.update(cutoff_utc="2026-01-11T08:02:00.000000Z"))
    context["proposals"] = (changed, second)
    assert_rejected(prepare_batch(**context), Code.INVALID_PROPOSAL)


@pytest.mark.parametrize("number", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_proposal_and_projection(context, number):
    first, second = context["proposals"]
    context["proposals"] = (change_details(first, lambda d: d["statistics"].update(mean=number)), second)
    assert_rejected(prepare_batch(**context))
    with pytest.raises(ContractError):
        canonical_projection({"number": number})


def test_json_limits_and_duplicate_properties(context):
    first, second = context["proposals"]
    huge = replace(first, prediction=replace(first.prediction, details_json=" " * 6001))
    assert_rejected(prepare_batch(**dict(context, proposals=(huge, second))), Code.JSON_LIMIT)
    duplicate = first.prediction.details_json.replace('"synthetic":true', '"synthetic":false,"synthetic":true')
    assert duplicate != first.prediction.details_json
    broken = replace(first, prediction=replace(first.prediction, details_json=duplicate))
    assert_rejected(prepare_batch(**dict(context, proposals=(broken, second))))
    for value in ({"x": "x"*241}, {"x": "x"*240, **{str(i): "x"*240 for i in range(100)}},
                  {"a": {"b": {"c": {"d": {"e": {"f": {"g": {"h": 1}}}}}}}}):
        with pytest.raises(ContractError) as error:
            canonical_projection(value)
        assert error.value.code == Code.JSON_LIMIT


@pytest.mark.parametrize("field,value", [("database", "industrial_predict_dev"),
    ("role", "ui47_app"), ("host", "postgresql://private:secret@host/db"),
    ("port", True), ("instance_uuid", "invalid")])
def test_bad_destination(context, field, value):
    bad = replace(context["policy"].destination, **{field: value})
    context["policy"] = replace(context["policy"], destination=bad)
    result = prepare_batch(**context)
    assert_rejected(result, Code.DESTINATION_MISMATCH)
    assert str(value) not in repr(result) or value is True


def test_destination_differs_from_declaration(context):
    bad = replace(context["authorization"].destination, port=55433)
    context["authorization"] = replace(context["authorization"], destination=bad)
    assert_rejected(prepare_batch(**context), Code.DESTINATION_MISMATCH)


@pytest.mark.parametrize("kind", ["duplicate", "incomplete", "content", "fingerprint"])
def test_authorization_content_is_checked(context, kind):
    declaration = context["authorization"]
    first, second = declaration.targets
    if kind == "duplicate":
        targets = (first, first)
    elif kind == "incomplete":
        targets = (first,)
    elif kind == "content":
        targets = (replace(first, content_sha256="0"*64), second)
    else:
        targets = (replace(first, reference_sha256="invalid"), second)
    context["authorization"] = replace(declaration, targets=targets)
    assert_rejected(prepare_batch(**context))


def test_computed_envelope_is_validated(context):
    first, second = context["proposals"]
    context["proposals"] = (replace(first, statistics=replace(first.statistics, mean=66)), second)
    assert_rejected(prepare_batch(**context), Code.INVALID_PROPOSAL)


def test_no_database_service_or_executable_side_effects_in_modules():
    package = ROOT / "backend" / "app" / "p101_persistence"
    forbidden = {"sqlalchemy", "psycopg", "socket", "httpx", "requests", "joblib", "sklearn", "subprocess"}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] not in forbidden for alias in node.names)
            if isinstance(node, ast.ImportFrom):
                assert node.module.split(".")[0] not in forbidden
                assert not node.module.startswith(("app.core", "app.models", "app.services"))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"connect", "commit", "flush", "fit", "fit_predict", "execute"}
