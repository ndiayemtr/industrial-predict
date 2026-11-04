"""Offline crypto with ephemeral keys/certificates; all observations are injected."""

import ast
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
import traceback
from unittest.mock import Mock

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from b2b_postgres_qualification import authority as a, evidence as e, validation as v
from b2b_postgres_qualification.contracts import ExecutionDisabled, Rejected
from b2b_postgres_qualification.test_contracts import (
    CAMPAIGN, INSTANCE, NOW, PRIVATE, FavorableDouble, approval, plan, observations,
    campaign as base_campaign, forbid_external_effects,
)


APPROVAL_ID = "55555555-5555-4555-8555-555555555555"
INITIAL_REVISION = "4b7e2a91c6d0"


def key_usage(ca):
    return x509.KeyUsage(digital_signature=True, content_commitment=False,
                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                         key_cert_sign=ca, crl_sign=ca, encipher_only=None, decipher_only=None)


@pytest.fixture(scope="module")
def certificates():
    # Never serialize or persist a private key. No fixed signing secret in Git.
    root_key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Synthetic B2B Test CA")])
    root = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(NOW - timedelta(days=1)).not_valid_after(NOW + timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=True, path_length=2), critical=True)
            .add_extension(key_usage(True), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256()))
    def leaf(host, *, expired=False):
        key = ec.generate_private_key(ec.SECP256R1())
        return (x509.CertificateBuilder()
                .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, host)]))
                .issuer_name(root.subject).public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(NOW - timedelta(days=3))
                .not_valid_after(NOW - timedelta(days=1) if expired else NOW + timedelta(days=5))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(key_usage(False), critical=True)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .add_extension(x509.SubjectAlternativeName([x509.DNSName(host)]), critical=False)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
                .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
                .sign(root_key, hashes.SHA256()).public_bytes(Encoding.DER))
    return root.public_bytes(Encoding.DER), leaf


@pytest.fixture
def campaign(base_campaign, certificates):
    return replace(base_campaign, ca_sha256=sha256(certificates[0]).hexdigest())


@pytest.fixture
def policy(certificates):
    return e.CollectorPolicy("synthetic-context", "1" * 64, "2" * 64,
                             NOW - timedelta(minutes=5), certificates[0])


@pytest.fixture
def packets(campaign, policy, certificates):
    leaf = certificates[1](campaign.host)
    values = []
    for observation in observations(campaign):
        facts = dict(observation.facts)
        if observation.kind == "postgres":
            facts["revision"] = INITIAL_REVISION
            observation = replace(observation, facts=tuple(sorted(facts.items())))
            kind = v.ROLE_KINDS[campaign.roles.index(facts["session_user"])]
            owner = kind in ("admin", "migrator")
            runtime = kind == "runtime"
            extra = dict(
                privilege_profile=kind, schema_usage="true", schema_create="true" if owner else "false",
                database_create="false", database_temp="false", role_memberships="0", session_select="true",
                session_insert="true" if owner or runtime else "false",
                session_update="*" if owner else "last_activity_at,replaced_by,revoked_at" if runtime else "",
                session_delete="true" if owner else "false", sequence_usage="true" if owner else "false",
                users_select="true", users_update="*" if owner else "id" if runtime else "",
                identities_select="true", identities_update="*" if owner else "id" if runtime else "",
                business_write="true" if owner else "false", role_admin="false")
        elif observation.kind == "docker":
            extra = dict(context_name="synthetic-context", endpoint_sha256="1" * 64,
                         image_id_sha256="2" * 64, container_networks=campaign.network_id,
                         volume_engine_id=campaign.engine_id, volume_driver="local", volume_scope="local",
                         volume_created_at=policy.volume_created_at.isoformat(timespec="microseconds"))
        else:
            facts["ca_sha256"] = campaign.ca_sha256
            observation = replace(observation, facts=tuple(sorted(facts.items())))
            extra = dict(peer_certificate_sha256=sha256(leaf).hexdigest(),
                         chain_verified="true", hostname_verified="true")
        values.append(e.EvidencePacket(observation, tuple(sorted(extra.items())),
                                       leaf if observation.kind == "tls" else None))
    return tuple(values)


