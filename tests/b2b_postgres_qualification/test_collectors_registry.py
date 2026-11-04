"""Only synthetic transports and isolated temporary SQLite/filesystem resources."""

from dataclasses import replace
from contextlib import contextmanager
from hashlib import sha256
import json
import multiprocessing
from pathlib import Path
import tempfile
import traceback
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from b2b_postgres_qualification import collectors as c, durable as d, evidence as e, validation as v
from b2b_postgres_qualification.contracts import Rejected, ExecutionDisabled
from b2b_postgres_qualification.test_authority_evidence import (
    NOW, PRIVATE, APPROVAL_ID, INITIAL_REVISION, campaign, certificates, base_campaign,
    policy as base_policy, packets, signing_key, trusted, approval, plan, sign,
)


ENDPOINT = "npipe:////./pipe/b2bq-synthetic"
LIMITS = c.ResourceLimits(512 * 1024**2, 1000000000, 128 * 1024**2)


@pytest.fixture(autouse=True)
def no_real_collection(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Real collection forbidden")
    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection", "socket.getaddrinfo", "subprocess.run", "os.system"):
        monkeypatch.setattr(name, forbidden)


@pytest.fixture
def policy(base_policy):
    return replace(base_policy, endpoint_sha256=sha256(ENDPOINT.encode()).hexdigest())


def docker_data(campaign, policy):
    def container(cid, name, image, ip, mounts):
        return dict(id=cid, name="/" + name, image="sha256:" + image,
            image_ref="docker.io/library/postgres@sha256:" + campaign.image_sha256,
            networks={campaign.network_name: {"NetworkID": campaign.network_id, "IPAddress": ip}},
            mounts=mounts, ports={"5432/tcp": None}, status="running", privileged=False,
            restart="no", memory=LIMITS.memory_bytes, cpus=LIMITS.nano_cpus, shm=LIMITS.shm_bytes, readonly_root=True)
    return dict(
        endpoint=ENDPOINT, engine=campaign.engine_id,
        postgres=container(campaign.container_id, campaign.container_name, policy.image_id_sha256,
            campaign.server_address, [dict(Type="volume", Name=campaign.volume_name, Destination="/var/lib/postgresql/data", RW=True)]),
        runner=container(campaign.runner_id, campaign.container_name.removesuffix("-postgres") + "-runner", "3" * 64, "172.29.211.3", []),
        network=dict(id=campaign.network_id, name=campaign.network_name, driver="bridge", internal=True,
            members={campaign.container_id: {}, campaign.runner_id: {}}, ipam=[dict(Subnet=campaign.subnet)]),
        volume=dict(name=campaign.volume_name, driver="local", scope="local", created=policy.volume_created_at.isoformat()),
        image=dict(id="sha256:" + policy.image_id_sha256, digests=["docker.io/library/postgres@sha256:" + campaign.image_sha256], os="linux", arch="amd64"),
        runner_image=dict(id="sha256:" + "3" * 64, digests=["synthetic@sha256:" + "4" * 64], os="linux", arch="amd64"),
    )


def docker_mock(monkeypatch, campaign, data):
    calls = []
    def run(argv, **options):
        calls.append((argv, options))
        action = argv[3:]
        if action[:2] == ["context", "inspect"]: value = data["endpoint"]
        elif action[0] == "info": value = data["engine"]
        elif action[0] == "inspect": value = data["postgres"] if action[-1] == campaign.container_id else data["runner"]
        elif action[0] == "network": value = data["network"]
        elif action[0] == "volume": value = data["volume"]
        elif action[0] == "image": value = data["image"] if action[2] == data["postgres"]["image"] else data["runner_image"]
        else: raise AssertionError("Mutating Docker command")
        return SimpleNamespace(returncode=0, stdout=json.dumps(value).encode(), stderr=b"")
    monkeypatch.setattr(c.subprocess, "run", run)
    return calls


def docker_collector(campaign, policy):
    return c.DockerCollector(campaign, policy, executable=str(Path.cwd() / "synthetic-docker.exe"),
        postgres_limits=LIMITS, runner_limits=LIMITS, runner_image_id_sha256="3" * 64, clock=lambda: NOW)


def test_read_only_docker_collection_with_mocked_cli(monkeypatch, campaign, policy):
    calls = docker_mock(monkeypatch, campaign, docker_data(campaign, policy))
    result = docker_collector(campaign, policy).collect()
    e._docker_adapter(campaign, policy, result.packet)
    assert not result.real_attested and not result.execution_authorized
    assert len(calls) == 8
    for argv, options in calls:
        assert options["shell"] is False and 0 < options["timeout"] <= 3
        assert ".Config.Env" not in " ".join(argv)
        assert not {"start", "stop", "run", "exec", "create", "rm", "up", "down"} & set(argv)
    with pytest.raises(ExecutionDisabled):
        v.request_execution(result)


@pytest.mark.parametrize("kind,field,value", [
    ("postgres", "id", "f" * 64), ("postgres", "name", "/industrial-predict-postgres-ui47"),
    ("postgres", "ports", {"5432/tcp": [{"HostIp": "0.0.0.0", "HostPort": "5434"}]}),
    ("postgres", "memory", 0), ("runner", "readonly_root", False),
    ("runner", "image", "sha256:" + "f" * 64), ("network", "internal", False),
    ("network", "members", {"unapproved": {}}), ("volume", "name", "industrial-predict-postgres-ui47-data"),
    ("image", "digests", []),
])
def test_incomplete_or_falsified_docker_results(monkeypatch, campaign, policy, kind, field, value):
    data = docker_data(campaign, policy)
    data[kind][field] = value
    docker_mock(monkeypatch, campaign, data)
    with pytest.raises(Rejected): docker_collector(campaign, policy).collect()


def test_docker_destination_and_error_sanitization(monkeypatch, campaign, policy):
    data = docker_data(campaign, policy)
    data["endpoint"] = "tcp://unapproved.invalid:2375"
    calls = docker_mock(monkeypatch, campaign, data)
    with pytest.raises(Rejected): docker_collector(campaign, policy).collect()
    assert len(calls) == 1
    data = docker_data(campaign, policy)
    del data["postgres"]["mounts"]
    docker_mock(monkeypatch, campaign, data)
    with pytest.raises(Rejected): docker_collector(campaign, policy).collect()
    monkeypatch.setattr(c.subprocess, "run", Mock(side_effect=RuntimeError(PRIVATE)))
    with pytest.raises(Rejected) as caught: docker_collector(campaign, policy).collect()
    assert PRIVATE not in "".join(traceback.format_exception(caught.value))


class FakeCursor:
    def __init__(self, connection): self.connection = connection
    def execute(self, query):
        assert query in ("BEGIN TRANSACTION READ ONLY", "SET LOCAL statement_timeout='3s'", "SET LOCAL lock_timeout='1s'",
                         c.IDENTITY_SQL, c.REVISION_SQL, c.PRIVILEGES_SQL, c.COLUMNS_SQL)
        self.connection.queries.append(query)
        self.last = query
    def fetchone(self):
        return {c.IDENTITY_SQL: self.connection.identity, c.REVISION_SQL: {"version_num": INITIAL_REVISION},
                c.PRIVILEGES_SQL: dict(self.connection.privileges)}[self.last]
    def fetchall(self):
        assert self.last == c.COLUMNS_SQL
        return self.connection.columns
    def close(self): pass


class FakeConnection:
    def __init__(self, campaign, packets):
        role = campaign.roles[2]
        self.identity = dict(database=campaign.database, session_role=role, role=role, address=campaign.server_address,
            port=5432, version="170010", cluster=campaign.cluster_name, dev_marker=None,
            instance=campaign.instance_id, read_only="on", default_read_only="on", pid=103, elevated=False)
        extra = dict(packets[5].supplemental)
        self.privileges = {key: True if value == "true" else False if value == "false" else int(value) if key == "role_memberships" else value
            for key, value in extra.items() if key not in ("session_update", "users_update", "identities_update", "privilege_profile", "role_admin")}
        self.columns = [dict(table_name=table, column_name=name, can_update=name in allowed)
            for table, names, allowed in (
                ("application_sessions", ("secret_digest", "last_activity_at", "replaced_by", "revoked_at"), {"last_activity_at", "replaced_by", "revoked_at"}),
                ("local_users", ("id", "state"), {"id"}), ("external_identities", ("id", "user_id", "issuer", "subject"), {"id"}))
            for name in names]
        self.queries, self.rolled_back, self.closed = [], False, False
    def cursor(self): return FakeCursor(self)
    def rollback(self): self.rolled_back = True
    def close(self): self.closed = True
    def commit(self): raise AssertionError("SQL collector cannot commit")


class FakeTransport:
    def __init__(self, connection, campaign, packets):
        self.connection = connection
        self.binding = c.TlsBinding(connection, 7, True, "scram-sha-256", campaign.host, packets[2].certificate_der, ())
        self.opened = None
    def open_readonly(self, **options): self.opened = options; return self.connection
    def tls_binding(self, connection): assert connection is self.connection; return self.binding


def test_sql_tls_same_connection_metadata_and_rollback(campaign, policy, packets):
    connection = FakeConnection(campaign, packets)
    transport = FakeTransport(connection, campaign, packets)
    result = c.PostgresCollector(campaign, policy, transport=transport, clock=lambda: NOW).collect(
        c.SqlCredentials(campaign.roles[2], "synthetic-only-password"), revision=INITIAL_REVISION)
    assert connection.closed and connection.rolled_back
    assert "default_transaction_read_only=on" in transport.opened["options"]
    assert transport.opened["host"] == campaign.host and transport.opened["timeout"] == 3
    e._postgres_adapter(campaign, result[0])
    e._tls_adapter(campaign, policy, result[1], NOW)
    assert result[0].observation.connection_id == result[1].observation.connection_id
    assert not result[0].real_attested


@pytest.mark.parametrize("field,value", [("database", "industrial_predict_dev"), ("instance", "wrong"),
    ("session_role", "ui47_app"), ("read_only", "off"), ("default_read_only", "off"), ("elevated", True), ("dev_marker", "existing-dev")])
def test_sql_identity_refused_before_catalogs(campaign, policy, packets, field, value):
    connection = FakeConnection(campaign, packets)
    connection.identity[field] = value
    transport = FakeTransport(connection, campaign, packets)
    with pytest.raises(Rejected):
        c.PostgresCollector(campaign, policy, transport=transport, clock=lambda: NOW).collect(c.SqlCredentials(campaign.roles[2], "synthetic"), revision=INITIAL_REVISION)
    assert c.REVISION_SQL not in connection.queries and connection.closed and connection.rolled_back


@pytest.mark.parametrize("change", [{"driver_verified": False}, {"connection": object()}, {"auth_method": "trust"},
    {"verified_host": "localhost"}, {"certificate_der": b"invalid synthetic certificate"}])
def test_sql_tls_binding_or_certificate_failure(campaign, policy, packets, change):
    connection = FakeConnection(campaign, packets)
    transport = FakeTransport(connection, campaign, packets)
    transport.binding = replace(transport.binding, **change)
    with pytest.raises(Rejected):
        c.PostgresCollector(campaign, policy, transport=transport, clock=lambda: NOW).collect(c.SqlCredentials(campaign.roles[2], "synthetic"), revision=INITIAL_REVISION)
    assert connection.closed and c.PRIVILEGES_SQL not in connection.queries


def test_no_default_sql_transport_and_credentials_repr(campaign, policy):
    credentials = c.SqlCredentials(campaign.roles[2], PRIVATE)
    assert PRIVATE not in repr(credentials)
    with pytest.raises(Rejected): c.PostgresCollector(campaign, policy).collect(credentials, revision=INITIAL_REVISION)
    with pytest.raises(ExecutionDisabled): v.request_execution(credentials)


@pytest.fixture
def registry_directory():
    with tempfile.TemporaryDirectory(prefix="b2bq-registry-", dir=Path.cwd()) as directory:
        d.initialize_test_registry(directory)
        yield directory


def registry(directory, trusted):
    return d.DurableApprovalRegistry(directory=directory, trusted_keys=(trusted,))


def consume(store, campaign, plan, approval, signed):
    return store.consume_verified(campaign, plan, approval, signed, expected_initial_state_sha256="f" * 64, now=NOW)


def _consume_worker(directory, trusted, campaign, plan, approval, signed, queue):
    try:
        consume(registry(directory, trusted), campaign, plan, approval, signed)
        queue.put("consumed")
    except Rejected: queue.put("rejected")
    except Exception: queue.put("unexpected")


def test_atomic_replay_across_processes_and_restart(registry_directory, campaign, plan, approval, trusted, signing_key):
    signed = sign(campaign, plan, approval, signing_key)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    workers = [context.Process(target=_consume_worker, args=(registry_directory, trusted, campaign, plan, approval, signed, queue)) for _ in range(3)]
    try:
        for worker in workers: worker.start()
        results = [queue.get(timeout=30) for _ in workers]
        for worker in workers:
            worker.join(timeout=30)
            assert not worker.is_alive() and worker.exitcode == 0
        assert sorted(results) == ["consumed", "rejected", "rejected"]
    finally:
        for worker in workers:
            if worker.is_alive(): worker.terminate(); worker.join()
        queue.close(); queue.join_thread()
    restarted = registry(registry_directory, trusted)
    report = restarted.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID)
    assert report.state == "consumed" and report.campaign_id == campaign.campaign_id and report.history == ("consumed",)
    with pytest.raises(Rejected): consume(restarted, campaign, plan, approval, signed)
    with pytest.raises(ExecutionDisabled): v.request_execution(report)


