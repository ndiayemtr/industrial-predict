"""Explicit REAL-1 lease. Signatures authorize; they do not invent infrastructure facts."""

from dataclasses import asdict
from datetime import datetime, timedelta
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import stat
import sys

from b2b_postgres_qualification import authority, evidence, validation as v
from b2b_postgres_qualification.contracts import Offline, Observation
from p101_postgres_qualification import plans
from p101_postgres_qualification.execution_authority import signing_bytes, verify_signature


CHECKS = ('new_resources', 'routes_non_overlapping', 'registry_power_loss_and_acl',
    'artifact_runtime_verified', 'tls_bootstrap_independent', 'p101_writer_grants_approved', 'human_consent')
# The current Docker CLI collector returns `unverified_external`. A signed
# readiness envelope authenticates its signer, not the host that made the
# observations. Until a separately authenticated collector exists, no receipt
# can authorize opening a real PostgreSQL connection.
AUTHENTICATED_DOCKER_COLLECTOR_AVAILABLE = False
POSTGRES_IMAGE_ID = '7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317'
PACKAGES = dict(SQLAlchemy='2.0.52', alembic='1.19.1', cryptography='50.0.2',
    pandas='3.0.6', numpy='2.5.3', psycopg='3.3.4', **{'psycopg-binary': '3.3.4'})


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('ascii')


def safe_path(path):
    path = Path(path)
    v.require(path.is_absolute() and path.resolve(strict=True) == path)
    v.require(all(not p.is_symlink() and not p.is_junction() for p in (path, *path.parents)))
    return path


def capture(path, maximum=1048576):
    path = safe_path(path)
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        metadata = os.fstat(stream.fileno())
        v.require(stat.S_ISREG(metadata.st_mode) and metadata.st_size <= maximum)
        raw = stream.read(maximum + 1)
    v.require(len(raw) <= maximum)
    return raw


def parse_json(raw):
    from b2b_postgres_qualification.collectors import _json_object
    return json.loads(raw.decode('utf8'), object_pairs_hook=_json_object)


def read_json(path):
    return parse_json(capture(path))


@v.guarded
def verify_artifacts(path, expected_sha256, program_sha256, campaign):
    """No installs/builds/downloads. An independently supplied, reviewed artifact lock."""
    path = safe_path(path)
    v.digest(expected_sha256)
    raw = capture(path)
    v.require(sha256(raw).hexdigest() == expected_sha256)
    lock = parse_json(raw)  # Parse the EXACT bytes hashed, never reopen the manifest.
    v.require(type(lock) is dict and set(lock) == {'format', 'platform', 'python', 'base_image',
        'postgres_image_id', 'postgres_repo_digest', 'program_sha256', 'packages', 'files'})
    v.require(lock['format'] == 'p101-real1-artifacts-v1' and lock['platform'] == 'linux/amd64'
        and lock['python'] == '3.12.10' and sys.version_info[:3] == (3, 12, 10)
        and re.fullmatch(r'docker\.io/[a-z0-9/_-]+@sha256:[0-9a-f]{64}', lock['base_image']) is not None
        and lock['postgres_image_id'] == POSTGRES_IMAGE_ID
        and lock['postgres_repo_digest'] == campaign.image_sha256 and lock['program_sha256'] == program_sha256)
    packages, files = lock['packages'], lock['files']
    v.require(type(packages) is dict and all(packages.get(name) == expected for name, expected in PACKAGES.items()))
    v.require(all(type(name) is str and type(value) is str and version(name) == value for name, value in packages.items()))
    v.require(type(files) is list and 2 <= len(files) <= 256)
    names = []
    for item in files:
        v.require(type(item) is dict and set(item) == {'path', 'sha256'})
        name = item['path']
        v.require(type(name) is str and re.fullmatch(r'[a-zA-Z0-9_.+-]+', name) is not None
            and (name.endswith('.whl') or name in ('requirements.lock', 'trusted-keys.json')) and name not in names)
        names.append(name)
        v.digest(item['sha256'])
        artifact = safe_path(path.parent / name)
        v.require(artifact.is_file() and artifact.stat().st_size <= 268435456)
        v.require(sha256(artifact.read_bytes()).hexdigest() == item['sha256'])
    v.require({'requirements.lock', 'trusted-keys.json'}.issubset(names)
        and any(name.endswith('.whl') for name in names))
    # This validates exact approved artifacts, not the claim that a build was reproduced.
    # Closure/build/runtime verification is separately signed by the external reviewer.
    return expected_sha256