@pytest.fixture
def signing_key():
    return ed25519.Ed25519PrivateKey.generate()


@pytest.fixture
def trusted(signing_key, approval):
    return a.TrustedKey(approval.authority_id, "synthetic-key",
                        signing_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw),
                        NOW - timedelta(hours=1), NOW + timedelta(hours=1), False)


def sign(campaign, plan, approval, signing_key, *, state="f" * 64, approval_id=APPROVAL_ID, key_id="synthetic-key"):
    payload = a.signing_bytes(campaign, plan, approval, approval_id=approval_id,
                              key_id=key_id, initial_state_sha256=state, now=NOW)
    return a.SignedApproval(approval_id, key_id, state, signing_key.sign(payload))


def verifier(trusted):
    return a.ApprovalVerifier(trusted_keys=(trusted,), replay_registry=a.MemoryReplayRegistry())


def verify(trusted, campaign, plan, approval, signed, *, state="f" * 64, now=NOW):
    return verifier(trusted).verify(campaign, plan, approval, signed,
                                    expected_initial_state_sha256=state, now=now)


def review(campaign, policy, packets):
    return e.review_evidence(campaign, policy, packets, now=NOW, revision=INITIAL_REVISION)


def test_valid_ed25519_signature_and_initial_evidence_binding(campaign, policy, packets, plan, approval, trusted, signing_key):
    state = e.evidence_fingerprint(campaign, policy, packets, now=NOW, revision=INITIAL_REVISION)
    assert state == e.evidence_fingerprint(campaign, policy, tuple(reversed(packets)), now=NOW, revision=INITIAL_REVISION)
    signed = sign(campaign, plan, approval, signing_key, state=state)
    result = verify(trusted, campaign, plan, approval, signed, state=state)
    assert result.signature_verified
    assert not result.authenticated and not result.execution_authorized and not result.real_attested
    with pytest.raises(ExecutionDisabled):
        v.request_execution(campaign, plan, approval, result)
    with pytest.raises(ExecutionDisabled):
        v.require_real_attestation(result)


@pytest.mark.parametrize("signature", [None, b"", bytes(64), "invalid"])
def test_absent_wrong_and_invalid_signature_rejected(campaign, plan, approval, trusted, signing_key, signature):
    signed = replace(sign(campaign, plan, approval, signing_key), signature=signature)
    with pytest.raises(Rejected):
        verify(trusted, campaign, plan, approval, signed)


def test_signature_from_untrusted_private_key_rejected(campaign, plan, approval, trusted):
    signed = sign(campaign, plan, approval, ed25519.Ed25519PrivateKey.generate())
    with pytest.raises(Rejected):
        verify(trusted, campaign, plan, approval, signed)


@pytest.mark.parametrize("change", [{"revoked": True}, {"authority_id": "unknown-authority"},
                                     {"key_id": "unknown-key"}, {"valid_from": NOW},
                                     {"valid_until": NOW}, {"valid_until": NOW + timedelta(seconds=1)}])
def test_unknown_revoked_or_out_of_window_authority(campaign, plan, approval, trusted, signing_key, change):
    signed = sign(campaign, plan, approval, signing_key)
    with pytest.raises(Rejected):
        verify(replace(trusted, **change), campaign, plan, approval, signed)


def test_approval_destination_and_migration_tampering_rejected(campaign, plan, approval, trusted, signing_key):
    signed = sign(campaign, plan, approval, signing_key)
    altered_campaign = replace(campaign, instance_id="66666666-6666-4666-8666-666666666666")
    altered_approval = replace(approval, destination_sha256=v.destination_fingerprint(altered_campaign))
    analysis = v.migration_plan("analysis", v.PUBLICATIONS[12:])
    analysis_approval = replace(approval, operation="analysis", plan_sha256=v.plan_fingerprint(analysis))
    for c, p, document, receipt in (
        (altered_campaign, plan, altered_approval, signed),
        (campaign, analysis, analysis_approval, signed),
        (campaign, plan, replace(approval, expires_at=approval.expires_at + timedelta(seconds=1)), signed),
        (campaign, plan, approval, replace(signed, approval_id=INSTANCE)),
        (campaign, plan, approval, replace(signed, initial_state_sha256="e" * 64)),
        (campaign, replace(plan, publications=(replace(plan.publications[0], sha256="e" * 64),)), approval, signed),
    ):
        with pytest.raises(Rejected):
            verify(trusted, c, p, document, receipt)


