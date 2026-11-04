"""One synthetic offline campaign. No Docker, SQL, authority or collector exists."""

import ast
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone, tzinfo
import hashlib
import json
from pathlib import Path
import sys
import traceback
from unittest.mock import Mock

import pytest

from b2b_postgres_qualification.contracts import (
    Approval, AuthorityClaim, Campaign, Effect, EffectJournal, ExecutionDisabled,
    MigrationPlan, Observation, Rejected,
)
from b2b_postgres_qualification import validation as v


NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)
CAMPAIGN = "11111111-1111-4111-8111-111111111111"
INSTANCE = "22222222-2222-4222-8222-222222222222"
ENGINE = "33333333-3333-4333-8333-333333333333"
SUFFIX = CAMPAIGN.replace("-", "")
PREFIX = "b2bq_" + SUFFIX
PRIVATE = "SYNTHETIC-PRIVATE-DIAGNOSTIC-MARKER"


@pytest.fixture(autouse=True)
def forbid_external_effects(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("External operations forbidden")
    for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection",
                 "socket.getaddrinfo", "subprocess.run", "subprocess.Popen", "os.system"):
        monkeypatch.setattr(name, forbidden)


@pytest.fixture
def campaign():
    return Campaign(CAMPAIGN, INSTANCE, ENGINE, "a" * 64, "b" * 64, "c" * 64,
                    f"b2bq-{SUFFIX}-postgres", PREFIX + "_net", PREFIX + "_data",
                    PREFIX, f"b2bq-{SUFFIX}-postgres", 5432, "172.29.211.0/28",
                    "172.29.211.2", "b2bq-" + SUFFIX,
                    tuple(PREFIX + "_" + kind for kind in v.ROLE_KINDS), "d" * 64, "e" * 64, 170010)


@pytest.fixture
def plan():
    return v.migration_plan("sessions", v.PUBLICATIONS[11:12])


@pytest.fixture
def approval(campaign, plan):
    return Approval("synthetic-authority", CAMPAIGN, "sessions", v.destination_fingerprint(campaign),
                    v.plan_fingerprint(plan), NOW - timedelta(seconds=1), NOW + timedelta(minutes=5))


class FavorableDouble:
    """Deliberately unauthentic assertion, not an authority implementation."""

    def authenticate(self, *, authority_id, envelope_sha256):
        return AuthorityClaim(authority_id, envelope_sha256, True)


def observations(campaign, *, provenance="synthetic"):
    destination = v.destination_fingerprint(campaign)
    def item(kind, cid, facts):
        return Observation(kind, CAMPAIGN, destination, provenance, "synthetic-source",
                           NOW - timedelta(seconds=2), NOW - timedelta(seconds=1), cid,
                           tuple(sorted(facts.items())))
    result = [item("docker", ENGINE, dict(
        engine_id=ENGINE, container_id="a" * 64, container_name=f"b2bq-{SUFFIX}-postgres",
        network_id="c" * 64, network_name=PREFIX + "_net", volume_name=PREFIX + "_data",
        image_sha256="d" * 64, platform="linux/amd64", network_internal="true",
        members="a" * 64 + "," + "b" * 64, volume_target="/var/lib/postgresql/data",
        extra_mounts="", published_ports="", privileged="false", restart_policy="no", state="running"))]
    for i, role in enumerate(campaign.roles, 1):
        cid = f"44444444-4444-4444-8444-{i:012d}"
        result.append(item("postgres", cid, dict(
            database=PREFIX, instance_id=INSTANCE, cluster_name="b2bq-" + SUFFIX,
            session_user=role, current_user=role, server_address="172.29.211.2",
            server_port="5432", version_num="170010", backend_pid=str(100 + i),
            revision="b2b_0002_analyze", superuser="false", createdb="false", createrole="false",
            replication="false", bypassrls="false")))
        result.append(item("tls", cid, dict(sslmode="verify-full", ca_sha256="e" * 64,
                           verified_host=f"b2bq-{SUFFIX}-postgres", tls_in_use="true", backend_pid=str(100 + i))))
    return tuple(result)


def review(campaign, values):
    return v.review_observations(campaign, values, now=NOW, revision="b2b_0002_analyze")


def test_immutable_opaque_and_inert(campaign, plan, approval):
    assert v.validate_campaign(campaign) is campaign
    for obj in (campaign, plan, approval, AuthorityClaim("synthetic", "f" * 64, True)):
        assert not obj.execution_authorized and not obj.authenticated and not obj.real_attested
        assert CAMPAIGN not in repr(obj) and "offline-unattested" in repr(obj)
        with pytest.raises(ExecutionDisabled):
            bool(obj)
    with pytest.raises(FrozenInstanceError):
        campaign.port = 5434
    assert not hasattr(campaign, "__dict__")


