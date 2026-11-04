"""Future read-only collection paths. Tests must replace every external transport."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from time import monotonic
from typing import Protocol
from uuid import uuid4

from b2b_postgres_qualification.contracts import Observation, Offline
from b2b_postgres_qualification.evidence import EvidencePacket, _policy, _tls_adapter
from b2b_postgres_qualification import validation as v


def _clock():
    return datetime.now(timezone.utc)


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        v.require(key not in result)
        result[key] = value
    return result


def _template(fields):
    return "{" + ",".join('"' + name + '":{{json ' + expression + '}}' for name, expression in fields) + "}"


CONTAINER_FORMAT = _template((
    ("id", ".Id"), ("name", ".Name"), ("image", ".Image"), ("image_ref", ".Config.Image"),
    ("networks", ".NetworkSettings.Networks"), ("mounts", ".Mounts"),
    ("ports", ".NetworkSettings.Ports"), ("status", ".State.Status"),
    ("privileged", ".HostConfig.Privileged"), ("restart", ".HostConfig.RestartPolicy.Name"),
    ("memory", ".HostConfig.Memory"), ("cpus", ".HostConfig.NanoCpus"),
    ("shm", ".HostConfig.ShmSize"), ("readonly_root", ".HostConfig.ReadonlyRootfs"),
))
NETWORK_FORMAT = _template((("id", ".Id"), ("name", ".Name"), ("driver", ".Driver"),
                            ("internal", ".Internal"), ("members", ".Containers"), ("ipam", ".IPAM.Config")))
VOLUME_FORMAT = _template((("name", ".Name"), ("driver", ".Driver"), ("scope", ".Scope"), ("created", ".CreatedAt")))
IMAGE_FORMAT = _template((("id", ".Id"), ("digests", ".RepoDigests"), ("os", ".Os"), ("arch", ".Architecture")))


@dataclass(frozen=True, slots=True, repr=False)
class ResourceLimits(Offline):
    memory_bytes: int
    nano_cpus: int
    shm_bytes: int


@dataclass(frozen=True, slots=True, repr=False)
class DockerCollection(Offline):
    packet: EvidencePacket
    postgres_limits: ResourceLimits
    runner_limits: ResourceLimits
    runner_image_id_sha256: str


class DockerCollector(Offline):
    """Fixed consultation-only CLI calls; no generic command/inspect-output API."""

    @v.guarded
    def __init__(self, campaign, policy, *, executable, postgres_limits, runner_limits, runner_image_id_sha256, clock=_clock):
        v.validate_campaign(campaign)
        _policy(campaign, policy)
        v.require(type(executable) is str and Path(executable).is_absolute())
        v.require(not executable.startswith(("\\\\", "//")) and callable(clock))
        v.digest(runner_image_id_sha256)
        for limits in (postgres_limits, runner_limits):
            v.require(type(limits) is ResourceLimits)
            v.require(all(type(n) is int and n > 0 for n in (limits.memory_bytes, limits.nano_cpus, limits.shm_bytes)))
        self._campaign, self._policy, self._exe, self._clock = campaign, policy, executable, clock
        self._limits = (postgres_limits, runner_limits)
        self._runner_image = runner_image_id_sha256

    def _query(self, deadline, *arguments):
        remaining = deadline - monotonic()
        v.require(remaining > 0)
        result = subprocess.run([self._exe, "--context", self._policy.context_name, *arguments],
                                shell=False, capture_output=True, timeout=min(3, remaining))
        v.require(result.returncode == 0 and type(result.stdout) is bytes and len(result.stdout) <= 1048576)
        return json.loads(result.stdout.decode("utf-8"), object_pairs_hook=_json_object)

    @v.guarded
    def collect(self):
        c, policy = self._campaign, self._policy
        v.validate_campaign(c)
        _policy(c, policy)
        start = self._clock()
        v.utc(start)
        deadline = monotonic() + 10
        endpoint = self._query(deadline, "context", "inspect", policy.context_name, "--format", "{{json .Endpoints.docker.Host}}")
        v.require(type(endpoint) is str and endpoint.startswith(("npipe://", "unix://")))
        v.require(sha256(endpoint.encode("utf-8")).hexdigest() == policy.endpoint_sha256)
        engine = self._query(deadline, "info", "--format", "{{json .ID}}")
        v.require(type(engine) is str and engine == c.engine_id)
        containers = []
        for cid, limits in zip((c.container_id, c.runner_id), self._limits):
            data = self._query(deadline, "inspect", "--type", "container", "--format", CONTAINER_FORMAT, cid)
            v.require(type(data) is dict and set(data) == {"id", "name", "image", "image_ref", "networks", "mounts", "ports", "status", "privileged", "restart", "memory", "cpus", "shm", "readonly_root"})
            v.require(type(data["id"]) is str and data["id"] == cid and cid not in v.FORBIDDEN_IDS)
            v.require(data["status"] == "running" and data["privileged"] is False and data["restart"] == "no")
            v.require(data["readonly_root"] is True)
            v.require(type(data["networks"]) is dict and set(data["networks"]) == {c.network_name})
            v.require(data["networks"][c.network_name]["NetworkID"] == c.network_id)
            v.require(data["ports"] is None or type(data["ports"]) is dict and all(p is None or p == [] for p in data["ports"].values()))
            v.require(all(type(data[k]) is int for k in ("memory", "cpus", "shm")))
            v.require((data["memory"], data["cpus"], data["shm"]) == (limits.memory_bytes, limits.nano_cpus, limits.shm_bytes))
            containers.append(data)
        pg, runner = containers
        v.require(pg["name"] == "/" + c.container_name and type(runner["name"]) is str and runner["name"] == "/" + c.container_name.removesuffix("-postgres") + "-runner")
        v.require(pg["image"] == "sha256:" + policy.image_id_sha256)
        v.require(runner["image"] == "sha256:" + self._runner_image)
        v.require(pg["image_ref"] == "docker.io/library/postgres@sha256:" + c.image_sha256)
        v.require(type(pg["mounts"]) is list and len(pg["mounts"]) == 1 and runner["mounts"] == [])
        mount = pg["mounts"][0]
        v.require(mount["Type"] == "volume" and mount["Name"] == c.volume_name and mount["Destination"] == "/var/lib/postgresql/data" and mount["RW"] is True)
        v.require(pg["networks"][c.network_name]["IPAddress"] == c.server_address)
        network = self._query(deadline, "network", "inspect", c.network_id, "--format", NETWORK_FORMAT)
        v.require(set(network) == {"id", "name", "driver", "internal", "members", "ipam"})
        v.require(network["id"] == c.network_id and network["name"] == c.network_name and network["driver"] == "bridge" and network["internal"] is True)
        v.require(type(network["members"]) is dict and set(network["members"]) == {c.container_id, c.runner_id})
        v.require(type(network["ipam"]) is list and len(network["ipam"]) == 1 and network["ipam"][0]["Subnet"] == c.subnet)
        volume = self._query(deadline, "volume", "inspect", c.volume_name, "--format", VOLUME_FORMAT)
        v.require(set(volume) == {"name", "driver", "scope", "created"})
        v.require(volume["name"] == c.volume_name and volume["driver"] == "local" and volume["scope"] == "local")
        created = datetime.fromisoformat(volume["created"].replace("Z", "+00:00"))
        v.utc(created)
        v.require(created == policy.volume_created_at)
        image = self._query(deadline, "image", "inspect", pg["image"], "--format", IMAGE_FORMAT)
        v.require(set(image) == {"id", "digests", "os", "arch"})
        v.require(image["id"] == pg["image"] and image["os"] == "linux" and image["arch"] == "amd64")
        v.require(type(image["digests"]) is list and pg["image_ref"] in image["digests"])
        runner_image = self._query(deadline, "image", "inspect", runner["image"], "--format", IMAGE_FORMAT)
        v.require(set(runner_image) == {"id", "digests", "os", "arch"})
        v.require(runner_image["id"] == runner["image"] and runner_image["os"] == "linux" and runner_image["arch"] == "amd64")
        end = self._clock()
        v.utc(end)
        v.require(monotonic() <= deadline and 0 <= (end - start).total_seconds() <= 10)
        facts = dict(engine_id=engine, container_id=pg["id"], container_name=pg["name"][1:],
                     network_id=network["id"], network_name=network["name"], volume_name=volume["name"],
                     image_sha256=c.image_sha256, platform=image["os"] + "/" + image["arch"], network_internal="true",
                     members=",".join(sorted(network["members"])), volume_target=mount["Destination"], extra_mounts="",
                     published_ports="", privileged="false", restart_policy=pg["restart"], state=pg["status"])
        observation = Observation("docker", c.campaign_id, v.destination_fingerprint(c), "unverified_external",
                                  "docker-cli", start, end, str(uuid4()), tuple(sorted(facts.items())))
        extra = dict(context_name=policy.context_name, endpoint_sha256=sha256(endpoint.encode()).hexdigest(),
                     image_id_sha256=image["id"].removeprefix("sha256:"), container_networks=network["id"],
                     volume_engine_id=engine, volume_driver=volume["driver"], volume_scope=volume["scope"],
                     volume_created_at=created.isoformat(timespec="microseconds"))
        return DockerCollection(EvidencePacket(observation, tuple(sorted(extra.items()))), *self._limits, runner_image["id"].removeprefix("sha256:"))


@dataclass(frozen=True, slots=True, repr=False)
class SqlCredentials(Offline):
    role: str
    password: str


@dataclass(frozen=True, slots=True, repr=False)
class TlsBinding(Offline):
    connection: object
    socket_id: int
    driver_verified: bool
    auth_method: str
    verified_host: str
    certificate_der: bytes
    intermediates_der: tuple[bytes, ...]


class BoundPostgresTransport(Protocol):
    def open_readonly(self, *, host, port, database, role, password, ca_der, timeout, options):
        """Future trusted driver: dict rows, startup READ ONLY, verify-full and SCRAM."""
        ...

    def tls_binding(self, connection) -> TlsBinding:
        """Must capture peer certificate from THIS SQL connection, not a second socket."""
        ...


IDENTITY_SQL = """SELECT current_database() AS database, session_user AS session_role,
 current_user AS role, inet_server_addr()::text AS address, inet_server_port() AS port,
 current_setting('server_version_num') AS version,
 current_setting('cluster_name') AS cluster,
 current_setting('app.development_instance_id',true) AS dev_marker,
 current_setting('app.b2b_qualification_instance_id',true) AS instance,
 current_setting('transaction_read_only') AS read_only,
 current_setting('default_transaction_read_only') AS default_read_only,
 pg_backend_pid() AS pid,
 (SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls FROM pg_roles WHERE rolname=current_user) AS elevated"""
REVISION_SQL = "SELECT version_num FROM public.alembic_version"
PRIVILEGES_SQL = """SELECT
 has_schema_privilege(current_user,'public','USAGE') AS schema_usage,
 has_schema_privilege(current_user,'public','CREATE') AS schema_create,
 has_database_privilege(current_user,current_database(),'CREATE') AS database_create,
 has_database_privilege(current_user,current_database(),'TEMP') AS database_temp,
 (SELECT count(*) FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user)) AS role_memberships,
 has_table_privilege(current_user,'public.application_sessions','SELECT') AS session_select,
 has_table_privilege(current_user,'public.application_sessions','INSERT') AS session_insert,
 has_table_privilege(current_user,'public.application_sessions','DELETE') AS session_delete,
 (SELECT COALESCE(bool_or(has_sequence_privilege(current_user,c.oid,'USAGE')),false) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='S') AS sequence_usage,
 has_table_privilege(current_user,'public.local_users','SELECT') AS users_select,
 has_table_privilege(current_user,'public.external_identities','SELECT') AS identities_select,
 (SELECT COALESCE(bool_or(has_table_privilege(current_user,c.oid,p.permission)),false) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace CROSS JOIN (VALUES ('INSERT'),('UPDATE'),('DELETE'),('TRUNCATE')) p(permission) WHERE n.nspname='public' AND c.relname IN ('companies','sites','equipments','sensors','measurements','maintenance_records','prediction_records','maintenance_recommendations')) AS business_write"""
COLUMNS_SQL = """SELECT c.relname AS table_name,a.attname AS column_name,
 has_column_privilege(current_user,c.oid,a.attnum,'UPDATE') AS can_update
 FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname IN ('application_sessions','local_users','external_identities')
 AND a.attnum>0 AND NOT a.attisdropped ORDER BY c.relname,a.attname"""


class PostgresCollector(Offline):
    """Fixed metadata queries only. No default transport: unsupported peer capture refuses."""

    @v.guarded
    def __init__(self, campaign, policy, *, transport=None, clock=_clock):
        v.validate_campaign(campaign)
        _policy(campaign, policy)
        v.require(callable(clock))
        self._campaign, self._policy, self._transport, self._clock = campaign, policy, transport, clock

    @v.guarded
    def collect(self, credentials, *, revision):
        c, policy, transport = self._campaign, self._policy, self._transport
        v.validate_campaign(c)
        _policy(c, policy)
        v.require(type(credentials) is SqlCredentials and type(credentials.role) is str and credentials.role in c.roles)
        v.require(type(credentials.password) is str and 0 < len(credentials.password) <= 4096 and not any(ord(ch)<32 for ch in credentials.password))
        v.require(type(revision) is str and revision in tuple(p.revision for p in v.PUBLICATIONS))
        v.require(transport is not None)
        start, deadline = self._clock(), monotonic() + 10
        v.utc(start)
        connection = None
        try:
            connection = transport.open_readonly(host=c.host, port=c.port, database=c.database,
                role=credentials.role, password=credentials.password, ca_der=policy.trusted_ca_der, timeout=3,
                options="-c default_transaction_read_only=on -c statement_timeout=3000 -c lock_timeout=1000")
            binding = transport.tls_binding(connection)
            v.require(type(binding) is TlsBinding and binding.connection is connection)
            v.require(binding.driver_verified is True and type(binding.socket_id) is int and binding.socket_id > 0 and binding.verified_host == c.host)
            v.require(type(binding.auth_method) is str and binding.auth_method == "scram-sha-256")
            cursor = connection.cursor()
            try:
                cursor.execute("BEGIN TRANSACTION READ ONLY")
                cursor.execute("SET LOCAL statement_timeout='3s'")
                cursor.execute("SET LOCAL lock_timeout='1s'")
                cursor.execute(IDENTITY_SQL)
                row = cursor.fetchone()
                v.require(type(row) is dict)
                v.require(row["database"] == c.database and row["session_role"] == row["role"] == credentials.role)
                v.require(row["address"] == c.server_address and type(row["port"]) is int and row["port"] == c.port)
                v.require(row["version"] == str(c.server_version_num) and row["cluster"] == c.cluster_name and row["instance"] == c.instance_id)
                v.require(row["dev_marker"] in (None, "") and row["elevated"] is False)
                v.require(row["read_only"] == row["default_read_only"] == "on" and type(row["pid"]) is int and row["pid"] > 0)
                cid = str(uuid4())
                tls_facts = dict(sslmode="verify-full", ca_sha256=sha256(policy.trusted_ca_der).hexdigest(),
                                 verified_host=binding.verified_host, tls_in_use="true", backend_pid=str(row["pid"]))
                tls_obs = Observation("tls", c.campaign_id, v.destination_fingerprint(c), "unverified_external", "bound-sql-tls", start, start, cid, tuple(sorted(tls_facts.items())))
                extra = dict(peer_certificate_sha256=sha256(binding.certificate_der).hexdigest(), chain_verified="true", hostname_verified="true")
                tls_packet = EvidencePacket(tls_obs, tuple(sorted(extra.items())), binding.certificate_der, binding.intermediates_der)
                _tls_adapter(c, policy, tls_packet, start)
                cursor.execute(REVISION_SQL)
                v.require(cursor.fetchone() == {"version_num": revision})
                cursor.execute(PRIVILEGES_SQL)
                privileges = cursor.fetchone()
                v.require(type(privileges) is dict)
                cursor.execute(COLUMNS_SQL)
                columns = cursor.fetchall()
                v.require(type(columns) is list and 1 <= len(columns) <= 64)
                for table, key in (("application_sessions", "session_update"), ("local_users", "users_update"), ("external_identities", "identities_update")):
                    selected = [item for item in columns if item["table_name"] == table]
                    v.require(selected and all(type(item["can_update"]) is bool and type(item["column_name"]) is str for item in selected))
                    privileges[key] = "*" if all(item["can_update"] for item in selected) else ",".join(sorted(item["column_name"] for item in selected if item["can_update"]))
                privileges["role_admin"] = False
                privileges["privilege_profile"] = v.ROLE_KINDS[c.roles.index(credentials.role)]
                normalized = {}
                for key, value in privileges.items():
                    v.require(type(key) is str and type(value) in (str, bool, int))
                    normalized[key] = str(value).lower() if type(value) is bool else str(value)
                facts = dict(database=row["database"], instance_id=row["instance"], cluster_name=row["cluster"],
                    session_user=row["session_role"], current_user=row["role"], server_address=row["address"],
                    server_port=str(row["port"]), version_num=row["version"], backend_pid=str(row["pid"]), revision=revision,
                    superuser="false", createdb="false", createrole="false", replication="false", bypassrls="false")
                again = transport.tls_binding(connection)
                v.require(type(again) is TlsBinding and again.connection is connection and again.socket_id == binding.socket_id
                          and again.driver_verified is True and again.verified_host == binding.verified_host
                          and again.auth_method == binding.auth_method
                          and again.certificate_der == binding.certificate_der and again.intermediates_der == binding.intermediates_der)
                end = self._clock()
                v.utc(end)
                v.require(monotonic() <= deadline and 0 <= (end-start).total_seconds() <= 10)
                pg_obs = Observation("postgres", c.campaign_id, v.destination_fingerprint(c), "unverified_external", "bound-sql-metadata", start, end, cid, tuple(sorted(facts.items())))
                from dataclasses import replace
                result = (EvidencePacket(pg_obs, tuple(sorted(normalized.items()))), replace(tls_packet, observation=replace(tls_obs, observed_at=end)))
                # Reuse the exact role profile without inventing effective privileges.
                from b2b_postgres_qualification.evidence import _postgres_adapter
                _postgres_adapter(c, result[0])
                return result
            finally:
                try:
                    connection.rollback()
                finally:
                    cursor.close()
        finally:
            if connection is not None:
                connection.close()
