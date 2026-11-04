"""Injected-only evidence adapters and offline X.509 verification. No transports."""

from dataclasses import asdict, dataclass
from datetime import datetime
from hashlib import sha256
import json
from typing import Protocol

from b2b_postgres_qualification.contracts import Observation, Offline, Review, ExecutionDisabled, deny
from b2b_postgres_qualification import validation as v


@dataclass(frozen=True, slots=True, repr=False)
class CollectorPolicy(Offline):
    """Independent expected context/image/volume/CA, supplied by trusted test setup."""

    context_name: str
    endpoint_sha256: str
    image_id_sha256: str
    volume_created_at: datetime
    trusted_ca_der: bytes


@dataclass(frozen=True, slots=True, repr=False)
class EvidencePacket(Offline):
    observation: Observation
    supplemental: tuple[tuple[str, str], ...]
    certificate_der: bytes | None = None
    intermediates_der: tuple[bytes, ...] = ()


class ObservationSource(Protocol):
    def capture(self) -> tuple[EvidencePacket, ...]:
        """Future acquisition boundary; no implementation or caller is installed."""
        ...


def _policy(campaign, policy):
    v.require(type(policy) is CollectorPolicy)
    v.text(policy.context_name)
    v.digest(policy.endpoint_sha256)
    v.digest(policy.image_id_sha256)
    v.utc(policy.volume_created_at)
    v.require(type(policy.trusted_ca_der) is bytes and 0 < len(policy.trusted_ca_der) <= 16384)
    v.require(sha256(policy.trusted_ca_der).hexdigest() == campaign.ca_sha256)


def _supplemental(packet):
    v.require(type(packet.supplemental) is tuple and len(packet.supplemental) <= 24)
    for pair in packet.supplemental:
        v.require(type(pair) is tuple and len(pair) == 2 and all(type(s) is str for s in pair))
        v.require(len(pair[0]) <= 64 and len(pair[1]) <= 256)
    v.require(packet.supplemental == tuple(sorted(packet.supplemental)))
    data = dict(packet.supplemental)
    v.require(len(data) == len(packet.supplemental))
    return data


def _docker_adapter(campaign, policy, packet):
    v.require(packet.certificate_der is None and packet.intermediates_der == ())
    expected = dict(context_name=policy.context_name, endpoint_sha256=policy.endpoint_sha256,
                    image_id_sha256=policy.image_id_sha256, container_networks=campaign.network_id,
                    volume_engine_id=campaign.engine_id, volume_driver="local", volume_scope="local",
                    volume_created_at=policy.volume_created_at.isoformat(timespec="microseconds"))
    v.require(_supplemental(packet) == expected)


def _postgres_adapter(campaign, packet):
    v.require(packet.certificate_der is None and packet.intermediates_der == ())
    role = dict(packet.observation.facts)["session_user"]
    kind = v.ROLE_KINDS[campaign.roles.index(role)]
    owner = kind in ("admin", "migrator")
    runtime = kind == "runtime"
    expected = dict(
        privilege_profile=kind, schema_usage="true", schema_create="true" if owner else "false",
        database_create="false", database_temp="false", role_memberships="0",
        session_select="true", session_insert="true" if owner or runtime else "false",
        session_update="*" if owner else "last_activity_at,replaced_by,revoked_at" if runtime else "",
        session_delete="true" if owner else "false", sequence_usage="true" if owner else "false",
        users_select="true", users_update="*" if owner else "id" if runtime else "",
        identities_select="true", identities_update="*" if owner else "id" if runtime else "",
        business_write="true" if owner else "false", role_admin="false",
    )
    v.require(_supplemental(packet) == expected)


def _tls_adapter(campaign, policy, packet, now):
    v.require(type(packet.certificate_der) is bytes and 0 < len(packet.certificate_der) <= 16384)
    v.require(type(packet.intermediates_der) is tuple and len(packet.intermediates_der) <= 3)
    for item in packet.intermediates_der:
        v.require(type(item) is bytes and 0 < len(item) <= 16384)
    v.require(len(set(packet.intermediates_der)) == len(packet.intermediates_der))
    expected = dict(peer_certificate_sha256=sha256(packet.certificate_der).hexdigest(),
                    chain_verified="true", hostname_verified="true")
    v.require(_supplemental(packet) == expected)
    # Claims above are never sufficient: validate the injected certificate chain.
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    from cryptography.x509.verification import PolicyBuilder, Store

    def certificate(data):
        value = x509.load_der_x509_certificate(data)
        v.require(value.public_bytes(Encoding.DER) == data)
        return value

    ca = certificate(policy.trusted_ca_der)
    leaf = certificate(packet.certificate_der)
    intermediates = [certificate(data) for data in packet.intermediates_der]
    v.require(ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)
    verifier = (PolicyBuilder().store(Store([ca])).time(now).max_chain_depth(3)
                .build_server_verifier(x509.DNSName(campaign.host)))
    verifier.verify(leaf, intermediates)


@v.guarded
def review_evidence(campaign, policy, packets, *, now, revision):
    """Compare injected inventory/privileges and certificates, never acquire evidence."""
    v.validate_campaign(campaign)
    _policy(campaign, policy)
    v.utc(now)
    v.require(policy.volume_created_at <= now)
    v.require(type(packets) is tuple and len(packets) == 9)
    for packet in packets:
        v.require(type(packet) is EvidencePacket and type(packet.observation) is Observation)
        v.require(type(packet.intermediates_der) is tuple)
    v.review_observations(campaign, tuple(p.observation for p in packets), now=now, revision=revision)
    for packet in packets:
        if packet.observation.kind == "docker":
            _docker_adapter(campaign, policy, packet)
        elif packet.observation.kind == "postgres":
            _postgres_adapter(campaign, packet)
        else:
            _tls_adapter(campaign, policy, packet, now)
    return Review("injected_evidence_with_offline_certificate_checks")


@v.guarded
def evidence_fingerprint(campaign, policy, packets, *, now, revision):
    """A signed-state content reference, not proof of real collection/freshness."""
    review_evidence(campaign, policy, packets, now=now, revision=revision)
    observations = []
    for packet in packets:
        value = asdict(packet.observation)
        for key in ("started_at", "observed_at"):
            value[key] = value[key].isoformat(timespec="microseconds")
        observations.append(dict(observation=value, supplemental=packet.supplemental,
                                 certificate_sha256=sha256(packet.certificate_der).hexdigest() if packet.certificate_der else None,
                                 intermediate_sha256=tuple(sha256(data).hexdigest() for data in packet.intermediates_der)))
    policy_values = dict(context_name=policy.context_name, endpoint_sha256=policy.endpoint_sha256,
                         image_id_sha256=policy.image_id_sha256,
                         volume_created_at=policy.volume_created_at.isoformat(timespec="microseconds"),
                         ca_sha256=sha256(policy.trusted_ca_der).hexdigest())
    payload = dict(format="b2b-injected-evidence-v1", destination_sha256=v.destination_fingerprint(campaign),
                   revision=revision, policy=policy_values,
                   observations=sorted(observations, key=lambda p: (p["observation"]["kind"], p["observation"]["connection_id"])))
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")).hexdigest()


def collect_real_evidence(*args, **kwargs):
    """No acquisition or evidence source is ever called by this foundation."""
    deny(ExecutionDisabled)