def readiness_bytes(receipt):
    v.require(type(receipt) is dict)
    return canonical(dict(format='p101-real1-readiness-v1', receipt=receipt))


def verify_registry(root, campaign, registry):
    root = safe_path(root)
    v.require(str(root) == registry['mount_target'] + '/p101q-exec-' + campaign.campaign_id.replace('-', ''))
    v.require(os.name == 'posix' and sys.platform == 'linux' and os.geteuid() != 0)
    metadata = root.stat()
    v.require(metadata.st_uid == os.geteuid() and stat.S_IMODE(metadata.st_mode) == 0o700)
    for parent in root.parents:
        mode = parent.stat().st_mode
        v.require(not (mode & (stat.S_IWGRP | stat.S_IWOTH)) or bool(mode & stat.S_ISVTX))
    return root


def prepare_readiness(executor, intent, *, collection, artifact_sha256, registry_root, registry_target=None):
    """Host-side, AFTER explicit operator collection. No collection or signing here."""
    from b2b_postgres_qualification.collectors import DockerCollection
    v.require(type(collection) is DockerCollection)
    packet = asdict(collection.packet)
    for name in ('started_at', 'observed_at'):
        packet['observation'][name] = packet['observation'][name].isoformat()
    target = str(safe_path(registry_root)) if registry_target is None else registry_target
    if registry_target is not None:
        v.require(target == executor.resources['registry']['mount_target'] + '/p101q-exec-' + executor.campaign.campaign_id.replace('-', ''))
    return dict(authority_id=intent.authority_id, key_id=intent.key_id,
        intent_sha256=sha256(signing_bytes(intent)).hexdigest(), inventory=executor.resources,
        docker=packet, artifact_sha256=artifact_sha256,
        limits=dict(postgres=asdict(collection.postgres_limits), runner=asdict(collection.runner_limits),
            runner_image_id=collection.runner_image_id_sha256),
        registry_sha256=sha256(target.encode('utf8')).hexdigest(),
        approved_at=executor.clock().isoformat(),
        expires_at=min(executor.clock()+timedelta(seconds=120), intent.expires_at).isoformat(), checks=list(CHECKS))