def test_durable_uncertainty_is_terminal(registry_directory, campaign, plan, approval, trusted, signing_key):
    store = registry(registry_directory, trusted)
    signed = sign(campaign, plan, approval, signing_key)
    receipt = consume(store, campaign, plan, approval, signed)
    store.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID, campaign_id=campaign.campaign_id,
        envelope_sha256=receipt.envelope_sha256, outcome="uncertain")
    restarted = registry(registry_directory, trusted)
    assert restarted.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID).state == "uncertain"
    for outcome in v.OUTCOMES:
        with pytest.raises(Rejected):
            restarted.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID,
                campaign_id=campaign.campaign_id, envelope_sha256=receipt.envelope_sha256, outcome=outcome)


@pytest.mark.parametrize("commit_first", [False, True])
def test_registry_commit_uncertainty_preserves_reservation(monkeypatch, registry_directory, campaign, plan, approval, trusted, signing_key, commit_first):
    store = registry(registry_directory, trusted)
    signed = sign(campaign, plan, approval, signing_key)
    original = d._connect
    class LostAcknowledgement:
        def __init__(self, connection): self.connection = connection
        def execute(self, *args): return self.connection.execute(*args)
        def commit(self):
            if commit_first: self.connection.commit()
            raise OSError(PRIVATE)
        def close(self): self.connection.close()
    with monkeypatch.context() as patch:
        patch.setattr(d, "_connect", lambda root: LostAcknowledgement(original(root)))
        with pytest.raises(d.RegistryUncertain) as caught: consume(store, campaign, plan, approval, signed)
        assert PRIVATE not in "".join(traceback.format_exception(caught.value))
    restarted = registry(registry_directory, trusted)
    assert restarted.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID).state == "uncertain"
    with pytest.raises(Rejected): consume(restarted, campaign, plan, approval, signed)