def test_expiry_and_state_mismatch_before_consumption(campaign, plan, approval, trusted, signing_key):
    signed = sign(campaign, plan, approval, signing_key)
    boundary = verifier(trusted)
    with pytest.raises(Rejected):
        boundary.verify(campaign, plan, approval, signed, expected_initial_state_sha256="e" * 64, now=NOW)
    with pytest.raises(Rejected):
        boundary.verify(campaign, plan, approval, signed, expected_initial_state_sha256="f" * 64, now=approval.expires_at)
    assert boundary.verify(campaign, plan, approval, signed, expected_initial_state_sha256="f" * 64, now=NOW).signature_verified


def test_invalid_signature_does_not_consume_but_valid_signature_is_single_use(campaign, plan, approval, trusted, signing_key):
    signed = sign(campaign, plan, approval, signing_key)
    boundary = verifier(trusted)
    with pytest.raises(Rejected):
        boundary.verify(campaign, plan, approval, replace(signed, signature=bytes(64)), expected_initial_state_sha256="f" * 64, now=NOW)
    boundary.verify(campaign, plan, approval, signed, expected_initial_state_sha256="f" * 64, now=NOW)
    with pytest.raises(Rejected):
        boundary.verify(campaign, plan, approval, signed, expected_initial_state_sha256="f" * 64, now=NOW)
    # Explicit limitation: another in-memory registry has no knowledge of this use.
    assert verify(trusted, campaign, plan, approval, signed).signature_verified


def test_concurrent_replay_only_one_consumption(campaign, plan, approval, trusted, signing_key):
    boundary = verifier(trusted)
    signed = sign(campaign, plan, approval, signing_key)
    def attempt(_):
        try:
            boundary.verify(campaign, plan, approval, signed, expected_initial_state_sha256="f" * 64, now=NOW)
            return "verified"
        except Rejected:
            return "rejected"
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, (1, 2)))
    assert sorted(outcomes) == ["rejected", "verified"]


def test_favorable_double_or_submission_key_cannot_replace_trust(campaign, plan, approval, trusted, signing_key):
    signed = sign(campaign, plan, approval, signing_key)
    with pytest.raises(Rejected):
        a.ApprovalVerifier(trusted_keys=(FavorableDouble(),), replay_registry=a.MemoryReplayRegistry())
    with pytest.raises(Rejected):
        a.ApprovalVerifier(trusted_keys=(trusted,), replay_registry=Mock())
    with pytest.raises(TypeError):
        a.SignedApproval(APPROVAL_ID, "synthetic-key", "f" * 64, signed.signature, public_key=trusted.public_key)
    with pytest.raises(ExecutionDisabled):
        v.request_execution(authority=FavorableDouble(), signed=signed)


def test_offline_certificate_chain_and_all_three_adapters(campaign, policy, packets):
    result = review(campaign, policy, packets)
    assert not result.real_attested and not result.authenticated and not result.execution_authorized
    source = Mock()
    with pytest.raises(ExecutionDisabled):
        e.collect_real_evidence(source=source)
    assert source.mock_calls == []


@pytest.mark.parametrize("position,key,value", [
    (0, "context_name", "other-context"), (0, "endpoint_sha256", "f" * 64),
    (0, "image_id_sha256", "f" * 64), (0, "container_networks", "f" * 64),
    (0, "volume_engine_id", INSTANCE), (0, "volume_driver", "remote"),
    (0, "volume_created_at", NOW.isoformat()),
    (5, "session_update", "*"), (5, "session_delete", "true"),
    (5, "schema_create", "true"), (5, "business_write", "true"),
    (5, "users_update", "*"), (5, "sequence_usage", "true"),
    (2, "chain_verified", "false"), (2, "hostname_verified", "false"),
])
def test_docker_postgres_tls_supplemental_mismatches(campaign, policy, packets, position, key, value):
    values = list(packets)
    extra = dict(values[position].supplemental)
    extra[key] = value
    values[position] = replace(values[position], supplemental=tuple(sorted(extra.items())))
    with pytest.raises(Rejected):
        review(campaign, policy, tuple(values))


