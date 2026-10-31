"""Independent synthetic expectations/observations. No Docker transport exists."""

import ast
import builtins
from dataclasses import FrozenInstanceError, fields, replace
from datetime import datetime, timedelta, timezone, tzinfo
from pathlib import Path
import socket
import subprocess
import threading
import traceback

import pytest

from oidc_postgres_support import campaign_contract
from oidc_postgres_bootstrap.controller import ArtifactDigest, Clock, ClockSample, controller_contract
from oidc_postgres_bootstrap import docker_attestation as d


T0 = datetime(2030, 1, 1, tzinfo=timezone.utc)
N0 = 100_000_000_000
NOW = ClockSample(T0, N0)
MARKER = "SYNTHETIC_SENSITIVE_DOCKER_MARKER"


@pytest.fixture(autouse=True)
def forbid_operations(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("operational effect")
        raise AssertionError("No operational effects permitted")

    for target, name in ((subprocess, "Popen"), (subprocess, "run"), (socket.socket, "connect"),
                         (socket.socket, "connect_ex"), (socket, "create_connection"),
                         (socket, "getaddrinfo"), (threading.Thread, "start")):
        monkeypatch.setattr(target, name, forbidden)
    original = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"docker", "requests", "http", "urllib", "sqlalchemy", "psycopg", "psycopg2", "app", "alembic"}:
            forbidden()
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    yield
    assert attempts == []


def expected_binding():
    campaign = campaign_contract(
        campaign_id="00000000-0000-4000-8000-000000000001", container_id="a" * 64,
        container_name="oidc-tx-00000000000040008000000000000001-postgres",
        image_ref="docker.io/library/postgres@sha256:" + "b" * 64,
        image_id="sha256:" + "c" * 64, platform="linux/amd64", network_id="d" * 64,
        network_name="oidc-tx-00000000000040008000000000000001-net", subnet="172.30.91.0/28", gateway="172.30.91.1",
        storage_kind="tmpfs", storage_target="/var/lib/postgresql/data", storage_bytes=268435456,
        host="127.0.0.1", port=56439, database="oidct_00000000000040008000000000000001",
        preparation_role="oidct_00000000000040008000000000000001_owner",
        application_role="oidct_00000000000040008000000000000001_app",
        observation_role="oidct_00000000000040008000000000000001_observer", transport="verify-full", ca_sha256="e" * 64,
        server_address="172.30.91.2", server_port=5432, server_version_num=170010,
        cluster_name="oidc-test-00000000000040008000000000000001", scope="public.oidc_transactions")
    names = ("bootstrap.sh", "controller.py", "openssl.cnf.in", "pg_hba.local.conf.in", "pg_hba.tls.conf.in",
             "postgresql.local.conf.in", "postgresql.tls.conf.in", "roles.sql.in", "validation.py")
    return controller_contract(campaign=campaign, session_id="11111111-1111-4111-8111-111111111111",
        collector_session_id="22222222-2222-4222-8222-222222222222", engine_id="33333333-3333-4333-8333-333333333333",
        git_revision="a" * 40, artifacts=tuple(ArtifactDigest(name, "c" * 64) for name in names))


def expected_values():
    return dict(campaign_id="00000000-0000-4000-8000-000000000001",
        engine=d.EngineIdentity("33333333-3333-4333-8333-333333333333", "28.5.1", "linux", "amd64"),
        context=d.DockerContext("synthetic-context", "e" * 64),
        container=d.ContainerIdentity("a" * 64, "oidc-tx-00000000000040008000000000000001-postgres"),
        network=d.NetworkIdentity("d" * 64, "oidc-tx-00000000000040008000000000000001-net", "bridge", True,
                                  "172.30.91.0/28", "172.30.91.1", ()),
        image=d.ImageIdentity("sha256:" + "c" * 64, "docker.io/library/postgres@sha256:" + "b" * 64, "linux/amd64"),
        entrypoint=("/bin/bash", "/oidc/bootstrap.sh"), command=(),
        mounts=(d.Mount("tmpfs", "", "/var/lib/postgresql/data", 268435456, False, ("nodev", "noexec", "nosuid")),),
        volumes=(), container_networks=("d" * 64,),
        published_ports=(d.PortBinding("127.0.0.1", 56439, 5432, "tcp"),),
        limits=d.ResourceLimits(805306368, 1000000000), restart_policy=d.RestartPolicy("no", 0),
        state=d.ContainerState("created", False, False, False, False, False, 0, 0), privileged=False)