def test_fake_approval_and_content_substitution_never_consume(registry_directory, campaign, plan, approval, trusted, signing_key):
    store = registry(registry_directory, trusted)
    signed = sign(campaign, plan, approval, signing_key)
    for invalid in (True, Mock(signature_verified=True), replace(signed, signature=bytes(64))):
        with pytest.raises(Rejected): consume(store, campaign, plan, approval, invalid)
    assert store.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID).state == "absent"
    consume(store, campaign, plan, approval, signed)
    other = replace(approval, expires_at=approval.expires_at.replace(second=1))
    signed_other = sign(campaign, plan, other, signing_key)
    with pytest.raises(Rejected): consume(store, campaign, plan, other, signed_other)


def test_terminal_success_history_is_metadata_only(registry_directory, campaign, plan, approval, trusted, signing_key):
    store = registry(registry_directory, trusted)
    receipt = consume(store, campaign, plan, approval, sign(campaign, plan, approval, signing_key))
    result = store.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID,
        campaign_id=campaign.campaign_id, envelope_sha256=receipt.envelope_sha256, outcome="commit_confirmed")
    assert not result.execution_authorized
    assert store.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID).history == ("consumed", "commit_confirmed")
    assert PRIVATE not in repr(result)


@pytest.mark.parametrize("environment", ["development", "P101Private", "oidc-private"])
def test_registry_paths_exclude_existing_environment_names(environment):
    # No directory is created; rejection precedes path resolution/initialization.
    with pytest.raises(Rejected):
        d.initialize_test_registry(Path.cwd() / environment / "b2bq-registry-forbidden")


