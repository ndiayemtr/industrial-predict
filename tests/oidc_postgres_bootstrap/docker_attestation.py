"""Injected Docker declarations only. No transport, executor or authenticated proof."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from ipaddress import IPv4Address, IPv4Network
import re
from uuid import UUID

from oidc_postgres_bootstrap.controller import (
    ArtifactDigest, Clock, ClockSample, ControllerContract, CLOCK_TOLERANCE,
    MAX_PROOF_AGE, controller_contract,
)


class AttestationRejected(ValueError):
    def __init__(self):
        super().__init__("OIDC injected Docker observation rejected")


def _reject():
    try:
        raise AttestationRejected() from None
    except AttestationRejected as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _guarded(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            pass
        _reject()
    return checked


class _Unverified:
    __slots__ = ()

    def __repr__(self):
        return f"<{type(self).__name__}: injected-unverified>"

    def __bool__(self):
        _reject()

    @property
    def authenticated(self):
        return False

    @property
    def execution_authorized(self):
        return False


class DeclaredProvenance(Enum):
    SIMULATED = "simulated"
    UNVERIFIED_DECLARATION = "unverified_declaration"


@dataclass(frozen=True, slots=True, repr=False)
class EngineIdentity(_Unverified):
    engine_id: str
    server_version: str
    os_type: str
    architecture: str


@dataclass(frozen=True, slots=True, repr=False)
class DockerContext(_Unverified):
    name: str
    endpoint_sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class ContainerIdentity(_Unverified):
    container_id: str
    name: str


@dataclass(frozen=True, slots=True, repr=False)
class NetworkIdentity(_Unverified):
    network_id: str
    name: str
    driver: str
    internal: bool
    subnet: str
    gateway: str
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class ImageIdentity(_Unverified):
    image_id: str
    repository_digest: str
    platform: str


@dataclass(frozen=True, slots=True, repr=False)
class Mount(_Unverified):
    kind: str
    source: str
    target: str
    size_bytes: int
    read_only: bool
    options: tuple[str, ...]


@dataclass(frozen=True, slots=True, repr=False)
class PortBinding(_Unverified):
    host: str
    host_port: int
    container_port: int
    protocol: str


@dataclass(frozen=True, slots=True, repr=False)
class ResourceLimits(_Unverified):
    memory_bytes: int
    nano_cpus: int


@dataclass(frozen=True, slots=True, repr=False)
class RestartPolicy(_Unverified):
    name: str
    maximum_retry_count: int


@dataclass(frozen=True, slots=True, repr=False)
class ContainerState(_Unverified):
    status: str
    running: bool
    paused: bool
    restarting: bool
    dead: bool
    ever_started: bool
    exit_code: int
    restart_count: int


@dataclass(frozen=True, slots=True, repr=False)
class DockerSnapshot(_Unverified):
    campaign_id: str
    engine: EngineIdentity
    context: DockerContext
    container: ContainerIdentity
    network: NetworkIdentity
    image: ImageIdentity
    entrypoint: tuple[str, ...]
    command: tuple[str, ...]
    mounts: tuple[Mount, ...]
    volumes: tuple[str, ...]
    container_networks: tuple[str, ...]
    published_ports: tuple[PortBinding, ...]
    limits: ResourceLimits
    restart_policy: RestartPolicy
    state: ContainerState
    privileged: bool


@dataclass(frozen=True, slots=True, repr=False)
class CollectionInterval(_Unverified):
    started_at: datetime
    ended_at: datetime
    started_ns: int
    ended_ns: int


@dataclass(frozen=True, slots=True, repr=False)
class DockerExpectation(_Unverified):
    binding: ControllerContract
    snapshot: DockerSnapshot


@dataclass(frozen=True, slots=True, repr=False)
class DockerObservation(_Unverified):
    snapshot: DockerSnapshot
    provenance: DeclaredProvenance
    controller_session_id: str
    collector_session_id: str
    git_revision: str
    artifacts: tuple[ArtifactDigest, ...]
    interval: CollectionInterval


@dataclass(frozen=True, slots=True, repr=False)
class DockerAttestation(_Unverified):
    observation: DockerObservation

    @property
    def classification(self):
        return "injected_docker_concordance_only"


class ObservationSource(ABC):
    @abstractmethod
    def collect(self) -> DockerObservation:
        """Declaration boundary only. No real implementation is supplied."""


def _require(condition):
    if not condition:
        raise AttestationRejected()


def _shape(value, cls):
    _require(type(value) is cls)
    for field in fields(cls):
        member = getattr(value, field.name)
        expected = field.type
        if expected in (str, int, bool, datetime, DeclaredProvenance):
            _require(type(member) is expected)
        elif expected in _NESTED:
            _shape(member, expected)
        else:
            _require(type(member) is tuple)


_NESTED = (EngineIdentity, DockerContext, ContainerIdentity, NetworkIdentity,
           ImageIdentity, Mount, PortBinding, ResourceLimits, RestartPolicy,
           ContainerState, DockerSnapshot, CollectionInterval, DockerObservation)


def _hex(value, length=64):
    _require(type(value) is str and re.fullmatch(r"[a-f0-9]{" + str(length) + "}", value) is not None)
    _require(value != "0" * length)


def _uuid(value):
    _require(type(value) is str)
    parsed = UUID(value)
    _require(parsed.int != 0 and str(parsed) == value)


def _name(value):
    _require(type(value) is str and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value) is not None)


def _tokens(values, *, nonempty=False):
    _require(type(values) is tuple and (len(values) > 0 or not nonempty))
    _require(all(type(value) is str and re.fullmatch(r"[A-Za-z0-9_./:=+-]{1,256}", value) is not None
                 for value in values))


def _snapshot(value):
    _shape(value, DockerSnapshot)
    _uuid(value.campaign_id)
    _uuid(value.engine.engine_id)
    _require(re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}", value.engine.server_version) is not None)
    _require(value.engine.os_type == "linux" and value.engine.architecture in ("amd64", "arm64"))
    _name(value.context.name)
    _hex(value.context.endpoint_sha256)
    _hex(value.container.container_id)
    _name(value.container.name)
    network = value.network
    _hex(network.network_id)
    _name(network.name)
    _require(network.driver == "bridge" and network.internal is True)
    subnet = IPv4Network(network.subnet, strict=True)
    _require(str(subnet) == network.subnet and str(IPv4Address(network.gateway)) == network.gateway)
    _require(IPv4Address(network.gateway) in subnet)
    _require(type(network.members) is tuple and type(value.container_networks) is tuple)
    for values in (network.members, value.container_networks):
        for identifier in values:
            _hex(identifier)
        _require(values == tuple(sorted(set(values))))
    image = value.image
    _require(image.image_id.startswith("sha256:"))
    _hex(image.image_id.removeprefix("sha256:"))
    _require(image.repository_digest.startswith("docker.io/library/postgres@sha256:"))
    _hex(image.repository_digest.removeprefix("docker.io/library/postgres@sha256:"))
    _require(image.platform == value.engine.os_type + "/" + value.engine.architecture)
    _tokens(value.entrypoint, nonempty=True)
    _tokens(value.command)
    _require(len(value.mounts) == 1 and value.volumes == ())
    mount = value.mounts[0]
    _shape(mount, Mount)
    _require(type(mount.options) is tuple and all(type(option) is str for option in mount.options))
    _require(mount.kind == "tmpfs" and mount.source == "" and mount.read_only is False)
    _require(mount.target == "/var/lib/postgresql/data" and 64 * 1024**2 <= mount.size_bytes <= 1024**3)
    _require(mount.options == ("nodev", "noexec", "nosuid"))
    _require(len(value.published_ports) == 1)
    port = value.published_ports[0]
    _shape(port, PortBinding)
    _require(port.host in ("127.0.0.1", "::1") and 1024 <= port.host_port <= 65535)
    _require(port.container_port == 5432 and port.protocol == "tcp")
    _require(value.limits.memory_bytes == 768 * 1024**2 and value.limits.nano_cpus == 1_000_000_000)
    _require(value.restart_policy.name == "no" and value.restart_policy.maximum_retry_count == 0)
    state = value.state
    _require(state.status == "created" and not any((state.running, state.paused, state.restarting,
                                                   state.dead, state.ever_started)))
    _require(state.exit_code == state.restart_count == 0 and value.privileged is False)
    _require(network.members == () and value.container_networks == (network.network_id,))
    return value


def _binding(value):
    _require(type(value) is ControllerContract)
    return controller_contract(**{field.name: getattr(value, field.name) for field in fields(ControllerContract)})


def _expectation(value):
    _require(type(value) is DockerExpectation)
    binding = _binding(value.binding)
    snap = _snapshot(value.snapshot)
    campaign = binding.campaign
    _require(snap.campaign_id == campaign.campaign_id and snap.engine.engine_id == binding.engine_id)
    _require((snap.container.container_id, snap.container.name) == (campaign.container_id, campaign.container_name))
    _require((snap.network.network_id, snap.network.name, snap.network.subnet, snap.network.gateway) ==
             (campaign.network_id, campaign.network_name, campaign.subnet, campaign.gateway))
    _require((snap.image.image_id, snap.image.repository_digest, snap.image.platform) ==
             (campaign.image_id, campaign.image_ref, campaign.platform))
    _require((snap.mounts[0].kind, snap.mounts[0].target, snap.mounts[0].size_bytes) ==
             (campaign.storage_kind, campaign.storage_target, campaign.storage_bytes))
    port = snap.published_ports[0]
    _require((port.host, port.host_port, port.container_port) == (campaign.host, campaign.port, campaign.server_port))
    return value


def _utc(value):
    _require(type(value) is datetime and value.tzinfo is timezone.utc)


def _duration(utc, ns):
    _require(timedelta(0) <= utc <= MAX_PROOF_AGE and
             0 <= ns <= (MAX_PROOF_AGE // timedelta(microseconds=1)) * 1000)
    _require(abs((utc // timedelta(microseconds=1)) * 1000 - ns) <=
             (CLOCK_TOLERANCE // timedelta(microseconds=1)) * 1000)


def _observation(value):
    _shape(value, DockerObservation)
    _snapshot(value.snapshot)
    _uuid(value.controller_session_id)
    _uuid(value.collector_session_id)
    _hex(value.git_revision, 40)
    # Artifact identities are validated by rebuilding the public controller contract
    # at comparison time; individual entries are still checked at construction.
    for artifact in value.artifacts:
        _shape(artifact, ArtifactDigest)
        _name(artifact.name)
        _hex(artifact.sha256)
    _require(len(value.artifacts) > 0)
    interval = value.interval
    _utc(interval.started_at)
    _utc(interval.ended_at)
    _require(0 <= interval.started_ns <= interval.ended_ns)
    _duration(interval.ended_at - interval.started_at, interval.ended_ns - interval.started_ns)
    return value


@_guarded
def docker_snapshot(**values):
    return _snapshot(DockerSnapshot(**values))


@_guarded
def docker_expectation(**values):
    return _expectation(DockerExpectation(**values))


@_guarded
def docker_observation(**values):
    return _observation(DockerObservation(**values))


@_guarded
def build_attestation(expected, observation, now):
    _expectation(expected)
    _observation(observation)
    _require(type(now) is ClockSample and type(now.monotonic_ns) is int and now.monotonic_ns >= 0)
    _utc(now.utc)
    binding = expected.binding
    _require(observation.snapshot == expected.snapshot)
    _require(observation.controller_session_id == binding.session_id)
    _require(observation.collector_session_id == binding.collector_session_id)
    _require(observation.git_revision == binding.git_revision and observation.artifacts == binding.artifacts)
    _duration(now.utc - observation.interval.ended_at, now.monotonic_ns - observation.interval.ended_ns)
    return DockerAttestation(observation)


@_guarded
def collect_attestation(expected, source, clock):
    _expectation(expected)
    _require(isinstance(source, ObservationSource))
    _require(isinstance(clock, Clock))
    before = clock.sample()
    _require(type(before) is ClockSample and type(before.monotonic_ns) is int and before.monotonic_ns >= 0)
    _utc(before.utc)
    # Caller-supplied Python code is not a trusted collector or a sandbox.
    observation = _observation(source.collect())
    now = clock.sample()
    _require(type(now) is ClockSample and type(now.monotonic_ns) is int and now.monotonic_ns >= 0)
    _utc(now.utc)
    _duration(now.utc - before.utc, now.monotonic_ns - before.monotonic_ns)
    _require(observation.interval.started_at >= before.utc and observation.interval.started_ns >= before.monotonic_ns)
    return build_attestation(expected, observation, now)
