"""Offline safety contracts: every observation below is synthetic and injected."""

import ast
import builtins
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path
import socket
import subprocess
import threading
import traceback

import pytest

import oidc_postgres_support as support


CAMPAIGN = "00000000-0000-4000-8000-000000000001"
SUFFIX = "00000000000040008000000000000001"
SENSITIVE = "postgresql://user:PRIVATE_MARKER@private.example/secret-path"


def contract_values():
    return dict(
        campaign_id=CAMPAIGN,
        container_id="a" * 64,
        container_name=f"oidc-tx-{SUFFIX}-postgres",
        image_ref="docker.io/library/postgres@sha256:" + "c" * 64,
        image_id="sha256:" + "d" * 64,
        platform="linux/amd64",
        network_id="b" * 64,
        network_name=f"oidc-tx-{SUFFIX}-net",
        subnet="172.30.91.0/24",
        gateway="172.30.91.1",
        storage_kind="tmpfs",
        storage_target="/var/lib/postgresql/data",
        storage_bytes=268435456,
        host="127.0.0.1",
        port=56439,
        database=f"oidct_{SUFFIX}",
        preparation_role=f"oidct_{SUFFIX}_owner",
        application_role=f"oidct_{SUFFIX}_app",
        observation_role=f"oidct_{SUFFIX}_observer",
        transport="verify-full",
        ca_sha256="e" * 64,
        server_address="172.30.91.2",
        server_port=5432,
        server_version_num=170010,
        cluster_name=f"oidc-test-{SUFFIX}",
        scope="public.oidc_transactions",
    )


def inventory_values():
    # Independent observed data: never copy, serialize or replace the contract.
    return dict(
        campaign_id="00000000-0000-4000-8000-000000000001",
        container_id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        container_name="oidc-tx-00000000000040008000000000000001-postgres",
        image_ref="docker.io/library/postgres@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        image_id="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        platform="linux/amd64",
        network_id="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        network_name="oidc-tx-00000000000040008000000000000001-net",
        subnet="172.30.91.0/24",
        gateway="172.30.91.1",
        network_internal=True,
        network_members=("a" * 64,),
        container_networks=("b" * 64,),
        mounts=(("tmpfs", "/var/lib/postgresql/data", 268435456, True),),
        published_ports=(("127.0.0.1", 56439, 5432, "tcp"),),
        state="running",
        restart_policy="no",
        privileged=False,
    )


def observation_values():
    # SQL and client facts are independently specified, including three sessions.
    result = []
    for kind, role, pid in (
        ("preparation", "oidct_00000000000040008000000000000001_owner", 301),
        ("application", "oidct_00000000000040008000000000000001_app", 302),
        ("observation", "oidct_00000000000040008000000000000001_observer", 303),
    ):
        result.append(dict(
            campaign_id="00000000-0000-4000-8000-000000000001",
            role_kind=kind,
            database="oidct_00000000000040008000000000000001",
            session_user=role,
            current_user=role,
            server_address="172.30.91.2",
            server_port=5432,
            server_version_num=170010,
            cluster_name="oidc-test-00000000000040008000000000000001",
            backend_pid=pid,
            tls_in_use=True,
            client_verification="verify-full",
            client_ca_sha256="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
            client_verified_host="127.0.0.1",
            superuser=False,
            create_database=False,
            create_role=False,
            scope="public.oidc_transactions",
        ))
    return result


def contract():
    return support.campaign_contract(**contract_values())


def inventory():
    return support.docker_inventory(**inventory_values())


def observations():
    return tuple(support.sql_observation(**item) for item in observation_values())