def _paused_outcome_worker(directory, trusted, campaign_id, authority_id, envelope, ready, resume, queue):
    """Pause B after a stale observation, before the real approval lock."""
    original = d._approval_lock
    @contextmanager
    def paused(claim):
        assert not d._present(claim.with_suffix(".uncertain"))
        ready.set()
        assert resume.wait(30)
        with original(claim):
            yield
    try:
        store = registry(directory, trusted)
        d._approval_lock = paused
        result = store.record_outcome(authority_id=authority_id, approval_id=APPROVAL_ID,
            campaign_id=campaign_id, envelope_sha256=envelope, outcome="commit_confirmed")
        queue.put(result.state)
    except Rejected:
        queue.put("rejected")
    except Exception:
        queue.put("unexpected")
    finally:
        d._approval_lock = original


def test_uncertainty_publication_serializes_stale_outcome_after_failed_commit(
        monkeypatch, registry_directory, campaign, plan, approval, trusted, signing_key):
    store = registry(registry_directory, trusted)
    receipt = consume(store, campaign, plan, approval, sign(campaign, plan, approval, signing_key))
    context = multiprocessing.get_context("spawn")
    ready, resume, queue = context.Event(), context.Event(), context.Queue()
    worker = context.Process(target=_paused_outcome_worker, args=(registry_directory, trusted,
        campaign.campaign_id, approval.authority_id, receipt.envelope_sha256, ready, resume, queue))
    original = d._connect
    class FailedCommit:
        def __init__(self, connection): self.connection = connection
        def execute(self, *args): return self.connection.execute(*args)
        def commit(self): raise OSError(PRIVATE)
        def close(self): self.connection.close()
    try:
        worker.start()
        assert ready.wait(30)  # B has observed absence and cannot enter SQLite yet.
        with monkeypatch.context() as patch:
            patch.setattr(d, "_connect", lambda root: FailedCommit(original(root)))
            with pytest.raises(d.RegistryUncertain):
                store.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID,
                    campaign_id=campaign.campaign_id, envelope_sha256=receipt.envelope_sha256, outcome="uncertain")
        claim, uncertain = store._paths(approval.authority_id, APPROVAL_ID)
        assert d._present(uncertain) and d._present(claim)
        resume.set()  # A's failed transaction has closed; its quarantine survives.
        assert queue.get(timeout=30) == "rejected"
        worker.join(timeout=30)
        assert not worker.is_alive() and worker.exitcode == 0
        db = original(Path(registry_directory))
        try:
            assert db.execute("SELECT state FROM approvals").fetchall() == [("consumed",)]
            assert db.execute("SELECT state FROM history ORDER BY sequence").fetchall() == [("consumed",)]
        finally:
            db.close()
        for current in (store, registry(registry_directory, trusted)):
            assert current.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID).state == "uncertain"
            with pytest.raises(Rejected):
                current.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID,
                    campaign_id=campaign.campaign_id, envelope_sha256=receipt.envelope_sha256, outcome="commit_confirmed")
            with pytest.raises(Rejected):
                consume(current, campaign, plan, approval, sign(campaign, plan, approval, signing_key))
    finally:
        resume.set()
        if worker.pid is not None:
            if worker.is_alive(): worker.terminate()
            worker.join(timeout=30)
        queue.close(); queue.join_thread()