def expectation_values():
    return dict(binding=expected_binding(), snapshot=d.docker_snapshot(**expected_values()))


def expected():
    return d.docker_expectation(**expectation_values())


def observed_values():
    # Literal collector fixture, NOT constructed from expected_values(), a binding,
    # an expectation, or any serialization/replacement of the expected snapshot.
    snapshot = d.docker_snapshot(
        campaign_id="00000000-0000-4000-8000-000000000001",
        engine=d.EngineIdentity("33333333-3333-4333-8333-333333333333", "28.5.1", "linux", "amd64"),
        context=d.DockerContext("synthetic-context", "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"),
        container=d.ContainerIdentity("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                                     "oidc-tx-00000000000040008000000000000001-postgres"),
        network=d.NetworkIdentity("dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
            "oidc-tx-00000000000040008000000000000001-net", "bridge", True, "172.30.91.0/28", "172.30.91.1", ()),
        image=d.ImageIdentity("sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
            "docker.io/library/postgres@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", "linux/amd64"),
        entrypoint=("/bin/bash", "/oidc/bootstrap.sh"), command=(),
        mounts=(d.Mount("tmpfs", "", "/var/lib/postgresql/data", 268435456, False, ("nodev", "noexec", "nosuid")),),
        volumes=(), container_networks=("dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",),
        published_ports=(d.PortBinding("127.0.0.1", 56439, 5432, "tcp"),),
        limits=d.ResourceLimits(805306368, 1000000000), restart_policy=d.RestartPolicy("no", 0),
        state=d.ContainerState("created", False, False, False, False, False, 0, 0), privileged=False)
    names = ("bootstrap.sh", "controller.py", "openssl.cnf.in", "pg_hba.local.conf.in", "pg_hba.tls.conf.in",
             "postgresql.local.conf.in", "postgresql.tls.conf.in", "roles.sql.in", "validation.py")
    return dict(snapshot=snapshot, provenance=d.DeclaredProvenance.SIMULATED,
        controller_session_id="11111111-1111-4111-8111-111111111111",
        collector_session_id="22222222-2222-4222-8222-222222222222", git_revision="a" * 40,
        artifacts=tuple(ArtifactDigest(name, "c" * 64) for name in names),
        interval=d.CollectionInterval(T0, T0, N0, N0))


def observed():
    return d.docker_observation(**observed_values())


class FakeClock(Clock):
    def sample(self):
        return NOW


class FakeSource(d.ObservationSource):
    def collect(self):
        return observed()


def rejected(operation):
    with pytest.raises(d.AttestationRejected) as caught:
        operation()
    error = caught.value
    assert str(error) == "OIDC injected Docker observation rejected"
    assert error.__context__ is None and error.__cause__ is None and error.__suppress_context__ is True
    assert MARKER not in str(error) + repr(error) + "".join(traceback.format_exception(error))


def test_nominal_simulation_is_frozen_opaque_and_never_authenticated():
    result = d.collect_attestation(expected(), FakeSource(), FakeClock())
    assert result.observation == observed()
    assert result.classification == "injected_docker_concordance_only"
    for item in (expected(), result, result.observation, result.observation.snapshot,
                 result.observation.interval, result.observation.snapshot.engine):
        assert item.authenticated is False and item.execution_authorized is False
        assert MARKER not in repr(item) and "injected-unverified" in repr(item)
        rejected(lambda: bool(item))
        with pytest.raises((FrozenInstanceError, TypeError)):
            item.injected_field = True
    with pytest.raises(FrozenInstanceError):
        result.observation.snapshot.engine.engine_id = MARKER


@pytest.mark.parametrize("factory,values", [(d.docker_snapshot, expected_values),
    (d.docker_expectation, expectation_values), (d.docker_observation, observed_values)])
def test_closed_factories_reject_every_missing_or_unknown_field(factory, values):
    for name in values():
        data = values()
        del data[name]
        rejected(lambda: factory(**data))
    rejected(lambda: factory(**dict(values(), authenticated=True)))
    rejected(lambda: factory(**dict(values(), unknown=MARKER)))


@pytest.mark.parametrize("group,field,value", [
    ("engine", "engine_id", "44444444-4444-4444-8444-444444444444"),
    ("engine", "server_version", "28.5.2"), ("engine", "os_type", "windows"), ("engine", "architecture", "arm64"),
    ("context", "name", "different"), ("context", "endpoint_sha256", "f" * 64),
    ("container", "container_id", "f" * 64), ("container", "name", "other"),
    ("network", "network_id", "f" * 64), ("network", "name", "other"), ("network", "driver", "host"),
    ("network", "internal", False), ("network", "subnet", "172.30.92.0/28"),
    ("network", "gateway", "172.30.91.3"), ("network", "members", ("f" * 64,)),
    ("image", "image_id", "sha256:" + "f" * 64),
    ("image", "repository_digest", "docker.io/library/postgres@sha256:" + "f" * 64),
    ("image", "platform", "linux/arm64"),
    ("limits", "memory_bytes", 805306367), ("limits", "nano_cpus", 2000000000),
    ("restart_policy", "name", "always"), ("restart_policy", "maximum_retry_count", 1),
    ("state", "status", "running"), ("state", "running", True), ("state", "paused", True),
    ("state", "restarting", True), ("state", "dead", True), ("state", "ever_started", True),
    ("state", "exit_code", 1), ("state", "restart_count", 1),
])
def test_each_critical_nested_divergence_is_rejected(group, field, value):
    proof = observed()
    snapshot = proof.snapshot
    changed = replace(getattr(snapshot, group), **{field: value})
    rejected(lambda: d.build_attestation(expected(), replace(proof, snapshot=replace(snapshot, **{group: changed})), NOW))


@pytest.mark.parametrize("field,value", [
    ("campaign_id", "44444444-4444-4444-8444-444444444444"),
    ("entrypoint", ("/bin/other",)), ("entrypoint", ()), ("command", ("postgres",)),
    ("entrypoint", ("/bin/sh", "-c", "echo secret; dangerous")),
    ("mounts", ()), ("volumes", ("unapproved-volume",)), ("container_networks", ("d" * 64, "f" * 64)),
    ("privileged", True), ("privileged", 0), ("command", []), ("state", {}),
])
def test_snapshot_divergences_or_malformed_collections_are_rejected(field, value):
    proof = replace(observed(), snapshot=replace(observed().snapshot, **{field: value}))
    rejected(lambda: d.build_attestation(expected(), proof, NOW))


@pytest.mark.parametrize("field,value", [("kind", "bind"), ("source", "/host/path"), ("target", "/other"),
    ("size_bytes", 134217728), ("size_bytes", True), ("read_only", True), ("options", ()),
    ("options", ("exec", "suid"))])
def test_mount_changes_are_rejected(field, value):
    proof = observed()
    mount = replace(proof.snapshot.mounts[0], **{field: value})
    rejected(lambda: d.build_attestation(expected(), replace(proof, snapshot=replace(proof.snapshot, mounts=(mount,))), NOW))


def validate_options_via(path, options):
    original = observed()
    # Raw construction deliberately bypasses every validating factory.
    mount = d.Mount("tmpfs", "", "/var/lib/postgresql/data", 268435456, False, options)
    values = {field.name: getattr(original.snapshot, field.name) for field in fields(d.DockerSnapshot)}
    values["mounts"] = (mount,)
    snapshot = d.DockerSnapshot(**values)
    proof = d.DockerObservation(**{field.name: snapshot if field.name == "snapshot" else getattr(original, field.name)
                                  for field in fields(d.DockerObservation)})
    if path == "factory":
        return d.docker_snapshot(**values)
    if path == "build":
        return d.build_attestation(expected(), proof, NOW)

    class InjectedSource(d.ObservationSource):
        def collect(self):
            return proof

    return d.collect_attestation(expected(), InjectedSource(), FakeClock())


@pytest.mark.parametrize("path", ["factory", "build", "collect"])
def test_native_mount_options_remain_nominal_on_all_paths(path):
    result = validate_options_via(path, ("nodev", "noexec", "nosuid"))
    assert result.authenticated is False and result.execution_authorized is False


@pytest.mark.parametrize("path", ["factory", "build", "collect"])
@pytest.mark.parametrize("kind", ["str_subclass", "mutable_true", "counter", "raises", "mixed", "last_mixed", "list", "tuple_subclass"])
def test_mount_option_types_are_rejected_before_any_custom_equality(path, kind):
    calls = []

    class StringSubclass(str):
        def __eq__(self, other):
            calls.append("string equality")
            return super().__eq__(other)

    class MutableAlwaysEqual:
        def __init__(self):
            self.payload = []

        def __eq__(self, other):
            calls.append("mutable equality")
            self.payload.append(other)
            return True

    class CountingEqual:
        def __eq__(self, other):
            calls.append("counted equality")
            return True

    class RaisingEqual:
        def __eq__(self, other):
            calls.append("raising equality")
            raise RuntimeError(MARKER)

    class TupleSubclass(tuple):
        def __eq__(self, other):
            calls.append("tuple equality")
            return super().__eq__(other)

    if kind == "list":
        options = ["nodev", "noexec", "nosuid"]
    elif kind == "tuple_subclass":
        options = TupleSubclass(("nodev", "noexec", "nosuid"))
    elif kind == "mixed":
        options = ("nodev", CountingEqual(), "nosuid")
    elif kind == "last_mixed":
        options = ("nodev", "noexec", CountingEqual())
    else:
        first = {"str_subclass": StringSubclass("nodev"), "mutable_true": MutableAlwaysEqual(),
                 "counter": CountingEqual(), "raises": RaisingEqual()}[kind]
        options = (first, "noexec", "nosuid")
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        rejected(lambda: validate_options_via(path, options))
    assert calls == []
    if kind == "mutable_true":
        assert options[0].payload == []


@pytest.mark.parametrize("field,value", [("host", "0.0.0.0"), ("host_port", 5433), ("container_port", 5433),
    ("protocol", "udp"), ("host_port", True)])
def test_unexpected_port_details_are_rejected(field, value):
    proof = observed()
    port = replace(proof.snapshot.published_ports[0], **{field: value})
    rejected(lambda: d.build_attestation(expected(), replace(proof, snapshot=replace(proof.snapshot, published_ports=(port,))), NOW))


def test_additional_mount_or_port_is_not_ignored():
    for field in ("mounts", "published_ports"):
        proof = observed()
        doubled = getattr(proof.snapshot, field) * 2
        rejected(lambda: d.build_attestation(expected(), replace(proof, snapshot=replace(proof.snapshot, **{field: doubled})), NOW))


@pytest.mark.parametrize("field,value", [("controller_session_id", "44444444-4444-4444-8444-444444444444"),
    ("collector_session_id", "44444444-4444-4444-8444-444444444444"), ("git_revision", "f" * 40),
    ("artifacts", ()), ("provenance", None), ("provenance", "authenticated"), ("provenance", True),
    ("interval", None)])
def test_incomplete_metadata_or_false_provenance_is_rejected(field, value):
    rejected(lambda: d.build_attestation(expected(), replace(observed(), **{field: value}), NOW))


def test_artifacts_and_binding_cannot_be_substituted():
    proof = observed()
    changed = (replace(proof.artifacts[0], sha256="f" * 64), *proof.artifacts[1:])
    rejected(lambda: d.build_attestation(expected(), replace(proof, artifacts=changed), NOW))
    rejected(lambda: d.build_attestation(expected(), replace(proof, artifacts=proof.artifacts[:-1]), NOW))
    binding = replace(expected_binding(), engine_id="44444444-4444-4444-8444-444444444444")
    rejected(lambda: d.docker_expectation(binding=binding, snapshot=expected().snapshot))
    rejected(lambda: d.docker_expectation(binding=True, snapshot=expected().snapshot))


def test_unverified_provenance_is_a_label_never_real_evidence():
    proof = replace(observed(), provenance=d.DeclaredProvenance.UNVERIFIED_DECLARATION)
    result = d.build_attestation(expected(), proof, NOW)
    assert result.authenticated is False and result.execution_authorized is False
    assert result.classification == "injected_docker_concordance_only"
    with pytest.raises(TypeError):
        d.ObservationSource()
    for source in (None, True, object(), proof):
        rejected(lambda: d.collect_attestation(expected(), source, FakeClock()))


@pytest.mark.parametrize("utc_us,mono_ns,accepted", [
    (0, 0, True), (5000000, 5000000000, True), (5000001, 5000000000, False),
    (5000000, 5000000001, False), (-1, 0, False), (0, -1, False),
    (1000, 0, True), (1001, 0, False), (0, 1000000, True), (0, 1000001, False),
])
def test_proof_age_strict_bounds_and_clock_coherence(utc_us, mono_ns, accepted):
    now = ClockSample(T0 + timedelta(microseconds=utc_us), N0 + mono_ns)
    if accepted:
        assert d.build_attestation(expected(), observed(), now).authenticated is False
    else:
        rejected(lambda: d.build_attestation(expected(), observed(), now))


@pytest.mark.parametrize("utc_us,mono_ns,accepted", [
    (5000000, 5000000000, True), (5000001, 5000000000, False), (5000000, 5000000001, False),
    (-1, 0, False), (0, -1, False), (1000000, 0, False), (1000, 0, True), (1001, 0, False),
])
def test_collection_intervals_are_typed_bounded_and_coherent(utc_us, mono_ns, accepted):
    interval = d.CollectionInterval(T0 - timedelta(microseconds=utc_us), T0, N0 - mono_ns, N0)
    proof = replace(observed(), interval=interval)
    if accepted:
        assert d.build_attestation(expected(), proof, NOW).authenticated is False
    else:
        rejected(lambda: d.build_attestation(expected(), proof, NOW))


@pytest.mark.parametrize("field,value", [("started_ns", True), ("ended_ns", -1),
    ("started_at", T0.replace(tzinfo=None)), ("ended_at", "2030-01-01")])
def test_malformed_interval_fields(field, value):
    rejected(lambda: d.docker_observation(**dict(observed_values(), interval=replace(observed().interval, **{field: value}))))


def test_collection_uses_clock_after_callback_and_refuses_cached_or_stale_data():
    class SequenceClock(Clock):
        def __init__(self, first, second):
            self.samples = iter((first, second))

        def sample(self):
            return next(self.samples)

    rejected(lambda: d.collect_attestation(expected(), FakeSource(), SequenceClock(NOW, ClockSample(T0 + timedelta(seconds=6), N0 + 6000000000))))
    rejected(lambda: d.collect_attestation(expected(), FakeSource(), SequenceClock(ClockSample(T0 + timedelta(seconds=1), N0 + 1000000000),
                                                                                  ClockSample(T0 + timedelta(seconds=1), N0 + 1000000000))))
    rejected(lambda: d.collect_attestation(expected(), FakeSource(), SequenceClock(NOW, ClockSample(T0, N0 - 1))))
    rejected(lambda: d.collect_attestation(expected(), FakeSource(), SequenceClock(NOW, ClockSample(T0 + timedelta(seconds=1), N0))))
    rejected(lambda: d.collect_attestation(expected(), FakeSource(), None))


def test_errors_are_detached_from_sensitive_caller_source_clock_and_timezone(caplog, capsys):
    class ExplodingSource(d.ObservationSource):
        def collect(self):
            raise RuntimeError(MARKER)

    class ExplodingClock(Clock):
        def sample(self):
            raise RuntimeError(MARKER)

    class ExplodingTimezone(tzinfo):
        def utcoffset(self, value):
            raise RuntimeError(MARKER)

    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        rejected(lambda: d.collect_attestation(expected(), ExplodingSource(), FakeClock()))
        rejected(lambda: d.collect_attestation(expected(), FakeSource(), ExplodingClock()))
        rejected(lambda: d.docker_observation(**dict(observed_values(), unknown=MARKER)))
        rejected(lambda: d.build_attestation(expected(), observed(), ClockSample(datetime(2030, 1, 1, tzinfo=ExplodingTimezone()), N0)))
        rejected(lambda: bool(observed()))
    assert caplog.records == []
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_no_environment_activation_or_import_effects(monkeypatch):
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "PGHOST", "APPROVED"):
        monkeypatch.setenv(name, MARKER)
    assert d.build_attestation(expected(), observed(), NOW).authenticated is False
    source = Path(d.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert imports <= {"abc", "dataclasses", "datetime", "enum", "functools", "ipaddress", "re", "uuid", "oidc_postgres_bootstrap.controller"}
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"now", "utcnow"}
                   for node in ast.walk(tree))
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("IO")
        raise AssertionError("No file IO on import")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    exec(compile(source, "offline_docker_import_probe", "exec"), {"__name__": "offline_docker_import_probe"})
    assert attempts == []
