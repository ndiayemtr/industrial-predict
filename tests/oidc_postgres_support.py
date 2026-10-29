"""Pure declarations for future disposable OIDC PostgreSQL tests. No executor."""

from dataclasses import dataclass, fields
from functools import wraps
from hashlib import sha256
from ipaddress import IPv4Address, IPv4Network
import re
from uuid import UUID


SCOPE = "public.oidc_transactions"
FORBIDDEN_PORTS = frozenset({5433, 5434, 55432})


class CampaignRejected(ValueError):
    def __init__(self):
        super().__init__("OIDC test campaign data rejected")


class ExecutionDisabled(RuntimeError):
    def __init__(self):
        super().__init__("OIDC test operational authority is unavailable")


def _raise_public(error_type):
    try:
        raise error_type() from None
    except (CampaignRejected, ExecutionDisabled) as error:
        # Clear even an exception currently handled by the caller. A bare
        # re-raise preserves this clearing instead of reattaching that context.
        error.__context__ = None
        error.__cause__ = None
        error.__suppress_context__ = True
        raise


class _Inert:
    __slots__ = ()

    def __repr__(self):
        return f"<{type(self).__name__}: inert>"

    def __bool__(self):
        _raise_public(ExecutionDisabled)

    @property
    def execution_authorized(self):
        return False