class LiveGuard(Offline):
    """Revalidate two externally signed envelopes and immutable prerequisites per use.

    TrustedKey entries/executor configuration come from the administrator, never
    from the submitted receipt. No favorable bool or inherited interface suffices.
    """
    @v.guarded
    def __init__(self, executor, intent, signature, *, receipt, receipt_signature, artifact_lock):
        from p101_postgres_qualification.execution import CampaignExecutor
        v.require(type(executor) is CampaignExecutor)
        self.executor, self.intent, self.signature = executor, intent, signature
        # Frozen bytes, not a mutable reference to caller-provided inventory/receipt.
        self._receipt = canonical(receipt)
        self._receipt_signature, self.artifact_lock = receipt_signature, Path(artifact_lock)
        self.check()

    @v.guarded
    def check(self):
        from p101_postgres_qualification.execution import _program_digest
        ex, intent = self.executor, self.intent
        expected = ex.expected_bindings(intent.operation)
        verify_signature(intent, self.signature, trusted_keys=ex.keys, now=ex.clock(), expected=expected)
        receipt = json.loads(self._receipt)
        v.require(set(receipt) == {'authority_id', 'key_id', 'intent_sha256', 'inventory', 'docker', 'limits',
            'artifact_sha256', 'registry_sha256', 'approved_at', 'expires_at', 'checks'})
        v.require(receipt['authority_id'] == intent.authority_id and receipt['key_id'] == intent.key_id
            and receipt['intent_sha256'] == sha256(signing_bytes(intent)).hexdigest()
            and plans.exact_equal(receipt['inventory'], ex.resources) and receipt['checks'] == list(CHECKS))
        registry = ex.resources.get('registry')
        v.require(type(registry) is dict)
        expected_limits = dict(postgres=dict(memory_bytes=ex.resources['postgres_memory'],
            nano_cpus=ex.resources['nano_cpus'], shm_bytes=67108864),
            runner=dict(memory_bytes=ex.resources['runner_memory'], nano_cpus=ex.resources['nano_cpus'], shm_bytes=67108864),
            runner_image_id=ex.resources['runner_image_id'])
        v.require(plans.exact_equal(receipt['limits'], expected_limits))
        authority._validate_keys(ex.keys)
        now = ex.clock()
        start, end = (datetime.fromisoformat(receipt[name]) for name in ('approved_at', 'expires_at'))
        v.utc(start)
        v.utc(end)
        v.require(start <= now < end <= intent.expires_at and timedelta(0) < end-start <= timedelta(seconds=120))
        keys = [key for key in ex.keys if key.authority_id == intent.authority_id and key.key_id == intent.key_id]
        v.require(len(keys) == 1 and not keys[0].revoked and keys[0].valid_from <= start
            and end <= keys[0].valid_until)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        v.require(type(self._receipt_signature) is bytes and len(self._receipt_signature) == 64)
        Ed25519PublicKey.from_public_bytes(keys[0].public_key).verify(self._receipt_signature, readiness_bytes(receipt))
        packet = receipt['docker']
        v.require(type(packet) is dict and set(packet) == {'observation', 'supplemental', 'certificate_der', 'intermediates_der'}
            and packet['certificate_der'] is None and packet['intermediates_der'] == [])
        obs = dict(packet['observation'])
        obs['started_at'], obs['observed_at'] = (datetime.fromisoformat(obs[name]) for name in ('started_at', 'observed_at'))
        obs['facts'] = tuple(tuple(pair) for pair in obs['facts'])
        observation = Observation(**obs)
        v.utc(observation.started_at)
        v.utc(observation.observed_at)
        from p101_postgres_qualification.resources import facts
        v.require(observation.kind == 'docker' and observation.source_id == 'p101-docker-cli'
            and observation.provenance == 'authenticated_collector' and observation.campaign_id == ex.campaign.campaign_id
            and observation.destination_sha256 == v.destination_fingerprint(ex.campaign)
            and timedelta(0) <= observation.observed_at-observation.started_at <= timedelta(seconds=10)
            and timedelta(0) <= now-observation.observed_at <= timedelta(seconds=120)
            and dict(observation.facts) == facts(ex.campaign, registry))
        evidence._docker_adapter(ex.campaign, ex.policy, evidence.EvidencePacket(observation,
            tuple(tuple(pair) for pair in packet['supplemental'])))
        # The current collector cannot meet this condition. Keep this gate after
        # binding validation so malformed/foreign declarations are rejected for
        # their own mismatch, while no signed declaration can open the real path.
        v.require(AUTHENTICATED_DOCKER_COLLECTOR_AVAILABLE)
        root = safe_path(ex.reservations._root)
        v.require(receipt['registry_sha256'] == sha256(str(root).encode('utf8')).hexdigest())
        # REAL entry is Linux-only; no assertion that Windows file fsync is sufficient.
        verify_registry(root, ex.campaign, registry)
        v.require(ex.policy.image_id_sha256 == POSTGRES_IMAGE_ID)
        verify_artifacts(self.artifact_lock, receipt['artifact_sha256'], _program_digest(), ex.campaign)
        return expected