def _hold_approval_lock(directory, trusted, authority_id, held, release, queue):
    try:
        store = registry(directory, trusted)
        claim, _ = store._paths(authority_id, APPROVAL_ID)
        with d._approval_lock(claim):
            held.set()
            assert release.wait(30)
        queue.put("released")
    except Exception:
        queue.put("unexpected")


def test_approval_lock_contention_refuses_without_sqlite_or_mutation(
        monkeypatch, registry_directory, campaign, plan, approval, trusted, signing_key):
    store = registry(registry_directory, trusted)
    signed = sign(campaign, plan, approval, signing_key)
    receipt = consume(store, campaign, plan, approval, signed)
    context = multiprocessing.get_context("spawn")
    held, release, queue = context.Event(), context.Event(), context.Queue()
    worker = context.Process(target=_hold_approval_lock,
        args=(registry_directory, trusted, approval.authority_id, held, release, queue))
    try:
        worker.start()
        assert held.wait(30)
        with monkeypatch.context() as patch:
            connect = Mock(side_effect=AssertionError("SQLite must follow approval lock"))
            patch.setattr(d, "_connect", connect)
            with pytest.raises(Rejected): consume(store, campaign, plan, approval, signed)
            with pytest.raises(Rejected): store.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID)
            with pytest.raises(Rejected):
                store.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID,
                    campaign_id=campaign.campaign_id, envelope_sha256=receipt.envelope_sha256, outcome="commit_confirmed")
            connect.assert_not_called()
        release.set()
        assert queue.get(timeout=30) == "released"
        worker.join(timeout=30)
        assert not worker.is_alive() and worker.exitcode == 0
        assert store.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID).history == ("consumed",)
    finally:
        release.set()
        if worker.pid is not None:
            if worker.is_alive(): worker.terminate()
            worker.join(timeout=30)
        queue.close(); queue.join_thread()


