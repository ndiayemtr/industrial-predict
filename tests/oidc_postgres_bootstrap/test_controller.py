"""Simulations of authority/clock/evidence. Never prove real approval or identity."""

import ast
import builtins
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import socket
import subprocess
import threading
import traceback

import pytest

from oidc_postgres_support import campaign_contract
from oidc_postgres_bootstrap import controller as c


T0 = datetime(2030, 1, 1, tzinfo=timezone.utc)
N0 = 100_000_000_000
SESSION = "11111111-1111-4111-8111-111111111111"
COLLECTOR = "22222222-2222-4222-8222-222222222222"
ENGINE = "33333333-3333-4333-8333-333333333333"
CAMPAIGN = "00000000-0000-4000-8000-000000000001"
SUFFIX = "00000000000040008000000000000001"
MARKER = "SYNTHETIC_SENSITIVE_CONTROLLER_MARKER"
NAMES = ("bootstrap.sh", "controller.py", "openssl.cnf.in", "pg_hba.local.conf.in", "pg_hba.tls.conf.in",
         "postgresql.local.conf.in", "postgresql.tls.conf.in", "roles.sql.in", "validation.py")


@pytest.fixture(autouse=True)
def forbid_operations(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("operation")
        raise AssertionError("Operational effect forbidden")

    for target, name in ((subprocess, "Popen"), (subprocess, "run"), (socket.socket, "connect"),
                         (socket.socket, "connect_ex"), (socket, "create_connection"),
                         (socket, "getaddrinfo"), (threading.Thread, "start")):
        monkeypatch.setattr(target, name, forbidden)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"app", "sqlalchemy", "psycopg", "psycopg2", "docker", "alembic", "dotenv"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    yield
    assert attempts == []


def expected_campaign(new=False):
    return campaign_contract(
        campaign_id=CAMPAIGN, container_id=("f" if new else "a") * 64,
        container_name=f"oidc-tx-{SUFFIX}-postgres", image_ref="docker.io/library/postgres@sha256:" + "b" * 64,
        image_id="sha256:" + "c" * 64, platform="linux/amd64", network_id="d" * 64,
        network_name=f"oidc-tx-{SUFFIX}-net", subnet="172.30.91.0/28", gateway="172.30.91.1",
        storage_kind="tmpfs", storage_target="/var/lib/postgresql/data", storage_bytes=268435456,
        host="127.0.0.1", port=56439, database=f"oidct_{SUFFIX}",
        preparation_role=f"oidct_{SUFFIX}_owner", application_role=f"oidct_{SUFFIX}_app",
        observation_role=f"oidct_{SUFFIX}_observer", transport="verify-full", ca_sha256="e" * 64,
        server_address="172.30.91.2", server_port=5432, server_version_num=170010,
        cluster_name=f"oidc-test-{SUFFIX}", scope="public.oidc_transactions")


# Independently specified expected conditions and injected observations.
POLICIES = (
    (c.Operation.RECREATE, c.Phase.RECREATION_AUTHORIZED, "docker-inspector",
     (("state", "created"), ("started", "never"), ("network_members", "none"), ("artifacts", "reviewed")),
     (("state", "created"), ("entrypoint", "controlled"), ("mounts", "tmpfs_only"),
      ("ports", "loopback_only"), ("limits", "768m_1cpu"), ("restart", "no"))),
    (c.Operation.INSPECT_NEW, c.Phase.NEW_CONTAINER_INSPECTED, "docker-inspector",
     (("state", "created"), ("creation_receipt", "recorded")),
     (("identity", "exact_new_id"), ("configuration", "exact_manifest"), ("dev_p101", "unchanged"))),
    (c.Operation.BOOTSTRAP_LOCAL, c.Phase.LOCAL_BOOTSTRAP, "local-inspector",
     (("generation", "first"), ("pgdata", "empty"), ("tmpfs", "verified"), ("authority", "separate_phase")),
     (("version", "17.10"), ("auth", "scram-sha-256"), ("transport", "private_unix"),
      ("tcp", "absent"), ("roles", "restricted"), ("table_oidc", "absent"))),
    (c.Operation.CONFIGURE_TLS, c.Phase.TLS_CONFIGURATION, "tls-inspector",
     (("tcp", "absent"), ("roles", "restricted"), ("container", "same_generation")),
     (("tls", "verified"), ("san", "IP:127.0.0.1"), ("hba", "restricted"),
      ("bootstrap_login", "disabled"), ("container", "same_generation"))),
    (c.Operation.ATTEST_FINAL, c.Phase.FINAL_ATTESTATION, "sql-inspector",
     (("tls", "verified"), ("hba", "restricted")),
     (("sql_identity", "exact"), ("sessions", "three_independent_pids"), ("client", "verify-full"),
      ("source", "observed_expected"), ("privileges", "restricted"), ("table_oidc", "absent"))),
)


def contract_values():
    return dict(campaign=expected_campaign(), session_id=SESSION, collector_session_id=COLLECTOR,
                engine_id=ENGINE, git_revision="a" * 40,
                artifacts=tuple(c.ArtifactDigest(name, "c" * 64) for name in NAMES))


def approval_values(index=0, serial=None):
    serial = index + 1 if serial is None else serial
    operation, phase, _, before, after = POLICIES[index]
    return dict(approval_id=f"44444444-4444-4444-8444-{serial:012d}",
        external_reference=f"55555555-5555-4555-8555-{serial:012d}", provenance=c.Provenance.EXTERNAL_HUMAN_APPROVAL,
        controller_session_id=SESSION, campaign=expected_campaign(index > 0), engine_id=ENGINE,
        git_revision="a" * 40, artifacts=tuple(c.ArtifactDigest(name, "c" * 64) for name in NAMES),
        operations=(operation,), phases=(phase,), not_before=T0 - timedelta(seconds=1),
        expires_at=T0 + timedelta(seconds=60), preconditions=before, postconditions=after)


def approval(index=0, serial=None):
    return c.approval_contract(**approval_values(index, serial))


def observed_values(index=0, stage=c.EvidenceStage.BEFORE, at=T0, ns=N0):
    # These literal facts are not copied from an approval or ControllerContract.
    new = index > 0 or stage is c.EvidenceStage.AFTER
    observed_campaign = campaign_contract(
        campaign_id="00000000-0000-4000-8000-000000000001", container_id=("f" if new else "a") * 64,
        container_name="oidc-tx-00000000000040008000000000000001-postgres",
        image_ref="docker.io/library/postgres@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        image_id="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
        platform="linux/amd64", network_id="dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
        network_name="oidc-tx-00000000000040008000000000000001-net", subnet="172.30.91.0/28", gateway="172.30.91.1",
        storage_kind="tmpfs", storage_target="/var/lib/postgresql/data", storage_bytes=268435456,
        host="127.0.0.1", port=56439, database="oidct_00000000000040008000000000000001",
        preparation_role="oidct_00000000000040008000000000000001_owner",
        application_role="oidct_00000000000040008000000000000001_app",
        observation_role="oidct_00000000000040008000000000000001_observer", transport="verify-full",
        ca_sha256="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
        server_address="172.30.91.2", server_port=5432, server_version_num=170010,
        cluster_name="oidc-test-00000000000040008000000000000001", scope="public.oidc_transactions")
    _, phase, source, before, after = POLICIES[index]
    names = ("bootstrap.sh", "controller.py", "openssl.cnf.in", "pg_hba.local.conf.in", "pg_hba.tls.conf.in",
             "postgresql.local.conf.in", "postgresql.tls.conf.in", "roles.sql.in", "validation.py")
    return dict(declared_source=source, engine_id="33333333-3333-4333-8333-333333333333",
        campaign=observed_campaign, controller_session_id="11111111-1111-4111-8111-111111111111",
        collector_session_id="22222222-2222-4222-8222-222222222222", phase=phase, stage=stage,
        started_at=at, ended_at=at, started_ns=ns, ended_ns=ns, git_revision="a" * 40,
        artifacts=tuple(c.ArtifactDigest(name, "c" * 64) for name in names),
        observations=before if stage is c.EvidenceStage.BEFORE else after)


def evidence(index=0, stage=c.EvidenceStage.BEFORE, at=T0, ns=N0):
    return c.evidence_envelope(**observed_values(index, stage, at, ns))


class FakeClock(c.Clock):
    def __init__(self):
        self.current = c.ClockSample(T0, N0)

    def sample(self):
        return self.current


class FakeAuthority(c.ApprovalAuthority):
    def authenticate(self, supplied):
        # Test assertion only: no cryptographic/administrative proof exists here.
        return c.AuthorityVerdict(c.AuthorityDecision.ATTESTED, supplied.approval_id,
            supplied.external_reference, supplied.provenance, supplied.controller_session_id,
            c.approval_fingerprint(supplied))


def controller():
    clock = FakeClock()
    return c.Controller(c.controller_contract(**contract_values()), clock), clock


def rejected(operation):
    with pytest.raises(c.ControlRejected) as caught:
        operation()
    error = caught.value
    assert str(error) == "OIDC offline control data rejected"
    assert error.__context__ is None and error.__cause__ is None and error.__suppress_context__ is True
    assert MARKER not in str(error) + repr(error) + "".join(traceback.format_exception(error))


def advance(control, index):
    grant = approval(index)
    decision = control.request(grant, FakeAuthority(), evidence(index))
    assert decision.kind is c.ResultKind.DESCRIBED
    assert decision.execution_authorized is False and decision.action.execution_authorized is False
    assert control.record(grant.approval_id, c.ResultKind.SUCCESS,
                          evidence(index, c.EvidenceStage.AFTER)).kind is c.ResultKind.SUCCESS


def test_complete_nominal_lifecycle_has_only_inert_descriptions():
    control, _ = controller()
    for index in range(5):
        advance(control, index)
    assert control.state.lifecycle is c.Lifecycle.COMPLETE
    assert control.state.phase is c.Phase.FINAL_ATTESTATION
    assert control.state.container_id == "f" * 64
    assert len(control.state.used_approvals) == 5
    assert control.request(approval(4), FakeAuthority(), evidence(4)).kind is c.ResultKind.REFUSED
    with pytest.raises(FrozenInstanceError):
        control.state.container_id = "b" * 64
    for item in (control, control.state, approval(), evidence()):
        assert "offline" in repr(item) and item.execution_authorized is False
        rejected(lambda: bool(item))


@pytest.mark.parametrize("factory,values", [(c.controller_contract, contract_values),
    (c.approval_contract, approval_values), (c.evidence_envelope, observed_values)])
def test_missing_unknown_and_malformed_fields_are_rejected(factory, values):
    for name in values():
        data = values()
        del data[name]
        rejected(lambda: factory(**data))
    rejected(lambda: factory(**dict(values(), approved=True)))


@pytest.mark.parametrize("field,value", [
    ("approval_id", MARKER), ("external_reference", "https://private.invalid"),
    ("provenance", True), ("operations", ()), ("operations", (c.Operation.RECREATE, c.Operation.INSPECT_NEW)),
    ("phases", (c.Phase.LOCAL_BOOTSTRAP,)), ("preconditions", (("exit_code", "0"),)),
    ("postconditions", ()), ("not_before", T0.replace(tzinfo=None)),
    ("expires_at", T0 - timedelta(seconds=2)), ("expires_at", T0 + timedelta(minutes=11)),
])
def test_approval_contract_is_narrow_closed_and_typed(field, value):
    rejected(lambda: c.approval_contract(**dict(approval_values(), **{field: value})))


@pytest.mark.parametrize("authority", [None, True, False, object(), c.AuthorityDecision.ATTESTED])
def test_absent_authority_or_flags_are_never_approval(authority):
    control, _ = controller()
    assert control.request(approval(), authority, evidence()).kind is c.ResultKind.REFUSED
    assert control.state.lifecycle is c.Lifecycle.READY


@pytest.mark.parametrize("field,value", [
    ("decision", c.AuthorityDecision.UNATTESTED), ("decision", c.AuthorityDecision.REFUSED),
    ("decision", True), ("approval_id", "different"), ("external_reference", "different"),
    ("controller_session_id", "different"), ("approval_digest", "b" * 64), ("provenance", "human"),
])
def test_authority_verdict_must_bind_the_exact_approval(field, value):
    class DivergentAuthority(FakeAuthority):
        def authenticate(self, supplied):
            return replace(super().authenticate(supplied), **{field: value})

    control, _ = controller()
    assert control.request(approval(), DivergentAuthority(), evidence()).kind is c.ResultKind.REFUSED


@pytest.mark.parametrize("field,value", [
    ("controller_session_id", COLLECTOR), ("engine_id", COLLECTOR), ("git_revision", "b" * 40),
])
def test_approval_scope_must_match_controller(field, value):
    control, _ = controller()
    changed = replace(approval(), **{field: value})
    assert control.request(changed, FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED


@pytest.mark.parametrize("field,value", [("container_id", "b" * 64), ("network_id", "b" * 64),
    ("ca_sha256", "b" * 64), ("database", "other"), ("image_id", "sha256:" + "b" * 64)])
def test_campaign_or_destination_divergence_is_refused(field, value):
    control, _ = controller()
    changed = replace(approval(), campaign=replace(expected_campaign(), **{field: value}))
    assert control.request(changed, FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED


@pytest.mark.parametrize("field,value", [
    ("declared_source", "sql-inspector"), ("engine_id", COLLECTOR), ("controller_session_id", COLLECTOR),
    ("collector_session_id", SESSION), ("phase", c.Phase.LOCAL_BOOTSTRAP),
    ("stage", c.EvidenceStage.AFTER), ("git_revision", "b" * 40),
    ("observations", (("state", "created"),)), ("started_ns", True),
])
def test_independent_evidence_detects_missing_or_divergent_facts(field, value):
    control, _ = controller()
    proof = replace(evidence(), **{field: value})
    assert control.request(approval(), FakeAuthority(), proof).kind is c.ResultKind.REFUSED
    # Authenticated reference consumed before considering the supplied facts.
    assert control.state.used_approvals == (approval().approval_id,)
    assert control.request(approval(), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED


def test_artifact_fingerprints_and_required_set_are_exact():
    control, _ = controller()
    changed = replace(approval(), artifacts=(replace(approval().artifacts[0], sha256="b" * 64), *approval().artifacts[1:]))
    assert control.request(changed, FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    rejected(lambda: c.controller_contract(**dict(contract_values(), artifacts=())))
    rejected(lambda: c.controller_contract(**dict(contract_values(), artifacts=contract_values()["artifacts"][:-1])))
    control, _ = controller()
    proof = replace(evidence(), artifacts=(replace(evidence().artifacts[0], sha256="b" * 64), *evidence().artifacts[1:]))
    assert control.request(approval(), FakeAuthority(), proof).kind is c.ResultKind.REFUSED


def test_phase_skip_or_missing_authorized_phase_is_refused():
    control, _ = controller()
    assert control.request(approval(1), FakeAuthority(), evidence(1)).kind is c.ResultKind.REFUSED
    rejected(lambda: c.approval_contract(**dict(approval_values(), phases=())))


@pytest.mark.parametrize("seconds", [-2, 60, 61])
def test_not_yet_valid_or_expired_approval_is_refused(seconds):
    control, clock = controller()
    clock.current = c.ClockSample(T0 + timedelta(seconds=seconds), N0 + (seconds + 10) * 1_000_000_000)
    assert control.request(approval(), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED


@pytest.mark.parametrize("field", ["utc", "monotonic"])
def test_clock_regression_invalidates_the_session(field):
    control, clock = controller()
    assert control.request(approval(), None, evidence()).kind is c.ResultKind.REFUSED
    clock.current = c.ClockSample(T0 - timedelta(microseconds=1) if field == "utc" else T0,
                                 N0 - 1 if field == "monotonic" else N0)
    assert control.request(approval(), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    assert control.state.lifecycle is c.Lifecycle.INVALIDATED
    clock.current = c.ClockSample(T0, N0)
    assert control.request(approval(serial=2), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED


def test_authority_delay_cannot_extend_the_monotonic_deadline():
    control, clock = controller()

    class DelayedAuthority(FakeAuthority):
        def authenticate(self, supplied):
            result = super().authenticate(supplied)
            clock.current = c.ClockSample(T0, N0 + 60_000_000_000)
            return result

    assert control.request(approval(), DelayedAuthority(), evidence()).kind is c.ResultKind.REFUSED


@pytest.mark.parametrize("seconds,ns", [(-6, -6_000_000_000), (1, 1_000_000_000), (0, -6_000_000_000)])
def test_stale_or_future_evidence_is_refused(seconds, ns):
    control, _ = controller()
    proof = evidence(at=T0 + timedelta(seconds=seconds), ns=N0 + ns)
    assert control.request(approval(), FakeAuthority(), proof).kind is c.ResultKind.REFUSED


def test_replay_of_approval_or_external_reference_is_refused():
    control, _ = controller()
    grant = approval()
    assert control.request(grant, FakeAuthority(), evidence()).kind is c.ResultKind.DESCRIBED
    assert control.request(grant, FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    assert control.record(grant.approval_id, c.ResultKind.SUCCESS, evidence(stage=c.EvidenceStage.AFTER)).kind is c.ResultKind.SUCCESS
    assert control.request(grant, FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    next_grant = replace(approval(1), external_reference=grant.external_reference)
    assert control.request(next_grant, FakeAuthority(), evidence(1)).kind is c.ResultKind.REFUSED


@pytest.mark.parametrize("variant", ["explicit", "missing", "divergent", "late", "monotonic_late", "bad_receipt"])
def test_uncertainty_blocks_retry_and_all_further_actions(variant):
    control, clock = controller()
    grant = approval()
    control.request(grant, FakeAuthority(), evidence())
    proof = evidence(stage=c.EvidenceStage.AFTER)
    outcome = c.ResultKind.SUCCESS
    if variant == "explicit":
        outcome = c.ResultKind.UNCERTAIN
    elif variant == "missing":
        proof = None
    elif variant == "divergent":
        proof = replace(proof, campaign=replace(proof.campaign, network_id="b" * 64))
    elif variant == "late":
        clock.current = c.ClockSample(T0 + timedelta(seconds=60), N0 + 60_000_000_000)
    elif variant == "monotonic_late":
        clock.current = c.ClockSample(T0, N0 + 60_000_000_000)
    else:
        proof = replace(proof, campaign=expected_campaign())
    assert control.record(grant.approval_id, outcome, proof).kind is c.ResultKind.UNCERTAIN
    assert control.state.lifecycle is c.Lifecycle.UNCERTAIN
    assert control.request(approval(serial=3), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    assert control.record(grant.approval_id, c.ResultKind.SUCCESS, evidence(stage=c.EvidenceStage.AFTER)).kind is c.ResultKind.REFUSED
    assert control.invalidate().kind is c.ResultKind.UNCERTAIN


def test_confirmed_failure_requires_its_own_proof_and_invalidates():
    control, _ = controller()
    grant = approval()
    control.request(grant, FakeAuthority(), evidence())
    proof = replace(evidence(stage=c.EvidenceStage.AFTER), campaign=expected_campaign(),
                    observations=(("outcome", "confirmed_failure"), ("effects", "bounded_known")))
    assert control.record(grant.approval_id, c.ResultKind.FAILURE, proof).kind is c.ResultKind.FAILURE
    assert control.state.lifecycle is c.Lifecycle.INVALIDATED
    assert control.request(approval(serial=3), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    control, _ = controller()
    control.request(grant, FakeAuthority(), evidence())
    assert control.record(grant.approval_id, c.ResultKind.FAILURE).kind is c.ResultKind.UNCERTAIN


def test_missing_postcondition_does_not_advance_phase():
    control, _ = controller()
    grant = approval()
    control.request(grant, FakeAuthority(), evidence())
    proof = replace(evidence(stage=c.EvidenceStage.AFTER), observations=(("state", "created"),))
    assert control.record(grant.approval_id, c.ResultKind.SUCCESS, proof).kind is c.ResultKind.UNCERTAIN
    assert control.state.phase is c.Phase.PREPARATION


def test_new_id_is_recorded_but_requires_a_separate_exact_approval():
    control, _ = controller()
    advance(control, 0)
    assert control.state.container_id == "f" * 64
    old_scope = replace(approval(1), campaign=expected_campaign())
    assert control.request(old_scope, FakeAuthority(), evidence(1)).kind is c.ResultKind.REFUSED
    advance(control, 1)


def test_test_doubles_and_a_new_instance_prove_no_real_authority_or_global_replay_safety():
    grant = approval()
    first, _ = controller()
    second, _ = controller()
    for control in (first, second):
        result = control.request(grant, FakeAuthority(), evidence())
        assert result.kind is c.ResultKind.DESCRIBED
        assert result.execution_authorized is False
    # Intentional boundary test: isolated instances have isolated volatile ledgers.
    assert first.state.used_approvals == second.state.used_approvals


def test_errors_from_clock_authority_and_factories_are_sanitized(caplog, capsys):
    class ExplodingAuthority(c.ApprovalAuthority):
        def authenticate(self, supplied):
            raise RuntimeError(MARKER)

    class ExplodingClock(c.Clock):
        def sample(self):
            raise RuntimeError(MARKER)

    control, _ = controller()
    assert control.request(approval(), ExplodingAuthority(), evidence()).kind is c.ResultKind.REFUSED
    control = c.Controller(c.controller_contract(**contract_values()), ExplodingClock())
    assert control.request(approval(), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    try:
        raise RuntimeError(MARKER)
    except RuntimeError:
        rejected(lambda: c.approval_contract(**dict(approval_values(), approval_id=MARKER)))
        rejected(lambda: c.evidence_envelope(**dict(observed_values(), observations=MARKER)))
        rejected(lambda: bool(approval()))
    assert MARKER not in repr(control) + repr(control.state)
    assert caplog.records == []
    output = capsys.readouterr()
    assert output.out == output.err == ""


def test_no_environment_authority_and_no_import_side_effect(monkeypatch):
    for name in ("APPROVED", "ALLOW_BOOTSTRAP", "PGHOST", "PGPASSWORD"):
        monkeypatch.setenv(name, MARKER)
    control, _ = controller()
    assert control.request(approval(), None, evidence()).kind is c.ResultKind.REFUSED
    source = Path(c.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imports.update(a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names)
    assert imports <= {"abc", "dataclasses", "datetime", "enum", "functools", "hashlib", "json", "re", "uuid", "oidc_postgres_support"}
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in {"now", "utcnow"}
                   for n in ast.walk(tree))
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("file IO")
        raise AssertionError("Forbidden IO")

    monkeypatch.setattr(builtins, "open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    exec(compile(source, "offline_controller_import_probe", "exec"), {"__name__": "offline_controller_import_probe"})
    assert attempts == []


@pytest.mark.parametrize("nested", ["invalidate", "same_approval", "other_approval", "record"])
def test_authority_reentrance_is_terminal_and_never_describes_an_action(nested):
    control, _ = controller()
    grant = approval()
    nested_results = []

    class ReentrantAuthority(FakeAuthority):
        def authenticate(self, supplied):
            if nested == "invalidate":
                result = control.invalidate()
            elif nested == "record":
                result = control.record(grant.approval_id, c.ResultKind.SUCCESS)
            else:
                other = grant if nested == "same_approval" else approval(serial=2)
                result = control.request(other, FakeAuthority(), evidence())
            nested_results.append(result)
            return super().authenticate(supplied)

    result = control.request(grant, ReentrantAuthority(), evidence())
    assert result.kind is c.ResultKind.REFUSED and result.action is None
    assert nested_results[0].action is None
    assert control.state.lifecycle is c.Lifecycle.INVALIDATED
    assert control.state.phase is c.Phase.PREPARATION
    assert control.request(approval(serial=3), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    assert control.record(grant.approval_id, c.ResultKind.SUCCESS).kind is c.ResultKind.REFUSED
    assert control.invalidate().kind is c.ResultKind.INVALIDATED


@pytest.mark.parametrize("during", ["first_sample", "second_sample", "record"])
@pytest.mark.parametrize("nested", ["invalidate", "request", "record"])
def test_clock_reentrance_cannot_restore_a_live_state(during, nested):
    control, clock = controller()
    grant = approval()
    if during == "record":
        assert control.request(grant, FakeAuthority(), evidence()).kind is c.ResultKind.DESCRIBED
    calls = []
    nested_results = []

    def sample():
        calls.append(1)
        trigger = len(calls) == (2 if during == "second_sample" else 1)
        if trigger:
            if nested == "invalidate":
                result = control.invalidate()
            elif nested == "request":
                result = control.request(grant, FakeAuthority(), evidence())
            else:
                result = control.record(grant.approval_id, c.ResultKind.SUCCESS,
                                        evidence(stage=c.EvidenceStage.AFTER))
            nested_results.append(result)
        return c.ClockSample(T0, N0)

    clock.sample = sample
    if during == "record":
        result = control.record(grant.approval_id, c.ResultKind.SUCCESS, evidence(stage=c.EvidenceStage.AFTER))
        assert result.kind is c.ResultKind.UNCERTAIN
    else:
        result = control.request(grant, FakeAuthority(), evidence())
        assert result.kind is c.ResultKind.REFUSED
    expected = c.Lifecycle.UNCERTAIN if during == "record" and nested != "invalidate" else c.Lifecycle.INVALIDATED
    assert control.state.lifecycle is expected
    assert result.action is None and nested_results[0].action is None
    assert control.state.phase is c.Phase.PREPARATION
    clock.sample = lambda: c.ClockSample(T0, N0)
    assert control.request(approval(serial=2), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
    assert control.state.lifecycle is expected


@pytest.mark.parametrize("utc_us,mono_ns,accepted", [
    (1_000_000, 1_000_000_000, True),
    (1_000_000, 0, False), (0, 1_000_000_000, False),
    (1_000, 0, True), (0, 1_000_000, True),
    (1_001, 0, False), (0, 1_000_001, False),
])
@pytest.mark.parametrize("after_description", [False, True])
def test_clock_progression_tolerance_and_failure_stage(utc_us, mono_ns, accepted, after_description):
    control, clock = controller()
    grant = approval()
    if after_description:
        assert control.request(grant, FakeAuthority(), evidence()).kind is c.ResultKind.DESCRIBED
    else:
        assert control.request(grant, None, evidence()).kind is c.ResultKind.REFUSED
    at, ns = T0 + timedelta(microseconds=utc_us), N0 + mono_ns
    clock.current = c.ClockSample(at, ns)
    if after_description:
        result = control.record(grant.approval_id, c.ResultKind.SUCCESS, evidence(stage=c.EvidenceStage.AFTER, at=at, ns=ns))
        expected = c.ResultKind.SUCCESS if accepted else c.ResultKind.UNCERTAIN
    else:
        result = control.request(grant, FakeAuthority(), evidence(at=at, ns=ns))
        expected = c.ResultKind.DESCRIBED if accepted else c.ResultKind.REFUSED
    assert result.kind is expected
    if not accepted:
        assert result.action is None
        assert control.state.lifecycle is (c.Lifecycle.UNCERTAIN if after_description else c.Lifecycle.INVALIDATED)


def test_small_clock_divergences_cannot_accumulate_beyond_the_session_anchor():
    control, clock = controller()
    for index in range(3):
        clock.current = c.ClockSample(T0 + timedelta(microseconds=index * 600), N0)
        assert control.request(approval(), None, evidence()).kind is c.ResultKind.REFUSED
        assert control.state.lifecycle is (c.Lifecycle.READY if index < 2 else c.Lifecycle.INVALIDATED)


@pytest.mark.parametrize("dimension", ["duration", "age"])
@pytest.mark.parametrize("difference_us,accepted", [(1_000, True), (1_001, False), (1_000_000, False)])
@pytest.mark.parametrize("after_description", [False, True])
def test_evidence_duration_and_age_must_be_coherent(dimension, difference_us, accepted, after_description):
    control, clock = controller()
    grant = approval()
    at, ns = T0, N0
    stage = c.EvidenceStage.AFTER if after_description else c.EvidenceStage.BEFORE
    if after_description:
        assert control.request(grant, FakeAuthority(), evidence()).kind is c.ResultKind.DESCRIBED
        at, ns = T0 + timedelta(seconds=2), N0 + 2_000_000_000
        clock.current = c.ClockSample(at, ns)
    proof = evidence(stage=stage, at=at, ns=ns)
    if dimension == "duration":
        proof = replace(proof, started_at=at - timedelta(microseconds=difference_us))
    else:
        proof = replace(proof, started_at=at - timedelta(microseconds=difference_us),
                        ended_at=at - timedelta(microseconds=difference_us))
    if after_description:
        result = control.record(grant.approval_id, c.ResultKind.SUCCESS, proof)
        assert result.kind is (c.ResultKind.SUCCESS if accepted else c.ResultKind.UNCERTAIN)
    else:
        result = control.request(grant, FakeAuthority(), proof)
        assert result.kind is (c.ResultKind.DESCRIBED if accepted else c.ResultKind.REFUSED)


@pytest.mark.parametrize("after_description", [False, True])
def test_small_divergence_does_not_extend_expiration(after_description):
    control, clock = controller()
    grant = approval()
    if after_description:
        assert control.request(grant, FakeAuthority(), evidence()).kind is c.ResultKind.DESCRIBED
    else:
        assert control.request(grant, None, evidence()).kind is c.ResultKind.REFUSED
    at, ns = T0 + timedelta(seconds=60), N0 + 59_999_500_000
    clock.current = c.ClockSample(at, ns)
    if after_description:
        result = control.record(grant.approval_id, c.ResultKind.SUCCESS,
                                evidence(stage=c.EvidenceStage.AFTER, at=at, ns=ns))
        assert result.kind is c.ResultKind.UNCERTAIN
    else:
        assert control.request(grant, FakeAuthority(), evidence(at=at, ns=ns)).kind is c.ResultKind.REFUSED


def test_tolerance_never_extends_evidence_age_or_collection_duration():
    control, _ = controller()
    proof = evidence(at=T0 - timedelta(seconds=5, microseconds=1), ns=N0 - 5_000_000_000)
    assert control.request(approval(), FakeAuthority(), proof).kind is c.ResultKind.REFUSED
    proof = replace(evidence(), started_at=T0 - timedelta(seconds=5, microseconds=1),
                    started_ns=N0 - 5_000_000_000)
    rejected(lambda: c.evidence_envelope(**{name: getattr(proof, name) for name in observed_values()}))


@pytest.mark.parametrize("change", [
    {"started_ns": -1}, {"ended_ns": N0 - 1},
    {"started_at": T0 + timedelta(microseconds=1)},
    {"started_ns": N0 - 6_000_000_000},
])
def test_impossible_or_negative_collection_intervals_are_rejected(change):
    rejected(lambda: c.evidence_envelope(**dict(observed_values(), **change)))


def test_callback_exception_after_invalidation_cannot_restore_state():
    control, _ = controller()

    class InvalidatingAuthority(FakeAuthority):
        def authenticate(self, supplied):
            control.invalidate()
            raise RuntimeError(MARKER)

    result = control.request(approval(), InvalidatingAuthority(), evidence())
    assert result.kind is c.ResultKind.REFUSED and result.action is None
    assert control.state.lifecycle is c.Lifecycle.INVALIDATED
    assert control.request(approval(serial=2), FakeAuthority(), evidence()).kind is c.ResultKind.REFUSED