@pytest.mark.parametrize("field", ["container_name", "network_name", "volume_name", "database", "host", "cluster_name"])
@pytest.mark.parametrize("name", sorted(v.FORBIDDEN_NAMES) + ["oidct_" + SUFFIX, "oidc-tx-" + SUFFIX + "-postgres"])
def test_existing_and_ambiguous_names_are_rejected(campaign, field, name):
    with pytest.raises(Rejected):
        v.validate_campaign(replace(campaign, **{field: name}))


@pytest.mark.parametrize("field", ["container_id", "runner_id", "network_id"])
@pytest.mark.parametrize("identity", sorted(v.FORBIDDEN_IDS))
def test_known_oidc_resource_ids_rejected(campaign, field, identity):
    with pytest.raises(Rejected):
        v.validate_campaign(replace(campaign, **{field: identity}))


@pytest.mark.parametrize("port", sorted(v.FORBIDDEN_PORTS) + [True, "5432", 0, 65536])
def test_existing_ports_and_coercions_rejected(campaign, port):
    with pytest.raises(Rejected):
        v.validate_campaign(replace(campaign, port=port))


@pytest.mark.parametrize("change", [
    {"instance_id": value} for value in sorted(v.FORBIDDEN_INSTANCES)
] + [{"host": "127.0.0.1"}, {"host": "localhost"}, {"container_id": "c" * 64},
     {"roles": ("ui47_admin", "ui47_migrator", "ui47_app", "observer")},
     {"roles": ["mutable"]}, {"subnet": "172.30.91.0/28"},
     {"subnet": "203.0.113.0/28"}, {"server_address": "172.29.211.0"},
     {"server_version_num": True}, {"ca_sha256": "0" * 64}])
def test_campaign_identity_and_inventory_must_be_exact(campaign, change):
    with pytest.raises(Rejected):
        v.validate_campaign(replace(campaign, **change))


def test_published_references_match_actual_versioned_sources():
    root = Path(__file__).resolve().parents[2] / "backend"
    assert len(v.PUBLICATIONS) == 13
    for i, publication in enumerate(v.PUBLICATIONS):
        assert publication.parent == (v.PUBLICATIONS[i-1].revision if i else None)
        raw = (root / publication.path).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(raw).hexdigest() == publication.sha256
        tree = ast.parse(raw.decode("utf-8"))
        metadata = {}
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                for name in node.targets if isinstance(node, ast.Assign) else [node.target]:
                    if isinstance(name, ast.Name) and name.id in ("revision", "down_revision"):
                        metadata[name.id] = ast.literal_eval(node.value)
        assert metadata == {"revision": publication.revision, "down_revision": publication.parent}
    manifest = json.loads((root / "general_migrations/revision_manifest.json").read_text(encoding="utf-8"))
    assert [(e["revision"], e["parent"], e["path"], e["sha256"]) for e in manifest["revisions"]] == [
        (p.revision, p.parent, p.path, p.sha256) for p in v.PUBLICATIONS[9:]]


@pytest.mark.parametrize("operation", list(v.PLAN_SLICES))
def test_four_exact_separate_plans(operation):
    start, end = v.PLAN_SLICES[operation]
    plan = v.migration_plan(operation, v.PUBLICATIONS[start:end])
    assert plan.initial_revision == v.PUBLICATIONS[start].parent
    assert plan.final_revision == v.PUBLICATIONS[end-1].revision
    assert not plan.execution_authorized


@pytest.mark.parametrize("change", [
    {"operation": "unknown"}, {"initial_revision": "base"}, {"final_revision": "head"},
    {"publications": ()}, {"publications": v.PUBLICATIONS[12:]},
    {"publications": (replace(v.PUBLICATIONS[11], sha256="f" * 64),)},
    {"publications": (replace(v.PUBLICATIONS[11], path="../unapproved.py"),)},
    {"publications": (replace(v.PUBLICATIONS[11], parent="09ac8101e9fe"),)},
])
def test_unknown_altered_and_divergent_plans_rejected(plan, change):
    with pytest.raises(Rejected):
        v.validate_plan(replace(plan, **change))


def test_bootstrap_order_cannot_be_reversed():
    with pytest.raises(Rejected):
        v.migration_plan("bootstrap", tuple(reversed(v.PUBLICATIONS[:9])))