def test_quarantine_read_error_is_not_absence(monkeypatch, registry_directory, campaign, plan, approval, trusted, signing_key):
    store = registry(registry_directory, trusted)
    receipt = consume(store, campaign, plan, approval, sign(campaign, plan, approval, signing_key))
    original = Path.stat
    def failed_stat(path, *args, **kwargs):
        if path.suffix == ".uncertain": raise PermissionError(PRIVATE)
        return original(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "stat", failed_stat)
        with pytest.raises(d.RegistryUncertain) as caught:
            store.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID,
                campaign_id=campaign.campaign_id, envelope_sha256=receipt.envelope_sha256, outcome="commit_confirmed")
        assert PRIVATE not in "".join(traceback.format_exception(caught.value))
    assert store.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID).state == "uncertain"


def _outcome_during_close_worker(directory, trusted, campaign_id, authority_id, envelope, start, done, queue):
    try:
        store = registry(directory, trusted)
        assert start.wait(30)
        result = store.record_outcome(authority_id=authority_id, approval_id=APPROVAL_ID,
            campaign_id=campaign_id, envelope_sha256=envelope, outcome="commit_confirmed")
        queue.put(result.state)
    except Rejected:
        queue.put("rejected")
    except Exception:
        queue.put("unexpected")
    finally:
        done.set()