@pytest.fixture(autouse=True)
def prohibit_external_operations(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("external operation")
        raise AssertionError("External operation forbidden in offline campaign")

    for target, name in (
        (socket.socket, "connect"), (socket.socket, "connect_ex"),
        (socket, "create_connection"), (socket, "getaddrinfo"),
        (subprocess, "Popen"), (subprocess, "run"), (threading.Thread, "start"),
    ):
        monkeypatch.setattr(target, name, forbidden)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {
            "app", "sqlalchemy", "psycopg", "psycopg2", "docker", "alembic",
            "dotenv", "pydantic_settings",
        }:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    yield
    # Rejections must not hide an attempted operation swallowed by sanitization.
    assert attempts == []


def assert_rejected(operation):
    with pytest.raises(support.CampaignRejected) as caught:
        operation()
    error = caught.value
    assert str(error) == "OIDC test campaign data rejected"
    assert SENSITIVE not in str(error) + repr(error)
    assert error.__context__ is None
    assert error.__cause__ is None
    assert error.__suppress_context__ is True


def test_complete_contract_and_independent_evidence_are_inert():
    campaign = contract()
    syntax = support.validate_contract(campaign)
    match = support.compare_evidence(campaign, inventory(), observations())
    assert syntax.stage == "syntax_only"
    assert match.stage == "injected_evidence_only"
    assert syntax.campaign_id == match.campaign_id == CAMPAIGN
    for item in (campaign, inventory(), *observations(), syntax, match):
        assert item.execution_authorized is False
        with pytest.raises(support.ExecutionDisabled):
            bool(item)
        assert repr(item) == f"<{type(item).__name__}: inert>"
        with pytest.raises(FrozenInstanceError):
            item.campaign_id = "changed"


@pytest.mark.parametrize("factory,values", [
    (support.campaign_contract, contract_values),
    (support.docker_inventory, inventory_values),
    (support.sql_observation, lambda: observation_values()[0]),
])
def test_every_field_is_mandatory_and_unknown_fields_are_rejected(factory, values):
    for name in values():
        data = values()
        del data[name]
        assert_rejected(lambda: factory(**data))
    data = values()
    data["password"] = SENSITIVE
    assert_rejected(lambda: factory(**data))


@pytest.mark.parametrize("field,value", [
    ("campaign_id", ""), ("campaign_id", "00000000-0000-0000-0000-000000000000"),
    ("campaign_id", "00000000000040008000000000000001"),
    ("container_id", "a" * 12), ("container_id", "0" * 64),
    ("container_name", "oidc-tx-other-postgres"), ("container_id", "b" * 64),
    ("network_id", "implicit"), ("network_name", "development"),
    ("image_ref", "postgres:17"), ("image_ref", SENSITIVE),
    ("image_id", "sha256:missing"), ("platform", "windows/amd64"),
    ("host", "localhost"), ("host", ""), ("host", "/var/run/postgresql"),
    ("host", "192.168.1.12"), ("host", "0.0.0.0"), ("host", "::"),
    ("host", "postgresql://127.0.0.1"),
    ("port", 5433), ("port", 5434), ("port", 55432),
    ("port", "56439"), ("port", True), ("port", 0), ("port", 65536),
    ("database", "postgres"), ("database", "oidct_other"),
    ("preparation_role", "postgres"), ("application_role", "postgres"),
    ("observation_role", f"oidct_{SUFFIX}_app"),
    ("transport", ""), ("transport", "prefer"), ("transport", "require"),
    ("ca_sha256", "missing"), ("server_address", "172.30.91.1"),
    ("server_address", "172.30.92.2"), ("server_address", "172.30.91.255"),
    ("subnet", "127.0.0.0/24"), ("subnet", "172.30.91.1/24"),
    ("subnet", "172.30.0.0/16"), ("gateway", "172.30.91.0"),
    ("server_port", 5433), ("server_version_num", 180000),
    ("server_version_num", 169999), ("cluster_name", "default"),
    ("storage_kind", "volume"), ("storage_kind", "bind"),
    ("storage_target", "/production"), ("storage_bytes", 0),
    ("storage_bytes", 2 * 1024**3), ("scope", "public.users"),
    ("scope", "public.*"), ("scope", "oidc_transactions"),
])
def test_invalid_contract_is_rejected(field, value):
    values = contract_values()
    values[field] = value
    assert_rejected(lambda: support.campaign_contract(**values))


def test_explicit_ipv6_loopback_contract_requires_matching_observation():
    values = contract_values()
    values["host"] = "::1"
    campaign = support.campaign_contract(**values)
    assert_rejected(lambda: support.compare_evidence(campaign, inventory(), observations()))


@pytest.mark.parametrize("field,value", [
    ("campaign_id", "00000000-0000-4000-8000-000000000002"),
    ("container_id", "f" * 64), ("container_name", "oidc-tx-prefix-only"),
    ("image_ref", "docker.io/library/postgres@sha256:" + "f" * 64),
    ("image_id", "sha256:" + "f" * 64), ("platform", "linux/arm64"),
    ("network_id", "f" * 64), ("network_name", "shared"),
    ("subnet", "172.30.92.0/24"), ("gateway", "172.30.91.3"),
    ("network_internal", False), ("network_members", ("a" * 64, "f" * 64)),
    ("network_members", ()), ("container_networks", ("b" * 64, "f" * 64)),
    ("mounts", ()),
    ("mounts", (("bind", "/var/lib/postgresql/data", 268435456, True),)),
    ("mounts", (("tmpfs", "/var/lib/postgresql/data", 268435456, False),)),
    ("mounts", (("tmpfs", "/var/lib/postgresql/data", 268435456, True),
                ("bind", "/unexpected", 1, True))),
    ("mounts", (("tmpfs", "/other", 268435456, True),)),
    ("mounts", (("tmpfs", "/var/lib/postgresql/data", 134217728, True),)),
    ("published_ports", (("0.0.0.0", 56439, 5432, "tcp"),)),
    ("published_ports", (("127.0.0.1", 5433, 5432, "tcp"),)),
    ("published_ports", (("127.0.0.1", 56439, 5433, "tcp"),)),
    ("published_ports", (("127.0.0.1", 56439, 5432, "udp"),)),
    ("published_ports", ()), ("state", "exited"),
    ("restart_policy", "always"), ("privileged", True),
])
def test_divergent_docker_inventory_fails(field, value):
    data = inventory_values()
    data[field] = value
    observed = support.docker_inventory(**data)
    assert_rejected(lambda: support.compare_evidence(contract(), observed, observations()))


@pytest.mark.parametrize("field,value", [
    ("campaign_id", "another-campaign"), ("role_kind", "administrator"),
    ("database", "postgres"), ("session_user", "postgres"),
    ("current_user", "other_role"), ("server_address", "172.30.91.3"),
    ("server_port", 5433), ("server_version_num", 170009),
    ("cluster_name", "default"), ("tls_in_use", False),
    ("client_verification", "require"), ("client_ca_sha256", "f" * 64),
    ("client_verified_host", "localhost"), ("superuser", True),
    ("create_database", True), ("create_role", True), ("scope", "public.users"),
])
@pytest.mark.parametrize("index", [0, 1, 2])
def test_each_sql_actor_is_checked(field, value, index):
    data = observation_values()
    data[index][field] = value
    observed = tuple(support.sql_observation(**item) for item in data)
    assert_rejected(lambda: support.compare_evidence(contract(), inventory(), observed))


@pytest.mark.parametrize("variant", ["none", "missing", "duplicate_role", "duplicate_pid", "list"])
def test_sql_observations_must_be_complete_and_independent(variant):
    observed = observations()
    if variant == "none":
        observed = None
    elif variant == "missing":
        observed = observed[:2]
    elif variant == "duplicate_role":
        observed = (observed[0], observed[0], observed[2])
    elif variant == "duplicate_pid":
        observed = (observed[0], replace(observed[1], backend_pid=301), observed[2])
    else:
        observed = list(observed)
    assert_rejected(lambda: support.compare_evidence(contract(), inventory(), observed))


@pytest.mark.parametrize("factory,data", [
    (support.docker_inventory, lambda: dict(inventory_values(), mounts=(["tmpfs", "x", 1, True],))),
    (support.docker_inventory, lambda: dict(inventory_values(), network_members=["a" * 64])),
    (support.docker_inventory, lambda: dict(inventory_values(), mounts=(("tmpfs", "x", True, True),))),
    (support.docker_inventory, lambda: dict(inventory_values(), published_ports=(("127.0.0.1", True, 5432, "tcp"),))),
    (support.sql_observation, lambda: dict(observation_values()[0], backend_pid=0)),
    (support.sql_observation, lambda: dict(observation_values()[0], tls_in_use=1)),
])
def test_typed_observations_reject_mutability_and_coercion(factory, data):
    assert_rejected(lambda: factory(**data()))


def test_frozen_constructor_and_tampering_cannot_skip_revalidation():
    invalid = replace(contract(), host="remote.example")
    assert_rejected(lambda: support.validate_contract(invalid))
    assert_rejected(lambda: support.compare_evidence(invalid, inventory(), observations()))
    invalid_inventory = replace(inventory(), mounts=(["tmpfs", "x", 1, True],))
    assert_rejected(lambda: support.compare_evidence(contract(), invalid_inventory, observations()))
    invalid_sql = (replace(observations()[0], backend_pid=True), *observations()[1:])
    assert_rejected(lambda: support.compare_evidence(contract(), inventory(), invalid_sql))


@pytest.mark.parametrize("candidate", [True, False, None, {"authorized": True}, "ALLOW_POSTGRES=1"])
def test_no_caller_flag_grants_operational_authority(candidate, monkeypatch):
    monkeypatch.setenv("ALLOW_POSTGRES", "1")
    monkeypatch.setenv("PGHOST", "production.example")
    with pytest.raises(support.ExecutionDisabled, match="authority is unavailable"):
        support.require_operational_authority(candidate)


def test_validation_and_matching_do_not_grant_authority():
    for candidate in (contract(), support.validate_contract(contract()),
                      support.compare_evidence(contract(), inventory(), observations())):
        with pytest.raises(support.ExecutionDisabled):
            support.require_operational_authority(candidate)


def test_secret_values_and_sensitive_object_exceptions_are_not_exposed():
    class Sensitive:
        def __repr__(self):
            raise RuntimeError(SENSITIVE)

        def __str__(self):
            raise RuntimeError(SENSITIVE)

    for value in (SENSITIVE, Sensitive()):
        assert_rejected(lambda: support.campaign_contract(**dict(contract_values(), host=value)))
    assert_rejected(lambda: support.validate_contract(Sensitive()))
    assert_rejected(lambda: support.compare_evidence(contract(), Sensitive(), observations()))
    invalid = replace(contract(), host=SENSITIVE)
    assert SENSITIVE not in repr(invalid)
    assert SENSITIVE not in repr(replace(observations()[0], session_user=SENSITIVE))


def test_underlying_validation_exception_is_discarded(monkeypatch):
    def sensitive_failure(_value):
        raise RuntimeError(SENSITIVE)

    monkeypatch.setattr(support, "UUID", sensitive_failure)
    assert_rejected(lambda: support.campaign_contract(**contract_values()))
    assert_rejected(lambda: support.validate_contract(contract_without_factory()))


def contract_without_factory():
    return support.CampaignContract(**contract_values())


def test_synthetic_ids_are_deterministic_distinct_and_campaign_bound():
    ids = support.synthetic_oidc_ids(contract(), "consume_race")
    assert ids == support.synthetic_oidc_ids(contract(), "consume_race")
    assert ids != support.synthetic_oidc_ids(contract(), "expiry")
    digests = [getattr(ids, field.name) for field in fields(ids)]
    assert len(set(digests)) == 4
    assert all(len(value) == 64 for value in digests)
    other_values = {name: value.replace(SUFFIX, "00000000000040008000000000000002")
                    if type(value) is str else value for name, value in contract_values().items()}
    other_values["campaign_id"] = "00000000-0000-4000-8000-000000000002"
    assert ids != support.synthetic_oidc_ids(support.campaign_contract(**other_values), "consume_race")
    assert_rejected(lambda: support.synthetic_oidc_ids(contract(), SENSITIVE))


def test_fixture_registry_and_cleanup_are_pure_bounded_descriptions():
    campaign = contract()
    resources = support.campaign_resources(campaign)
    ids = support.synthetic_oidc_ids(campaign, "consume")
    row = support.RowRef(CAMPAIGN, "public.oidc_transactions", ids.transaction_id)
    registry = support.created_registry(campaign, resources, (row,))
    cleanup = support.describe_cleanup(campaign, registry, resources[:1], (row,))
    assert cleanup.resources == resources[:1] and cleanup.rows == (row,)
    assert cleanup.execution_authorized is False
    assert len(resources) == 4
    assert resources[3].kind == "table" and resources[3].identity == "public.oidc_transactions"
    assert resources[2].identity == "a" * 64 + ":/var/lib/postgresql/data"
    with pytest.raises(FrozenInstanceError):
        registry.rows = ()


@pytest.mark.parametrize("variant", [
    "unregistered_resource", "unregistered_row", "foreign_id", "foreign_campaign",
    "foreign_table", "duplicate", "mutable", "wrong_registry", "wildcard_row",
])
def test_registry_rejects_unbounded_cleanup(variant):
    campaign = contract()
    resources = support.campaign_resources(campaign)
    row = support.RowRef(CAMPAIGN, "public.oidc_transactions", "f" * 64)
    registry = support.created_registry(campaign, (), ())
    wanted_resources, wanted_rows = (), ()
    if variant == "unregistered_resource":
        wanted_resources = resources[:1]
    elif variant == "unregistered_row":
        wanted_rows = (row,)
    elif variant == "foreign_id":
        wanted_resources = (replace(resources[0], identity="f" * 64),)
    elif variant == "foreign_campaign":
        wanted_resources = (replace(resources[0], campaign_id="other"),)
    elif variant == "foreign_table":
        wanted_rows = (replace(row, table="public.users"),)
    elif variant == "duplicate":
        wanted_resources = (resources[0], resources[0])
    elif variant == "mutable":
        wanted_resources = list(resources)
    elif variant == "wrong_registry":
        registry = replace(registry, campaign_id="other")
    else:
        wanted_rows = (replace(row, transaction_id="*"),)
    assert_rejected(lambda: support.describe_cleanup(campaign, registry, wanted_resources, wanted_rows))


def actors():
    return support.describe_actors(contract(), (
        ("winner", "application", "connection_one"),
        ("waiter", "application", "connection_two"),
        ("observer", "observation", "connection_three"),
    ))


def test_independent_actors_and_injected_lock_wait_events():
    first, second, observer = actors()
    assert first.sql_role == second.sql_role
    assert len({item.connection_id for item in (first, second, observer)}) == 3
    locked = support.concurrency_event(first, 401, 0, "lock_acquired")
    requested = support.concurrency_event(second, 402, 0, "lock_requested")
    condition = support.lock_wait_condition(locked, requested, (401,), "Lock")
    assert condition.blocker_pid == 401 and condition.waiter_pid == 402
    assert condition.execution_authorized is False
    for name in ("clock_sampled", "delete_returned", "commit_acknowledged", "session_closed"):
        assert support.concurrency_event(first, 401, 1, name).event == name


@pytest.mark.parametrize("specifications", [
    (), (("same", "application", "one"), ("same", "application", "two")),
    (("one", "application", "same"), ("two", "application", "same")),
    (("one", "administrator", "one"), ("two", "application", "two")),
    (("one", "application", SENSITIVE), ("two", "application", "two")),
])
def test_actor_descriptions_reject_shared_connections_and_invalid_roles(specifications):
    assert_rejected(lambda: support.describe_actors(contract(), specifications))


@pytest.mark.parametrize("variant", ["same_actor", "same_pid", "wrong_campaign", "not_locked", "not_waiting", "no_blocker", "wrong_wait", "bool_pid"])
def test_lock_wait_conditions_reject_insufficient_evidence(variant):
    first, second, _ = actors()
    blocker = support.concurrency_event(first, 401, 0, "lock_acquired")
    waiter = support.concurrency_event(second, 402, 0, "lock_requested")
    pids, event_type = (401,), "Lock"
    if variant == "same_actor":
        waiter = replace(waiter, actor_id=blocker.actor_id)
    elif variant == "same_pid":
        waiter = replace(waiter, backend_pid=401)
    elif variant == "wrong_campaign":
        waiter = replace(waiter, campaign_id="00000000-0000-4000-8000-000000000002")
    elif variant == "not_locked":
        blocker = replace(blocker, event="lock_requested")
    elif variant == "not_waiting":
        waiter = replace(waiter, event="clock_sampled")
    elif variant == "no_blocker":
        pids = ()
    elif variant == "wrong_wait":
        event_type = "Client"
    else:
        pids = (True,)
    assert_rejected(lambda: support.lock_wait_condition(blocker, waiter, pids, event_type))


def test_support_import_and_construction_have_no_external_dependencies(monkeypatch):
    source_path = Path(support.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    allowed = {"dataclasses", "functools", "hashlib", "ipaddress", "re", "uuid"}
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports.update(alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names)
    assert imports <= allowed
    assert not any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                   and node.func.id in {"open", "eval", "exec", "__import__"} for node in ast.walk(tree))

    # Fresh module execution under guards, without subprocesses or module cache reuse.
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("file operation")
        raise AssertionError("File or system operation forbidden")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    namespace = {"__name__": "oidc_support_fresh_import"}
    exec(compile(source, str(source_path), "exec"), namespace)
    fresh = namespace["campaign_contract"](**contract_values())
    assert namespace["validate_contract"](fresh).stage == "syntax_only"
    assert attempts == []


def test_supplied_mutable_mappings_are_not_retained():
    data = contract_values()
    campaign = support.campaign_contract(**data)
    data["host"] = SENSITIVE
    assert campaign.host == "127.0.0.1"
    observed_data = inventory_values()
    observed = support.docker_inventory(**observed_data)
    observed_data["network_members"] = ()
    assert observed.network_members == ("a" * 64,)


def test_libpq_and_authorization_environment_never_fill_missing_fields(monkeypatch):
    for name in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD", "ALLOW_POSTGRES"):
        monkeypatch.setenv(name, SENSITIVE)
    for field in ("host", "port", "database", "application_role", "transport"):
        values = contract_values()
        del values[field]
        assert_rejected(lambda: support.campaign_contract(**values))


@pytest.mark.parametrize("pid,sequence,event", [
    (True, 0, "lock_acquired"), (0, 0, "lock_acquired"),
    (401, -1, "lock_acquired"), (401, True, "lock_acquired"),
    (401, 0, SENSITIVE),
])
def test_concurrency_events_reject_invalid_values(pid, sequence, event):
    assert_rejected(lambda: support.concurrency_event(actors()[0], pid, sequence, event))


def test_errors_do_not_write_sensitive_data_to_logs_or_streams(caplog, capsys):
    assert_rejected(lambda: support.campaign_contract(**dict(contract_values(), host=SENSITIVE)))
    output = capsys.readouterr()
    assert output.out == output.err == ""
    assert caplog.records == []


def cleanup_entries(kind):
    if kind == "table":
        return (support.ResourceRef(CAMPAIGN, "table", "public.oidc_transactions"),), ()
    return (), (support.RowRef(CAMPAIGN, "public.oidc_transactions", "f" * 64),)


@pytest.mark.parametrize("kind", ["table", "row"])
def test_cleanup_registry_is_bound_to_exact_container_even_with_same_campaign(kind):
    first = contract()
    second = support.campaign_contract(**dict(contract_values(), container_id="f" * 64))
    assert first.campaign_id == second.campaign_id
    support.validate_contract(second)
    resources, rows = cleanup_entries(kind)
    registry = support.created_registry(first, resources, rows)
    assert_rejected(lambda: support.describe_cleanup(second, registry, resources, rows))


@pytest.mark.parametrize("kind", ["table", "row"])
@pytest.mark.parametrize("field,value", [
    ("container_id", "f" * 64),
    ("database", "other_database"),
    ("scope", "public.users"),
])
def test_cleanup_rejects_each_divergent_destination_field(kind, field, value):
    campaign = contract()
    resources, rows = cleanup_entries(kind)
    registry = support.created_registry(campaign, resources, rows)
    # Keep the contract valid: exercise the destination check itself, not just
    # the existing contract naming/scope rejection.
    altered = replace(registry, destination=replace(registry.destination, **{field: value}))
    assert_rejected(lambda: support.describe_cleanup(campaign, altered, resources, rows))


@pytest.mark.parametrize("kind", ["table", "row"])
@pytest.mark.parametrize("field,value", [
    ("database", "other_database"), ("scope", "public.users"),
])
def test_same_campaign_contract_with_other_database_or_scope_remains_invalid(kind, field, value):
    campaign = contract()
    resources, rows = cleanup_entries(kind)
    registry = support.created_registry(campaign, resources, rows)
    altered_contract = replace(campaign, **{field: value})
    assert altered_contract.campaign_id == registry.campaign_id
    # No weakening of the original database naming convention or table scope.
    assert_rejected(lambda: support.validate_contract(altered_contract))
    assert_rejected(lambda: support.describe_cleanup(altered_contract, registry, resources, rows))


@pytest.mark.parametrize("kind", ["table", "row"])
@pytest.mark.parametrize("variant", [
    "none", "missing_identity", "missing_field", "mapping", "invalid_id", "invalid_field_type",
])
def test_cleanup_fails_closed_for_missing_or_invalid_destination(kind, variant):
    campaign = contract()
    resources, rows = cleanup_entries(kind)
    registry = support.created_registry(campaign, resources, rows)
    if variant == "none":
        registry = replace(registry, destination=None)
    elif variant == "missing_identity":
        object.__delattr__(registry, "destination")
    elif variant == "missing_field":
        object.__delattr__(registry.destination, "database")
    elif variant == "mapping":
        registry = replace(registry, destination={
            "container_id": "a" * 64, "database": f"oidct_{SUFFIX}",
            "scope": "public.oidc_transactions",
        })
    elif variant == "invalid_id":
        registry = replace(registry, destination=replace(registry.destination, container_id=SENSITIVE))
    else:
        registry = replace(registry, destination=replace(registry.destination, database=[]))
    assert_rejected(lambda: support.describe_cleanup(campaign, registry, resources, rows))


@pytest.mark.parametrize("kind", ["table", "row"])
def test_nominal_cleanup_preserves_immutable_opaque_destination(kind):
    campaign = contract()
    resources, rows = cleanup_entries(kind)
    registry = support.created_registry(campaign, resources, rows)
    expected = support.DestinationIdentity("a" * 64, f"oidct_{SUFFIX}", "public.oidc_transactions")
    assert registry.destination == expected
    cleanup = support.describe_cleanup(campaign, registry, resources, rows)
    assert cleanup.destination == expected
    assert cleanup.resources == resources and cleanup.rows == rows
    assert repr(cleanup.destination) == "<DestinationIdentity: inert>"
    assert cleanup.execution_authorized is False
    for field in ("container_id", "database", "scope"):
        with pytest.raises(FrozenInstanceError):
            setattr(registry.destination, field, SENSITIVE)
    with pytest.raises(FrozenInstanceError):
        registry.destination = None
    with pytest.raises(FrozenInstanceError):
        cleanup.destination = None


def public_failure_operation(path):
    campaign = contract()
    syntax = support.validate_contract(campaign)
    matched = support.compare_evidence(campaign, inventory(), observations())
    registry = support.created_registry(campaign, (), ())
    cleanup = support.describe_cleanup(campaign, registry, (), ())
    first, second, _ = actors()
    blocker = support.concurrency_event(first, 401, 0, "lock_acquired")
    waiter = support.concurrency_event(second, 402, 0, "lock_requested")
    operations = {
        "campaign_factory": lambda: support.campaign_contract(),
        "docker_factory": lambda: support.docker_inventory(),
        "sql_factory": lambda: support.sql_observation(),
        "validation": lambda: support.validate_contract(None),
        "comparison_contract": lambda: support.compare_evidence(None, inventory(), observations()),
        "comparison_docker": lambda: support.compare_evidence(campaign, None, observations()),
        "comparison_sql": lambda: support.compare_evidence(campaign, inventory(), ()),
        "synthetic_ids": lambda: support.synthetic_oidc_ids(campaign, SENSITIVE),
        "resources": lambda: support.campaign_resources(None),
        "registry": lambda: support.created_registry(campaign, (), (None,)),
        "cleanup": lambda: support.describe_cleanup(campaign, replace(registry, destination=None), (), ()),
        "actors": lambda: support.describe_actors(campaign, ()),
        "event": lambda: support.concurrency_event(first, 0, 0, "lock_acquired"),
        "wait_condition": lambda: support.lock_wait_condition(blocker, waiter, (), "Lock"),
        "bool_contract": lambda: bool(campaign),
        "bool_validation": lambda: bool(syntax),
        "bool_concordance": lambda: bool(matched),
        "bool_cleanup": lambda: bool(cleanup),
        "authority_flag": lambda: support.require_operational_authority(True),
        "authority_contract": lambda: support.require_operational_authority(campaign),
        "authority_validation": lambda: support.require_operational_authority(syntax),
        "authority_concordance": lambda: support.require_operational_authority(matched),
    }
    return operations[path]


def assert_public_error_has_no_sensitive_chain(error, expected_type):
    assert type(error) is expected_type
    message = ("OIDC test campaign data rejected" if expected_type is support.CampaignRejected
               else "OIDC test operational authority is unavailable")
    assert str(error) == message
    assert repr(error) == f"{expected_type.__name__}({message!r})"
    assert error.__context__ is None
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
    rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert SENSITIVE not in rendered
    assert "RuntimeError:" not in rendered
    assert "ValueError:" not in rendered
    formatted = traceback.TracebackException.from_exception(error)
    assert formatted.__context__ is None and formatted.__cause__ is None
    assert formatted.__suppress_context__ is True


@pytest.mark.parametrize("path", [
    "campaign_factory", "docker_factory", "sql_factory", "validation",
    "comparison_contract", "comparison_docker", "comparison_sql", "synthetic_ids",
    "resources", "registry", "cleanup", "actors", "event", "wait_condition",
    "bool_contract", "bool_validation", "bool_concordance", "bool_cleanup",
    "authority_flag", "authority_contract", "authority_validation", "authority_concordance",
])
@pytest.mark.parametrize("outer_chain", ["context", "cause"])
def test_public_refusals_discard_active_caller_exception(path, outer_chain):
    operation = public_failure_operation(path)
    expected = (support.ExecutionDisabled if path.startswith(("bool_", "authority_"))
                else support.CampaignRejected)
    try:
        if outer_chain == "cause":
            raise RuntimeError(SENSITIVE) from ValueError(SENSITIVE)
        try:
            raise ValueError(SENSITIVE)
        except ValueError:
            raise RuntimeError(SENSITIVE)
    except RuntimeError as original:
        with pytest.raises(expected) as caught:
            operation()
        assert_public_error_has_no_sensitive_chain(caught.value, expected)
        # Protection of the public chain does not erase the caller's own error.
        assert str(original) == SENSITIVE
        assert (original.__cause__ if outer_chain == "cause" else original.__context__) is not None


@pytest.mark.parametrize("path", ["construction", "validation"])
def test_inner_sensitive_exception_and_active_outer_exception_are_both_detached(monkeypatch, path):
    campaign = contract()

    def sensitive_failure(_value):
        raise RuntimeError(SENSITIVE)

    monkeypatch.setattr(support, "UUID", sensitive_failure)
    operation = (lambda: support.campaign_contract(**contract_values()) if path == "construction"
                 else support.validate_contract(campaign))
    try:
        raise ValueError(SENSITIVE)
    except ValueError as original:
        with pytest.raises(support.CampaignRejected) as caught:
            operation()
        assert_public_error_has_no_sensitive_chain(caught.value, support.CampaignRejected)
        assert str(original) == SENSITIVE