@pytest.mark.parametrize("change", [
    {"expires_at": NOW}, {"expires_at": NOW - timedelta(seconds=1)},
    {"expires_at": NOW + timedelta(hours=1)}, {"issued_at": NOW + timedelta(seconds=1)},
    {"issued_at": NOW.replace(tzinfo=None)}, {"operation": "bootstrap"},
    {"destination_sha256": "f" * 64}, {"plan_sha256": "f" * 64},
    {"campaign_id": INSTANCE}, {"authority_id": PRIVATE},
])
def test_approval_expiry_binding_and_syntax(campaign, plan, approval, change):
    with pytest.raises(Rejected):
        v.review_approval(campaign, plan, replace(approval, **change), FavorableDouble(), now=NOW)


@pytest.mark.parametrize("bad", [None, True, {}, object()])
def test_absent_approval_rejected(campaign, plan, bad):
    authority = Mock()
    with pytest.raises(Rejected):
        v.review_approval(campaign, plan, bad, authority, now=NOW)
    assert authority.mock_calls == []


@pytest.mark.parametrize("bad", [None, True, {}, AuthorityClaim("synthetic", "f" * 64, False),
                                   AuthorityClaim("synthetic", "f" * 64, True)])
def test_non_authenticated_or_mismatched_authority_claim_rejected(campaign, plan, approval, bad):
    authority = Mock()
    authority.authenticate.return_value = bad
    with pytest.raises(Rejected):
        v.review_approval(campaign, plan, approval, authority, now=NOW)


def test_canonical_envelope_and_favorable_double_are_never_authority(campaign, plan, approval):
    encoded = v.approval_canonical(campaign, plan, approval, now=NOW)
    assert encoded == v.approval_canonical(campaign, plan, approval, now=NOW)
    body = json.loads(encoded)
    assert body["envelope"]["destination_sha256"] == v.destination_fingerprint(campaign)
    assert body["envelope"]["plan_sha256"] == v.plan_fingerprint(plan)
    result = v.review_approval(campaign, plan, approval, FavorableDouble(), now=NOW)
    assert not result.authenticated and not result.execution_authorized
    authority = Mock(wraps=FavorableDouble())
    with pytest.raises(ExecutionDisabled):
        v.request_execution(campaign, plan, approval, authority, now=NOW)
    assert authority.mock_calls == []


@pytest.mark.parametrize("provenance", ["synthetic", "unverified_external"])
def test_observation_concordance_never_becomes_real_attestation(campaign, provenance):
    result = review(campaign, observations(campaign, provenance=provenance))
    assert result.stage == "injected_observations_only"
    assert not result.real_attested and not result.execution_authorized
    with pytest.raises(ExecutionDisabled):
        v.require_real_attestation(result)


@pytest.mark.parametrize("change", [
    {"provenance": "real"}, {"provenance": "attested"}, {"provenance": True},
    {"observed_at": NOW - timedelta(seconds=31), "started_at": NOW - timedelta(seconds=32)},
    {"observed_at": NOW + timedelta(seconds=1)}, {"started_at": NOW - timedelta(seconds=20)},
    {"campaign_id": INSTANCE}, {"destination_sha256": "f" * 64},
    {"source_id": ""}, {"connection_id": CAMPAIGN + " "},
])
def test_observation_provenance_freshness_and_destination_rejected(campaign, change):
    values = observations(campaign)
    with pytest.raises(Rejected):
        review(campaign, (replace(values[0], **change), *values[1:]))


@pytest.mark.parametrize("position,key,value", [
    (0, "published_ports", "5434:5432"), (0, "network_internal", "false"),
    (0, "volume_name", "industrial-predict-postgres-ui47-data"), (0, "members", "unknown"),
    (0, "extra_mounts", "private"), (1, "database", "industrial_predict_dev"),
    (1, "current_user", "ui47_app"), (1, "superuser", "true"),
    (1, "revision", "09ac8101e9fe"), (2, "sslmode", "disable"),
    (2, "ca_sha256", "f" * 64), (2, "backend_pid", "999"),
])
def test_divergent_docker_sql_tls_facts_rejected(campaign, position, key, value):
    values = list(observations(campaign))
    facts = dict(values[position].facts)
    facts[key] = value
    values[position] = replace(values[position], facts=tuple(sorted(facts.items())))
    with pytest.raises(Rejected):
        review(campaign, tuple(values))


def test_duplicate_missing_mutable_and_unbound_observations_rejected(campaign):
    values = observations(campaign)
    for altered in (values[:-1], values + (values[0],), (values[0], values[1], values[1], *values[3:]),
                    (replace(values[0], facts=list(values[0].facts)), *values[1:]),
                    (values[0], values[1], replace(values[2], connection_id=INSTANCE), *values[3:])):
        with pytest.raises(Rejected):
            review(campaign, altered)


