"""Separate EXEC-1 signed intentions and fail-closed local replay reservations.

Existing B2B signing formats/registries and unconditional refusals are unchanged.
Offline verification does not establish human consent or authorize a live adapter.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path

from b2b_postgres_qualification import authority as existing, validation as v
from b2b_postgres_qualification.contracts import Offline
from b2b_postgres_qualification.durable import _exclusive, _present, _approval_lock


@dataclass(frozen=True, slots=True, repr=False)
class Intent(Offline):
    authority_id: str
    key_id: str
    approval_id: str
    operation: str
    campaign_sha256: str
    resources_sha256: str
    content_sha256: str
    initial_state_sha256: str
    catalogue_sha256: str
    issued_at: datetime
    expires_at: datetime


@v.guarded
def signing_bytes(intent):
    v.require(type(intent) is Intent and intent.operation in ('migrate', 'first-pair'))
    v.text(intent.authority_id)
    v.text(intent.key_id)
    v.identifier(intent.approval_id)
    for value in (intent.campaign_sha256, intent.resources_sha256, intent.content_sha256,
                  intent.initial_state_sha256, intent.catalogue_sha256):
        v.digest(value)
    v.utc(intent.issued_at)
    v.utc(intent.expires_at)
    v.require(timedelta(0) < intent.expires_at - intent.issued_at <= timedelta(minutes=15))
    values = asdict(intent)
    values['issued_at'], values['expires_at'] = intent.issued_at.isoformat(), intent.expires_at.isoformat()
    return json.dumps(dict(format='p101-exec1-ed25519-intent-v1', algorithm='Ed25519', intent=values),
        sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


@v.guarded
def verify_signature(intent, signature, *, trusted_keys, now, expected):
    existing._validate_keys(trusted_keys)  # Reuse fixed trusted key semantics.
    v.utc(now)
    payload = signing_bytes(intent)
    v.require(type(signature) is bytes and len(signature) == 64)
    v.require(intent.issued_at <= now < intent.expires_at)
    v.require(type(expected) is dict and set(expected) == {'operation', 'campaign_sha256',
        'resources_sha256', 'content_sha256', 'initial_state_sha256', 'catalogue_sha256'})
    v.require(all(type(value) is str and getattr(intent, key) == value for key, value in expected.items()))
    keys = [key for key in trusted_keys if key.authority_id == intent.authority_id and key.key_id == intent.key_id]
    v.require(len(keys) == 1)
    key = keys[0]
    v.require(not key.revoked and key.valid_from <= intent.issued_at <= now < key.valid_until
        and intent.expires_at <= key.valid_until)
    v.require(version('cryptography') == '50.0.2')
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    Ed25519PublicKey.from_public_bytes(key.public_key).verify(signature, payload)
    return sha256(payload).hexdigest()  # Metadata, never an execution capability.


class ReplayReservations(Offline):
    """Explicit isolated LOCAL storage. Claims survive process/object restarts.

    No automatic initialization, cleanup, release, retry or reconciliation. Trusted
    storage/ACL/OS locks are external prerequisites; power-loss durability unqualified.
    """

    @v.guarded
    def __init__(self, directory):
        root = Path(directory)
        v.require(root.is_absolute() and root.name.startswith('p101q-exec-')
            and root.resolve(strict=True) == root and root.is_dir())
        v.require(all(not path.is_symlink() and not path.is_junction() for path in (root, *root.parents)))
        self._root = root

    def _claim(self, campaign_sha256, operation):
        v.digest(campaign_sha256)
        v.require(operation in ('migrate', 'first-pair'))
        return self._root / (sha256((campaign_sha256 + ':' + operation).encode()).hexdigest() + '.claim')

    @v.guarded
    def reserve(self, intent, *, envelope_sha256):
        v.require(type(intent) is Intent)
        v.digest(envelope_sha256)
        claim = self._claim(intent.campaign_sha256, intent.operation)
        with _approval_lock(claim):
            v.require(not _present(claim))
            # Exclusive + fsynced reservation BEFORE any SQL. Existence alone stops
            # another approval, including if this write fails or its ack is lost.
            _exclusive(claim, json.dumps(dict(envelope=envelope_sha256,
                approval_id=intent.approval_id), sort_keys=True).encode('ascii'))

    @v.guarded
    def finish(self, intent, *, envelope_sha256, status, evidence_sha256):
        claim = self._claim(intent.campaign_sha256, intent.operation)
        v.digest(envelope_sha256)
        v.digest(evidence_sha256)
        v.require(status in ('refused', 'simulated_commit_confirmed', 'uncertain',
            'simulated_rollback_confirmed', 'simulated_commit_verification_failed'))
        with _approval_lock(claim):
            v.require(claim.is_file() and not claim.is_symlink() and not claim.is_junction())
            record = json.loads(claim.read_text(encoding='ascii'))
            v.require(record == dict(envelope=envelope_sha256, approval_id=intent.approval_id))
            _exclusive(claim.with_suffix('.outcome'), json.dumps(dict(status=status,
                evidence_sha256=evidence_sha256), sort_keys=True).encode('ascii'))

    @v.guarded
    def inspect(self, campaign_sha256, operation):
        claim = self._claim(campaign_sha256, operation)
        with _approval_lock(claim):
            if not _present(claim):
                return 'absent'
            outcome = claim.with_suffix('.outcome')
            if not _present(outcome):
                return 'uncertain'
            v.require(outcome.is_file() and not outcome.is_symlink() and not outcome.is_junction())
            value = json.loads(outcome.read_text(encoding='ascii'))
            v.require(type(value) is dict and set(value) == {'status', 'evidence_sha256'})
            v.digest(value['evidence_sha256'])
            v.require(value['status'] in ('refused', 'simulated_commit_confirmed', 'uncertain',
                'simulated_rollback_confirmed', 'simulated_commit_verification_failed'))
            return value['status']