def _sanitized(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            pass
        _raise_public(CampaignRejected)
    return checked


@dataclass(frozen=True, slots=True, repr=False)
class CampaignContract(_Inert):
    campaign_id: str
    container_id: str
    container_name: str
    image_ref: str
    image_id: str
    platform: str
    network_id: str
    network_name: str
    subnet: str
    gateway: str
    storage_kind: str
    storage_target: str
    storage_bytes: int
    host: str
    port: int
    database: str
    preparation_role: str
    application_role: str
    observation_role: str
    transport: str
    ca_sha256: str
    server_address: str
    server_port: int
    server_version_num: int
    cluster_name: str
    scope: str


@dataclass(frozen=True, slots=True, repr=False)
class DockerInventory(_Inert):
    campaign_id: str
    container_id: str
    container_name: str
    image_ref: str
    image_id: str
    platform: str
    network_id: str
    network_name: str
    subnet: str
    gateway: str
    network_internal: bool
    network_members: tuple[str, ...]
    container_networks: tuple[str, ...]
    # Full mount list: (kind, target, size bytes, writable). No bind/volume allowed.
    mounts: tuple[tuple[str, str, int, bool], ...]
    # Full publication list: (local host, published port, container port, protocol).
    published_ports: tuple[tuple[str, int, int, str], ...]
    state: str
    restart_policy: str
    privileged: bool


@dataclass(frozen=True, slots=True, repr=False)
class SqlObservation(_Inert):
    campaign_id: str
    role_kind: str
    database: str
    session_user: str
    current_user: str
    server_address: str
    server_port: int
    server_version_num: int
    cluster_name: str
    backend_pid: int
    tls_in_use: bool
    # These three facts must come from the future independent client collector.
    client_verification: str
    client_ca_sha256: str
    client_verified_host: str
    superuser: bool
    create_database: bool
    create_role: bool
    scope: str


@dataclass(frozen=True, slots=True, repr=False)
class ContractValidation(_Inert):
    campaign_id: str
    stage: str = "syntax_only"


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceConcordance(_Inert):
    campaign_id: str
    stage: str = "injected_evidence_only"


def _require(condition):
    if not condition:
        raise CampaignRejected()


def _text(value):
    _require(type(value) is str and 0 < len(value) <= 256)


def _hex(value):
    _text(value)
    _require(re.fullmatch(r"[0-9a-f]{64}", value) is not None and value != "0" * 64)


def _campaign(value):
    _text(value)
    parsed = UUID(value)
    _require(str(parsed) == value and parsed.int != 0)
    return parsed.hex


def _shape(value, cls):
    _require(type(value) is cls)
    for field in fields(cls):
        member = getattr(value, field.name)
        # No subclasses, mutable containers or implicit conversions.
        expected = field.type
        if expected in (str, int, bool):
            _require(type(member) is expected)
            if expected is str:
                _text(member)
        elif expected is DestinationIdentity:
            _shape(member, DestinationIdentity)
        else:
            _require(type(member) is tuple)


def _contract(contract):
    _shape(contract, CampaignContract)
    suffix = _campaign(contract.campaign_id)
    for value in (contract.container_id, contract.network_id, contract.ca_sha256):
        _hex(value)
    _require(contract.container_id != contract.network_id)
    _require(contract.container_name == f"oidc-tx-{suffix}-postgres")
    _require(contract.network_name == f"oidc-tx-{suffix}-net")
    _require(contract.database == f"oidct_{suffix}")
    for kind, tail in (("preparation", "owner"), ("application", "app"), ("observation", "observer")):
        _require(getattr(contract, f"{kind}_role") == f"oidct_{suffix}_{tail}")
    _require(contract.cluster_name == f"oidc-test-{suffix}")
    _require(contract.image_ref.startswith("docker.io/library/postgres@sha256:"))
    _hex(contract.image_ref.removeprefix("docker.io/library/postgres@sha256:"))
    _require(contract.image_id.startswith("sha256:"))
    _hex(contract.image_id.removeprefix("sha256:"))
    _require(contract.platform in ("linux/amd64", "linux/arm64"))
    _require(contract.host in ("127.0.0.1", "::1"))
    _require(1024 <= contract.port <= 65535 and contract.port not in FORBIDDEN_PORTS)
    _require(contract.server_port == 5432)
    _require(170000 <= contract.server_version_num < 180000)
    network = IPv4Network(contract.subnet, strict=True)
    # Restrict to explicit RFC1918 networks, rather than ipaddress.is_private.
    _require(any(network.subnet_of(IPv4Network(block)) for block in
                 ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))
    _require(24 <= network.prefixlen <= 28)
    gateway = IPv4Address(contract.gateway)
    server = IPv4Address(contract.server_address)
    _require(gateway in network and server in network)
    _require(gateway not in (network.network_address, network.broadcast_address))
    _require(server not in (network.network_address, network.broadcast_address, gateway))
    _require(contract.storage_kind == "tmpfs")
    _require(contract.storage_target == "/var/lib/postgresql/data")
    _require(64 * 1024**2 <= contract.storage_bytes <= 1024**3)
    _require(contract.transport == "verify-full")
    _require(contract.scope == SCOPE)
    return contract


@_sanitized
def campaign_contract(**values):
    """All fields mandatory; no environment, settings or connection defaults."""
    return _contract(CampaignContract(**values))


@_sanitized
def docker_inventory(**values):
    result = DockerInventory(**values)
    _shape(result, DockerInventory)
    for collection in (result.network_members, result.container_networks):
        _require(all(type(item) is str for item in collection))
    for mount in result.mounts:
        _require(type(mount) is tuple and len(mount) == 4)
        _require(tuple(type(item) for item in mount) == (str, str, int, bool))
    for publication in result.published_ports:
        _require(type(publication) is tuple and len(publication) == 4)
        _require(tuple(type(item) for item in publication) == (str, int, int, str))
    return result


@_sanitized
def sql_observation(**values):
    result = SqlObservation(**values)
    _shape(result, SqlObservation)
    _require(result.backend_pid > 0)
    return result


@_sanitized
def validate_contract(contract):
    return ContractValidation(_contract(contract).campaign_id)


@_sanitized
def compare_evidence(contract, inventory, observations):
    """Compare supplied facts; cannot authenticate their origin or authorize IO."""
    _contract(contract)
    _require(type(inventory) is DockerInventory)
    docker_inventory(**{field.name: getattr(inventory, field.name) for field in fields(inventory)})
    for name in ("campaign_id", "container_id", "container_name", "image_ref", "image_id",
                 "platform", "network_id", "network_name", "subnet", "gateway"):
        _require(getattr(inventory, name) == getattr(contract, name))
    _require(inventory.network_internal is True)
    _require(inventory.network_members == (contract.container_id,))
    _require(inventory.container_networks == (contract.network_id,))
    _require(inventory.mounts == (("tmpfs", contract.storage_target, contract.storage_bytes, True),))
    _require(inventory.published_ports == ((contract.host, contract.port, contract.server_port, "tcp"),))
    _require(inventory.state == "running" and inventory.restart_policy == "no")
    _require(inventory.privileged is False)
    _require(type(observations) is tuple and len(observations) == 3)
    roles = {"preparation": contract.preparation_role, "application": contract.application_role,
             "observation": contract.observation_role}
    seen = set()
    pids = set()
    for observation in observations:
        _shape(observation, SqlObservation)
        _require(observation.role_kind in roles and observation.role_kind not in seen)
        seen.add(observation.role_kind)
        _require(observation.backend_pid > 0 and observation.backend_pid not in pids)
        pids.add(observation.backend_pid)
        for name in ("campaign_id", "database", "server_address", "server_port",
                     "server_version_num", "cluster_name", "scope"):
            _require(getattr(observation, name) == getattr(contract, name))
        _require(observation.session_user == roles[observation.role_kind])
        _require(observation.current_user == roles[observation.role_kind])
        _require(observation.tls_in_use is True)
        _require(observation.client_verification == contract.transport)
        _require(observation.client_ca_sha256 == contract.ca_sha256)
        _require(observation.client_verified_host == contract.host)
        _require(not (observation.superuser or observation.create_database or observation.create_role))
    return EvidenceConcordance(contract.campaign_id)


def require_operational_authority(_candidate):
    """Placeholder refusal, never an execution capability or a launcher."""
    _raise_public(ExecutionDisabled)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticOidcIds(_Inert):
    transaction_id: str
    state_digest: str
    browser_digest: str
    policy_digest: str


@_sanitized
def synthetic_oidc_ids(contract, case):
    _contract(contract)
    _text(case)
    _require(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", case) is not None)
    return SyntheticOidcIds(*(sha256(f"oidc-test:{contract.campaign_id}:{case}:{kind}".encode("ascii")).hexdigest()
                              for kind in ("transaction", "state", "browser", "policy")))


@dataclass(frozen=True, slots=True, repr=False)
class ResourceRef(_Inert):
    campaign_id: str
    kind: str
    identity: str


@dataclass(frozen=True, slots=True, repr=False)
class RowRef(_Inert):
    campaign_id: str
    table: str
    transaction_id: str


@dataclass(frozen=True, slots=True, repr=False)
class DestinationIdentity(_Inert):
    container_id: str
    database: str
    scope: str


def _destination(contract):
    return DestinationIdentity(contract.container_id, contract.database, contract.scope)


@dataclass(frozen=True, slots=True, repr=False)
class CreatedRegistry(_Inert):
    campaign_id: str
    destination: DestinationIdentity
    resources: tuple[ResourceRef, ...]
    rows: tuple[RowRef, ...]


@dataclass(frozen=True, slots=True, repr=False)
class CleanupDescription(_Inert):
    campaign_id: str
    destination: DestinationIdentity
    resources: tuple[ResourceRef, ...]
    rows: tuple[RowRef, ...]


@_sanitized
def campaign_resources(contract):
    """Expected ownership inventory, not evidence of creation or authority."""
    _contract(contract)
    return tuple(ResourceRef(contract.campaign_id, kind, identity) for kind, identity in (
        ("container", contract.container_id), ("network", contract.network_id),
        ("tmpfs", f"{contract.container_id}:{contract.storage_target}"),
        ("table", SCOPE)))


def _entries(contract, resources, rows):
    _require(type(resources) is tuple and type(rows) is tuple)
    expected = campaign_resources(contract)
    for resource in resources:
        _shape(resource, ResourceRef)
        _require(resource in expected)
    for row in rows:
        _shape(row, RowRef)
        _require(row.campaign_id == contract.campaign_id and row.table == SCOPE)
        _hex(row.transaction_id)
    _require(len(set(resources)) == len(resources) and len(set(rows)) == len(rows))


@_sanitized
def created_registry(contract, resources, rows):
    """Record explicitly reported creation; performs no creation or discovery."""
    _contract(contract)
    _entries(contract, resources, rows)
    return CreatedRegistry(contract.campaign_id, _destination(contract), resources, rows)


@_sanitized
def describe_cleanup(contract, registry, resources, rows):
    _contract(contract)
    _shape(registry, CreatedRegistry)
    _require(registry.campaign_id == contract.campaign_id)
    _require(registry.destination == _destination(contract))
    _entries(contract, registry.resources, registry.rows)
    _entries(contract, resources, rows)
    _require(all(resource in registry.resources for resource in resources))
    _require(all(row in registry.rows for row in rows))
    return CleanupDescription(contract.campaign_id, registry.destination, resources, rows)


@dataclass(frozen=True, slots=True, repr=False)
class ActorDescription(_Inert):
    campaign_id: str
    actor_id: str
    role_kind: str
    sql_role: str
    connection_id: str


@_sanitized
def describe_actors(contract, specifications):
    """Distinct future connections; no encompassing transaction or savepoint."""
    _contract(contract)
    _require(type(specifications) is tuple and len(specifications) >= 2)
    result = []
    for specification in specifications:
        _require(type(specification) is tuple and len(specification) == 3)
        actor, kind, connection = specification
        for label in (actor, kind, connection):
            _text(label)
            _require(re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", label) is not None)
        _require(kind in ("preparation", "application", "observation"))
        result.append(ActorDescription(contract.campaign_id, actor, kind,
                                       getattr(contract, f"{kind}_role"), connection))
    _require(len({actor.actor_id for actor in result}) == len(result))
    _require(len({actor.connection_id for actor in result}) == len(result))
    return tuple(result)


@dataclass(frozen=True, slots=True, repr=False)
class ConcurrencyEvent(_Inert):
    campaign_id: str
    actor_id: str
    backend_pid: int
    sequence: int
    event: str


@_sanitized
def concurrency_event(actor, backend_pid, sequence, event):
    _shape(actor, ActorDescription)
    _campaign(actor.campaign_id)
    _require(type(backend_pid) is int and backend_pid > 0)
    _require(type(sequence) is int and sequence >= 0)
    _require(type(event) is str and event in (
        "lock_requested", "lock_acquired", "clock_sampled", "delete_returned",
        "commit_acknowledged", "session_closed"))
    return ConcurrencyEvent(actor.campaign_id, actor.actor_id, backend_pid, sequence, event)


@dataclass(frozen=True, slots=True, repr=False)
class LockWaitCondition(_Inert):
    campaign_id: str
    blocker_actor: str
    waiter_actor: str
    blocker_pid: int
    waiter_pid: int
    wait_event_type: str


@_sanitized
def lock_wait_condition(blocker, waiter, blocking_pids, wait_event_type):
    """Checks an injected wait observation; does not wait, query or sample time."""
    for event in (blocker, waiter):
        _shape(event, ConcurrencyEvent)
        _campaign(event.campaign_id)
        _require(event.backend_pid > 0 and event.sequence >= 0)
    _require(blocker.campaign_id == waiter.campaign_id)
    _require(blocker.actor_id != waiter.actor_id and blocker.backend_pid != waiter.backend_pid)
    _require(blocker.event == "lock_acquired" and waiter.event == "lock_requested")
    _require(type(blocking_pids) is tuple and blocking_pids == (blocker.backend_pid,))
    _require(type(blocking_pids[0]) is int)
    _require(type(wait_event_type) is str and wait_event_type == "Lock")
    return LockWaitCondition(blocker.campaign_id, blocker.actor_id, waiter.actor_id,
                             blocker.backend_pid, waiter.backend_pid, wait_event_type)