def test_journal_uncertainty_is_terminal_and_original_is_immutable(campaign):
    journal = EffectJournal(CAMPAIGN, v.destination_fingerprint(campaign))
    first = v.append_effect(campaign, journal, Effect("bootstrap", "commit_confirmed", NOW, "f" * 64))
    uncertain = v.append_effect(campaign, first, Effect("sessions", "uncertain", NOW, None))
    assert journal.entries == () and len(first.entries) == 1
    assert v.journal_summary(campaign, uncertain)["uncertain"]
    assert not uncertain.real_attested
    for outcome in v.OUTCOMES:
        with pytest.raises(Rejected):
            v.append_effect(campaign, uncertain, Effect("analysis", outcome, NOW, "f" * 64))
    with pytest.raises(Rejected):
        v.validate_journal(campaign, replace(uncertain, entries=uncertain.entries + (Effect("analysis", "commit_confirmed", NOW, "f" * 64),)))


@pytest.mark.parametrize("change", [
    {"outcome": "success"}, {"operation": "arbitrary"}, {"evidence_sha256": None},
    {"evidence_sha256": PRIVATE}, {"at": NOW.replace(tzinfo=None)},
])
def test_journal_rejects_unsupported_or_unsubstantiated_claims(campaign, change):
    journal = EffectJournal(CAMPAIGN, v.destination_fingerprint(campaign))
    entry = Effect("sessions", "commit_confirmed", NOW, "f" * 64)
    with pytest.raises(Rejected):
        v.append_effect(campaign, journal, replace(entry, **change))


def test_refusal_and_rollback_are_distinct_declared_outcomes(campaign):
    journal = EffectJournal(CAMPAIGN, v.destination_fingerprint(campaign))
    for outcome in ("refused", "rollback_confirmed"):
        journal = v.append_effect(campaign, journal, Effect("sessions", outcome, NOW, "f" * 64))
    assert v.journal_summary(campaign, journal)["outcomes"] == ("refused", "rollback_confirmed")
    with pytest.raises(Rejected):
        v.validate_journal(campaign, replace(journal, campaign_id=INSTANCE))


def test_scenarios_are_descriptions_and_cover_required_categories():
    assert {s.category for s in v.SCENARIOS} == {"migrations", "sessions", "concurrency", "authorization", "privileges"}
    assert len({s.identifier for s in v.SCENARIOS}) == len(v.SCENARIOS) == 26
    for scenario in v.SCENARIOS:
        assert all(type(value) is str and value for value in (
            scenario.identifier, scenario.precondition, scenario.action, scenario.expected, scenario.evidence, scenario.stop))
        assert not callable(scenario.action)


def test_diagnostics_and_representations_do_not_leak_context(campaign, plan, approval):
    class BrokenTimezone(tzinfo):
        def utcoffset(self, value):
            raise ValueError(PRIVATE)
    try:
        raise ValueError(PRIVATE)
    except ValueError:
        for call in (
            lambda: v.validate_campaign(replace(campaign, database=PRIVATE)),
            lambda: v.review_approval(campaign, plan, approval, Mock(authenticate=Mock(side_effect=RuntimeError(PRIVATE))), now=NOW),
            lambda: v.approval_canonical(campaign, plan, approval, now=NOW.replace(tzinfo=BrokenTimezone())),
            lambda: v.request_execution(PRIVATE),
        ):
            with pytest.raises((Rejected, ExecutionDisabled)) as caught:
                call()
            error = caught.value
            assert error.__context__ is None and error.__cause__ is None
            assert PRIVATE not in "".join(traceback.format_exception(error))
            assert PRIVATE not in repr(error)
    for obj in (replace(campaign, database=PRIVATE), replace(approval, authority_id=PRIVATE),
                Effect("sessions", "uncertain", NOW, PRIVATE)):
        assert PRIVATE not in repr(obj)


def test_modules_have_no_operational_imports_or_application_dependency():
    directory = Path(__file__).parent
    allowed = {"dataclasses", "datetime", "functools", "hashlib", "ipaddress", "json", "re", "uuid", "typing",
               "b2b_postgres_qualification.contracts"}
    for name in ("contracts.py", "validation.py"):
        tree = ast.parse((directory / name).read_text(encoding="utf-8"))
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module)
        assert set(imports) <= allowed
    assert "app.general_migrations" not in sys.modules
    assert "psycopg" not in sys.modules