@pytest.mark.parametrize("kind", ["hostname", "expired", "tampered", "malformed", "trailing"])
def test_certificate_claims_are_not_sufficient(campaign, policy, packets, certificates, kind):
    original = packets[2].certificate_der
    der = {
        "hostname": lambda: certificates[1]("wrong.example.invalid"),
        "expired": lambda: certificates[1](campaign.host, expired=True),
        "tampered": lambda: original[:-1] + bytes([original[-1] ^ 1]),
        "malformed": lambda: PRIVATE.encode(),
        "trailing": lambda: original + b"trailing",
    }[kind]()
    extra = dict(peer_certificate_sha256=sha256(der).hexdigest(), chain_verified="true", hostname_verified="true")
    packet = replace(packets[2], certificate_der=der, supplemental=tuple(sorted(extra.items())))
    with pytest.raises(Rejected):
        review(campaign, policy, (*packets[:2], packet, *packets[3:]))


def test_ca_unverified_transport_staleness_and_real_claims_rejected(campaign, policy, packets):
    with pytest.raises(Rejected):
        review(campaign, replace(policy, trusted_ca_der=b"wrong CA"), packets)
    for change in ({"provenance": "real"}, {"observed_at": NOW - timedelta(seconds=40), "started_at": NOW - timedelta(seconds=41)},
                   {"destination_sha256": "f" * 64}):
        packet = replace(packets[0], observation=replace(packets[0].observation, **change))
        with pytest.raises(Rejected):
            review(campaign, policy, (packet, *packets[1:]))
    for key, value in (("sslmode", "require"), ("ca_sha256", "f" * 64), ("verified_host", "localhost")):
        facts = dict(packets[2].observation.facts)
        facts[key] = value
        packet = replace(packets[2], observation=replace(packets[2].observation, facts=tuple(sorted(facts.items()))))
        with pytest.raises(Rejected):
            review(campaign, policy, (*packets[:2], packet, *packets[3:]))


def test_manual_results_cannot_become_real_proofs(campaign, policy, packets):
    fabricated = a.SignatureReview(APPROVAL_ID, "synthetic-authority", "synthetic-key", "f" * 64)
    assert fabricated.signature_verified and not fabricated.real_attested and not fabricated.authenticated
    with pytest.raises(TypeError):
        replace(fabricated, real_attested=True)
    with pytest.raises(ExecutionDisabled):
        v.require_real_attestation(fabricated)
    with pytest.raises(FrozenInstanceError):
        packets[0].certificate_der = b"modified"


def test_crypto_and_collector_diagnostics_are_constant(campaign, policy, packets, plan, approval, trusted, signing_key):
    signed = sign(campaign, plan, approval, signing_key)
    try:
        raise RuntimeError(PRIVATE)
    except RuntimeError:
        for call in (
            lambda: verify(trusted, campaign, plan, approval, replace(signed, signature=PRIVATE.encode())),
            lambda: review(campaign, replace(policy, trusted_ca_der=PRIVATE.encode()), packets),
            lambda: e.collect_real_evidence(PRIVATE),
        ):
            with pytest.raises((Rejected, ExecutionDisabled)) as caught:
                call()
            assert caught.value.__context__ is None and caught.value.__cause__ is None
            assert PRIVATE not in "".join(traceback.format_exception(caught.value))
    for obj in (replace(trusted, public_key=PRIVATE.encode()), replace(policy, trusted_ca_der=PRIVATE.encode()),
                replace(signed, signature=PRIVATE.encode()), replace(packets[2], certificate_der=PRIVATE.encode())):
        assert PRIVATE not in repr(obj)


def test_new_modules_have_no_acquisition_or_application_imports():
    directory = Path(__file__).parent
    for filename in ("authority.py", "evidence.py"):
        tree = ast.parse((directory / filename).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) else [node.module] if isinstance(node, ast.ImportFrom) else []
            assert not any(name.startswith(("socket", "subprocess", "ssl", "http", "psycopg", "sqlalchemy", "docker", "app.")) for name in modules)
