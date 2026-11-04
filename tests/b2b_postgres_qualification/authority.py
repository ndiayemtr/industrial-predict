"""Offline Ed25519 verification. No key discovery, signing or execution authority."""

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import json
from threading import Lock

from b2b_postgres_qualification.contracts import Offline
from b2b_postgres_qualification import validation as v


@dataclass(frozen=True, slots=True, repr=False)
class TrustedKey(Offline):
    """Server-supplied trust configuration, never a field of a submitted campaign."""

    authority_id: str
    key_id: str
    public_key: bytes
    valid_from: datetime
    valid_until: datetime
    revoked: bool


@dataclass(frozen=True, slots=True, repr=False)
class SignedApproval(Offline):
    approval_id: str
    key_id: str
    initial_state_sha256: str
    signature: bytes


@dataclass(frozen=True, slots=True, repr=False)
class SignatureReview(Offline):
    """Offline signature result only; manual construction is not a proof."""

    approval_id: str
    authority_id: str
    key_id: str
    envelope_sha256: str

    @property
    def signature_verified(self):
        return True


@v.guarded
def signing_bytes(campaign, plan, approval, *, approval_id, key_id, initial_state_sha256, now):
    """Versioned bytes to be signed externally; no signing/private key API exists."""
    v.identifier(approval_id)
    v.text(key_id)
    v.digest(initial_state_sha256)
    base = json.loads(v.approval_canonical(campaign, plan, approval, now=now))
    payload = {
        "format": "b2b-qualification-ed25519-intent-v1", "algorithm": "Ed25519",
        "approval_id": approval_id, "key_id": key_id, "approval": base,
        "initial_revision": plan.initial_revision, "final_revision": plan.final_revision,
        "initial_state_sha256": initial_state_sha256,
        "publications": [
            {"revision": p.revision, "parent": p.parent, "path": p.path, "sha256": p.sha256}
            for p in plan.publications
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


class MemoryReplayRegistry(Offline):
    """Atomic consumption within this object/process ONLY. No persistence or reset."""

    __slots__ = ("_seen", "_lock")

    def __init__(self):
        self._seen = set()
        self._lock = Lock()

    @v.guarded
    def consume(self, *, authority_id, approval_id):
        v.text(authority_id)
        v.identifier(approval_id)
        key = (authority_id, approval_id)
        with self._lock:
            v.require(key not in self._seen)
            self._seen.add(key)


def _validate_keys(keys):
    v.require(type(keys) is tuple and 1 <= len(keys) <= 32)
    for key in keys:
        v.require(type(key) is TrustedKey)
        v.text(key.authority_id)
        v.text(key.key_id)
        v.require(type(key.public_key) is bytes and len(key.public_key) == 32 and key.public_key != bytes(32))
        v.utc(key.valid_from)
        v.utc(key.valid_until)
        v.require(key.valid_from < key.valid_until and type(key.revoked) is bool)
    v.require(len({(k.authority_id, k.key_id) for k in keys}) == len(keys))
    v.require(len({k.public_key for k in keys}) == len(keys))


class ApprovalVerifier(Offline):
    """Trust keys and replay state are injected out-of-band, not read from the dossier.

    Configuration origin cannot be proved by Python object construction. No
    simulated callback/provider can replace the fixed Ed25519 verification path.
    """

    __slots__ = ("_keys", "_replay")

    @v.guarded
    def __init__(self, *, trusted_keys, replay_registry):
        _validate_keys(trusted_keys)
        v.require(type(replay_registry) is MemoryReplayRegistry)
        self._keys = trusted_keys
        self._replay = replay_registry

    @v.guarded
    def verify(self, campaign, plan, approval, signed, *, expected_initial_state_sha256, now):
        # Revalidate even raw/frozen objects; no ambient config or trust discovery.
        _validate_keys(self._keys)
        v.require(type(self._replay) is MemoryReplayRegistry)
        v.require(type(signed) is SignedApproval)
        v.digest(expected_initial_state_sha256)
        v.digest(signed.initial_state_sha256)
        v.require(signed.initial_state_sha256 == expected_initial_state_sha256)
        v.require(type(signed.signature) is bytes and len(signed.signature) == 64)
        payload = signing_bytes(campaign, plan, approval, approval_id=signed.approval_id,
                                key_id=signed.key_id, initial_state_sha256=signed.initial_state_sha256, now=now)
        candidates = [k for k in self._keys if k.authority_id == approval.authority_id and k.key_id == signed.key_id]
        v.require(len(candidates) == 1)
        key = candidates[0]
        v.require(not key.revoked and key.valid_from <= approval.issued_at <= now < key.valid_until)
        v.require(approval.expires_at <= key.valid_until)
        # Recognized implementation only; absence/unavailability fails closed.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

        Ed25519PublicKey.from_public_bytes(key.public_key).verify(signed.signature, payload)
        self._replay.consume(authority_id=key.authority_id, approval_id=signed.approval_id)
        return SignatureReview(signed.approval_id, key.authority_id, key.key_id, sha256(payload).hexdigest())