def _stored_states(directory):
    db = d._connect(Path(directory))
    try:
        return (db.execute("SELECT state FROM approvals").fetchall(),
                db.execute("SELECT state FROM history ORDER BY sequence").fetchall())
    finally:
        db.close()


@pytest.mark.parametrize("close_first", [False, True])
@pytest.mark.parametrize("transaction_uncertain", [False, True])
def test_lock_close_failure_racing_outcome_never_publishes_after_release(
        monkeypatch, registry_directory, campaign, plan, approval, trusted, signing_key,
        close_first, transaction_uncertain):
    store = registry(registry_directory, trusted)
    signed = sign(campaign, plan, approval, signing_key)
    envelope = d.ApprovalVerifier(trusted_keys=(trusted,), replay_registry=d.MemoryReplayRegistry()).verify(
        campaign, plan, approval, signed, expected_initial_state_sha256="f" * 64, now=NOW).envelope_sha256
    claim, uncertain = store._paths(approval.authority_id, APPROVAL_ID)
    context = multiprocessing.get_context("spawn")
    start, done, queue = context.Event(), context.Event(), context.Queue()
    worker = context.Process(target=_outcome_during_close_worker, args=(registry_directory, trusted,
        campaign.campaign_id, approval.authority_id, envelope, start, done, queue))
    real_open, real_close, real_connect = d.os.open, d.os.close, d._connect
    descriptor = None
    injected = False
    quarantines = []
    real_publish = d._publish_uncertainty
    def publish(marker):
        assert not injected, "Quarantine must precede release/close attempt"
        quarantines.append(marker)
        real_publish(marker)
    def opened(path, *args, **kwargs):
        nonlocal descriptor
        fd = real_open(path, *args, **kwargs)
        if Path(path) == claim.with_suffix(".lock"): descriptor = fd
        return fd
    def failed_close(fd):
        nonlocal injected
        if fd != descriptor: return real_close(fd)
        assert not injected, "An ambiguous descriptor must never be retried"
        injected = True
        if close_first: real_close(fd)  # Model failure AFTER effective release.
        start.set()
        assert done.wait(30)  # B finishes while A's close is still unresolved.
        raise OSError(PRIVATE)
    class FailedCommit:
        def __init__(self, connection): self.connection = connection
        def execute(self, *args): return self.connection.execute(*args)
        def commit(self): raise OSError(PRIVATE)
        def close(self): self.connection.close()
    try:
        worker.start()
        with monkeypatch.context() as patch:
            patch.setattr(d.os, "open", opened)
            patch.setattr(d.os, "close", failed_close)
            patch.setattr(d, "_publish_uncertainty", publish)
            if transaction_uncertain:
                patch.setattr(d, "_connect", lambda root: FailedCommit(real_connect(root)))
            with pytest.raises(d.RegistryCleanupError) as caught:
                consume(store, campaign, plan, approval, signed)
            assert caught.value.phase == "lock_close"
            assert caught.value.commit_status == ("uncertain" if transaction_uncertain else "not_assessed")
            assert PRIVATE not in "".join(traceback.format_exception(caught.value))
        # Only the fixture releases a deliberately leaked test descriptor.
        if not close_first:
            real_close(descriptor)
            descriptor = None
        expected = "rejected" if transaction_uncertain or not close_first else "commit_confirmed"
        assert queue.get(timeout=30) == expected
        worker.join(timeout=30)
        assert not worker.is_alive() and worker.exitcode == 0
        assert d._present(claim)
        if transaction_uncertain:
            assert quarantines == [uncertain] and d._present(uncertain)
            assert _stored_states(registry_directory) == ([], [])
        else:
            assert quarantines == [] and not d._present(uncertain)
            history = [("consumed",)] + ([("commit_confirmed",)] if close_first else [])
            assert _stored_states(registry_directory) == ([history[-1]], history)
        restarted = registry(registry_directory, trusted)
        assert restarted.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID).state == (
            "uncertain" if transaction_uncertain else expected if close_first else "consumed")
        with pytest.raises(Rejected): consume(restarted, campaign, plan, approval, signed)
        if transaction_uncertain:
            with pytest.raises(Rejected):
                restarted.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID,
                    campaign_id=campaign.campaign_id, envelope_sha256=envelope, outcome="commit_confirmed")
    finally:
        start.set()
        if worker.pid is not None:
            if worker.is_alive(): worker.terminate()
            worker.join(timeout=30)
        if descriptor is not None and injected and not close_first: real_close(descriptor)
        queue.close(); queue.join_thread()


