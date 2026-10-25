from copy import deepcopy
from dataclasses import replace
import json

import pytest

from app.p101_postgres.mapping import map_prediction, validate_dossier, validate_read, validate_sources
from app.p101_postgres.runtime import GuardRejected, PersistenceError
from app.p101_postgres.session import create_session_factory
from p101_postgres.conftest import NOW, signed_approval


def test_validated_dossier_is_rebuilt(dossier):
    before = deepcopy(dossier)
    validate_dossier(dossier)
    assert dossier == before
    invalid = replace(dossier, targets=(dossier.targets[0],))
    with pytest.raises(PersistenceError):
        validate_dossier(invalid)
    with pytest.raises(PersistenceError):
        validate_dossier(None)


def test_no_dossier_is_an_execution_approval(dossier, config, approval, verifier):
    verifier.verify(approval, dossier, config, NOW)
    with pytest.raises(GuardRejected):
        verifier.verify(dossier.authorization, dossier, config, NOW)
    with pytest.raises(GuardRejected):
        verifier.verify(replace(approval, signature="0" * 64), dossier, config, NOW)
    with pytest.raises(GuardRejected):
        verifier.verify(signed_approval(dossier, config, expires_at="2026-03-01T00:00:00Z"), dossier, config, NOW)
    with pytest.raises(GuardRejected):
        verifier.verify(signed_approval(dossier, config, dossier_sha256="0"*64), dossier, config, NOW)
    with pytest.raises(GuardRejected):
        verifier.verify(signed_approval(dossier, config, persistence_revision="b"*40), dossier, config, NOW)


def test_approval_binds_effective_guard_policy(dossier, config, approval, verifier):
    for changed in (replace(config, server_port=5433), replace(config, server_address="127.0.0.3"),
                    replace(config, tls_root_certificate="different-ca.pem")):
        with pytest.raises(GuardRejected):
            verifier.verify(approval, dossier, changed, NOW)


def test_authenticated_release_manifest_does_not_prove_wrong_bytes(dossier, config, verifier):
    evidence = list(config.release_files)
    evidence[0] = (evidence[0][0], "0"*64)
    changed = replace(config, release_files=tuple(evidence))
    token = signed_approval(dossier, changed)
    with pytest.raises(GuardRejected, match="release"):
        verifier.verify(token, dossier, changed, NOW)


@pytest.mark.parametrize("field,value", [("database", "industrial_predict_dev"),
    ("host", "unknown.invalid"), ("role", "ui47_app"), ("port", 1)])
def test_declared_destination_tamper_rejected(dossier, config, approval, verifier, field, value):
    config = replace(config, destination=replace(config.destination, **{field: value}))
    with pytest.raises((GuardRejected, ValueError)):
        verifier.verify(approval, dossier, config, NOW)


def test_factory_is_explicit_lazy_and_has_no_environment_fallback(config, monkeypatch):
    import app.p101_postgres.session as module
    import os
    for key in list(os.environ):
        if key.startswith("PG"):
            monkeypatch.delenv(key)
    monkeypatch.setenv("DATABASE_URL", "ignored")
    captured = {}

    def engine_spy(url, **kwargs):
        captured.update(url=url, **kwargs)
        return "simulated-engine"

    monkeypatch.setattr(module, "create_engine", engine_spy)
    monkeypatch.setattr(module, "sessionmaker", lambda **kw: kw)
    factory = create_session_factory(config)
    assert factory == dict(bind="simulated-engine", autoflush=False, expire_on_commit=False)
    assert captured["url"].database == config.destination.database
    assert captured["url"].password == config.password
    assert captured["connect_args"]["sslmode"] == "verify-full"
    assert captured["hide_parameters"] is True and captured["isolation_level"] == "READ COMMITTED"
    monkeypatch.setenv("PGSERVICE", "forbidden")
    with pytest.raises(ValueError, match="libpq"):
        create_session_factory(config)
    assert config.password not in repr(config)


def test_fourteen_fields_and_final_details(dossier, sources):
    mapping = validate_sources(dossier, sources)
    before = deepcopy(dossier)
    row = map_prediction(dossier, dossier.targets[0], mapping, 9001, NOW)
    assert len(row) == 14 and row["id"] == 9001 and row["measurement_id"] == 1011
    assert row["equipment_id"] == 401 and row["sensor_id"] == 501
    assert row["score"] == 0 and row["is_alert"] is False
    assert row["level"] is row["horizon_hours"] is None
    assert row["created_at"] == "2026-04-01T00:00:00.000000Z"
    assert row["predicted_at"] == "2026-01-11T08:00:00.000000Z"
    assert row["details"]["target"]["measurement_id"] == 1011
    assert [r["measurement_id"] for r in row["details"]["reference"]["observations"]] == list(range(1001, 1011))
    assert len(json.dumps(row["details"], ensure_ascii=False).encode()) <= 6000
    assert "revision_status" not in row["details"]["producer"]
    validate_read(dossier, dossier.targets[0], mapping, row)
    assert dossier == before


@pytest.mark.parametrize("kind", ["missing", "duplicate", "parent", "unit", "quality", "value", "nan", "time", "id"])
def test_source_checks(dossier, sources, kind):
    rows = deepcopy(list(sources))
    if kind == "missing": rows.pop()
    elif kind == "duplicate": rows[-1] = deepcopy(rows[-2])
    elif kind == "parent": rows[3]["payload"]["equipment_id"] = 999
    elif kind == "unit": rows[3]["payload"]["unit"] = "K"
    elif kind == "quality": rows[-1]["payload"]["quality"] = "bad"
    elif kind == "value": rows[-1]["payload"]["value"] = 71
    elif kind == "nan": rows[-1]["payload"]["value"] = float("nan")
    elif kind == "time": rows[-1]["payload"]["timestamp"] = "2026-01-12T08:00:00"
    elif kind == "id": rows[-1]["id"] = True
    with pytest.raises(PersistenceError):
        validate_sources(dossier, tuple(rows))


@pytest.mark.parametrize("kind", ["unknown", "score", "alert", "id", "details_unknown", "ref_id", "date", "oversize"])
def test_final_read_rejects_inconsistent_or_unbounded_json(dossier, sources, kind):
    mapping = validate_sources(dossier, sources)
    target = dossier.targets[0]
    row = map_prediction(dossier, target, mapping, 9001, NOW)
    if kind == "unknown": row["extra"] = None
    elif kind == "score": row["score"] = float("inf")
    elif kind == "alert": row["is_alert"] = True
    elif kind == "id": row["id"] = 0
    elif kind == "details_unknown": row["details"]["extra"] = True
    elif kind == "ref_id": row["details"]["reference"]["observations"][0]["measurement_id"] = True
    elif kind == "date": row["created_at"] = "2025-01-01T00:00:00Z"
    elif kind == "oversize": row["details"]["reason"] = "x" * 6000
    with pytest.raises(PersistenceError):
        validate_read(dossier, target, mapping, row)
