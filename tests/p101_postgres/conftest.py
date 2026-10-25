"""Only simulated sessions and pure SQL compilation; no database fixture."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import socket
from pathlib import Path

import pytest
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from p101_persistence.test_contracts import context
from app.p101_persistence.preparation import prepare_batch
from app.p101_postgres.runtime import ApprovalVerifier, ExecutionApproval, SandboxConfig, dossier_fingerprint, guard_policy_fingerprint, RELEASE_PATHS


NOW = datetime(2026, 4, 1, tzinfo=timezone.utc)
TEST_VERIFICATION_KEY = b"unit-test-only-independent-approval-key-000000"


@pytest.fixture(autouse=True)
def no_real_database_or_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("B-1 forbids real database/network execution")

    for cls, name in ((Engine, "connect"), (Connection, "execute"), (Session, "execute"),
                      (Session, "flush"), (Session, "commit")):
        monkeypatch.setattr(cls, name, forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


@pytest.fixture
def dossier(context):
    result = prepare_batch(**context)
    assert result.status == "validated_offline"
    return result.dossier


@pytest.fixture
def config(dossier):
    root = Path(__file__).resolve().parents[2]
    evidence = tuple((path, hashlib.sha256((root/path).read_bytes()).hexdigest()) for path in RELEASE_PATHS)
    return SandboxConfig(dossier.destination, "127.0.0.2", 5432, "p101_owner", "p101_reader",
                         "a" * 40, "unit-test-ca.pem", "unit-test-password-only", evidence)


def signed_approval(dossier, config, **changes):
    approval = ExecutionApproval("00000000-0000-4000-8000-000000000008", dossier_fingerprint(dossier),
        config.persistence_revision, (NOW + timedelta(days=1)).isoformat(), guard_policy_fingerprint(config), "")
    approval = replace(approval, **changes)
    signature = hmac.new(TEST_VERIFICATION_KEY, approval.payload(config.destination), hashlib.sha256).hexdigest()
    return replace(approval, signature=signature)


@pytest.fixture
def approval(dossier, config):
    return signed_approval(dossier, config)


@pytest.fixture
def verifier():
    return ApprovalVerifier(TEST_VERIFICATION_KEY)


@pytest.fixture
def sources(dossier):
    rows = [
        {"kind": "company", "id": 201, "payload": {"code": "MLDEMO-COMP-P101"}},
        {"kind": "site", "id": 301, "payload": {"code": "MLDEMO-SITE-P101", "company_id": 201}},
        {"kind": "equipment", "id": 401, "payload": {"code": "MLDEMO-EQ-P101", "site_id": 301,
            "equipment_type": "pump", "name": "Pompe P101 — démonstration synthétique"}},
        {"kind": "sensor", "id": 501, "payload": {"code": "MLDEMO-SEN-P101-TEMP", "equipment_id": 401,
            "sensor_type": "temperature", "unit": "°C"}},
    ]
    for index, row in enumerate(json.loads(dossier.manifest_canonical_json)["observations"], 1):
        rows.append({"kind": "measurement", "id": 1000 + index, "payload": {
            "sensor_id": 501, "timestamp": row["timestamp"], "value": float(row["value"]), "quality": "good"}})
    return tuple(rows)