@pytest.mark.parametrize("operation", ["consume", "outcome"])
@pytest.mark.parametrize("stage", ["before_commit", "ack_before_commit", "ack_after_commit", "confirmed"])
def test_sqlite_close_error_preserves_commit_knowledge_and_history(
        monkeypatch, registry_directory, campaign, plan, approval, trusted, signing_key, operation, stage):
    store = registry(registry_directory, trusted)
    signed = sign(campaign, plan, approval, signing_key)
    receipt = consume(store, campaign, plan, approval, signed) if operation == "outcome" else None
    original = d._connect
    class FailedClose:
        def __init__(self, connection): self.connection = connection
        def execute(self, query, *args):
            if stage == "before_commit" and query.startswith("INSERT INTO history"):
                raise OSError(PRIVATE)
            return self.connection.execute(query, *args)
        def commit(self):
            if stage == "ack_before_commit": raise OSError(PRIVATE)
            self.connection.commit()
            if stage == "ack_after_commit": raise OSError(PRIVATE)
        def close(self):
            self.connection.close()
            raise OSError(PRIVATE)
    with monkeypatch.context() as patch:
        patch.setattr(d, "_connect", lambda root: FailedClose(original(root)))
        with pytest.raises(d.RegistryCleanupError) as caught:
            if operation == "consume": consume(store, campaign, plan, approval, signed)
            else:
                store.record_outcome(authority_id=approval.authority_id, approval_id=APPROVAL_ID,
                    campaign_id=campaign.campaign_id, envelope_sha256=receipt.envelope_sha256, outcome="commit_confirmed")
        assert caught.value.phase == "sqlite_close"
        assert caught.value.commit_status == ("not_attempted" if stage == "before_commit" else
            "confirmed" if stage == "confirmed" else "uncertain")
        assert PRIVATE not in "".join(traceback.format_exception(caught.value))
    committed = stage in ("ack_after_commit", "confirmed")
    history = [("consumed",)] if operation == "outcome" or committed else []
    if operation == "outcome" and committed: history.append(("commit_confirmed",))
    assert _stored_states(registry_directory) == ([history[-1]] if history else [], history)
    claim, uncertain = store._paths(approval.authority_id, APPROVAL_ID)
    assert d._present(claim) and d._present(uncertain) == (stage != "confirmed")
    restarted = registry(registry_directory, trusted)
    report = restarted.inspect(authority_id=approval.authority_id, approval_id=APPROVAL_ID)
    assert report.state == (history[-1][0] if stage == "confirmed" else "uncertain")
    with pytest.raises(Rejected): consume(restarted, campaign, plan, approval, signed)
    with pytest.raises(ExecutionDisabled): v.request_execution(report)
