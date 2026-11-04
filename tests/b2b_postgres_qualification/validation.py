"""Deterministic declarations and comparisons; no files, clocks, network or SQL."""

from dataclasses import asdict
from datetime import datetime, timedelta
from functools import wraps
from hashlib import sha256
from ipaddress import IPv4Address, IPv4Network
import json
import re
from uuid import UUID

from b2b_postgres_qualification.contracts import (
    Approval, AuthorityClaim, Campaign, Effect, EffectJournal, ExecutionDisabled,
    MigrationPlan, Observation, Publication, Rejected, Review, Scenario, deny,
)


REFERENCE_HEAD = "3917027af6fabb482af1fa4a650e4f676025b8ad"
# Exact source references at REFERENCE_HEAD; never discovered or re-approved at runtime.
PUBLICATIONS = (
    Publication('0468ed5be8f1', None, 'migrations/versions/0468ed5be8f1_create_companies_table.py', 'e5e562511a7e83d4d984f51a58ced52c827521618e77a5f2ac101fddf8894bba'),
    Publication('50e5051527dc', '0468ed5be8f1', 'migrations/versions/50e5051527dc_create_sites_table.py', '24c8234a5e8ce9aae6dbd3b8fcfa1b58539eb19874d36518dfdd544a73b63b66'),
    Publication('656260b06cdf', '50e5051527dc', 'migrations/versions/656260b06cdf_create_equipments_table.py', '636729273bc38cf8571eb6c9fd2945d9d1c7c572a4ada82432fa0e2e30c41269'),
    Publication('572080d9e581', '656260b06cdf', 'migrations/versions/572080d9e581_create_sensors_table.py', 'a623ae93139cd1f88deb299b20aa9e69d1fe99428a37e03fd90fd7dfbf9d81ca'),
    Publication('570ce155aaf8', '572080d9e581', 'migrations/versions/570ce155aaf8_create_measurements_table.py', 'bc9262c2685575835ad372d4c82e174d9327a065b728675b2ba72e798968d44c'),
    Publication('783e16aa6ce3', '570ce155aaf8', 'migrations/versions/783e16aa6ce3_create_maintenance_records_table.py', '780c871579b9cc7a0b91dc4f7836ac17e64d984db20dd6647cc9a09249c4aef9'),
    Publication('675ebfea0bb5', '783e16aa6ce3', 'migrations/versions/675ebfea0bb5_add_equipment_criticality.py', '3d7e21e45645c53ece6fac7355209d2a011cba7c58f18599b1a3c22bd1a1d041'),
    Publication('d6ec01cf13b6', '675ebfea0bb5', 'migrations/versions/d6ec01cf13b6_add_prediction_records.py', '1fbda40b9aa8a1997ecb29fd6859a3c64785781c5163128940612bd5f15b4f99'),
    Publication('09ac8101e9fe', 'd6ec01cf13b6', 'migrations/versions/09ac8101e9fe_add_maintenance_recommendations.py', '11e4b0d62de251d00d1ee1829ff031b8492d43a49ca8d9d931cb1fe0489488ef'),
    Publication('12e2fc65f372', '09ac8101e9fe', 'general_migrations/versions/12e2fc65f372_create_oidc_transactions.py', '8dd65b4517c0fba38f789b8b2ce016cafa80794fd0bcf6b8a35d194773da5274'),
    Publication('4b7e2a91c6d0', '12e2fc65f372', 'general_migrations/versions/4b7e2a91c6d0_create_professional_accounts.py', '0aed6450f32f5b5459684de15c72f442cdaa39672df30224affb6b55221f1a26'),
    Publication('b2b_0001_sessions', '4b7e2a91c6d0', 'general_migrations/versions/b2b_0001_sessions.py', '64da06799a0c0d5033343ec91d6a5539d6cdef98ffc9a74f3d64a6a8beb1fe66'),
    Publication('b2b_0002_analyze', 'b2b_0001_sessions', 'general_migrations/versions/b2b_0002_analyze.py', 'ae59ca35458ca475e01057f025ff5b8e9f91af7e18301a0e6e3817454cb575fe'),
)

FORBIDDEN_IDS = frozenset({
    "00dc9dd7a2b2204a5017662cadfdc9c8ee9ec48b70fe75c56ef92362c641c03e",
    "bad3825904081e17d0c9dcf14ac7a88b3560cedaf60d8cb6c9912710b858b85e",
})
FORBIDDEN_INSTANCES = frozenset({
    "fb3284bd-fb7b-4c22-b620-96a1564b1d0c",
    "a62b2d3d-2b10-4a00-8c01-202610290001",
})
FORBIDDEN_PORTS = frozenset({5433, 5434, 55432, 56439, 8000, 8001, 8011, 4200, 4201, 4211})
FORBIDDEN_NAMES = frozenset({
    "industrial_predict", "industrial_predict_dev", "industrial_predict_ml_sandbox",
    "industrial_predict_p101_local_demo", "industrial-predict-postgres",
    "industrial-predict-postgres-ui47", "industrial-predict-postgres-ui47-data",
    "industrial-predict-p101-local-demo-data", "industrial-predict-p101-local-demo-net",
    "industrial-predict-p101-local-demo-postgres", "postgres_data",
})
ROLE_KINDS = ("admin", "migrator", "runtime", "observer")
PLAN_SLICES = {"bootstrap": (0, 9), "prerequisites": (9, 11), "sessions": (11, 12), "analysis": (12, 13)}
OUTCOMES = ("refused", "rollback_confirmed", "commit_confirmed", "uncertain")


def guarded(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            pass
        deny(Rejected)
    return checked


def require(condition):
    if not condition:
        raise Rejected()


def text(value):
    require(type(value) is str and re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", value) is not None)


def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None and value != "0" * 64)


def identifier(value):
    require(type(value) is str and str(UUID(value)) == value and UUID(value).int != 0)
    require(value not in FORBIDDEN_INSTANCES)


def utc(value):
    require(type(value) is datetime and value.tzinfo is not None and value.utcoffset() == timedelta(0))


def _canonical(value):
    # Private: only called after the complete public object's validation.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _fingerprint(value):
    return sha256(_canonical(value).encode("ascii")).hexdigest()


@guarded
def validate_campaign(campaign):
    require(type(campaign) is Campaign)
    for value in (campaign.campaign_id, campaign.instance_id, campaign.engine_id):
        identifier(value)
    require(campaign.campaign_id != campaign.instance_id)
    ids = (campaign.container_id, campaign.runner_id, campaign.network_id)
    for value in (*ids, campaign.image_sha256, campaign.ca_sha256):
        digest(value)
    require(len(set(ids)) == 3 and not set(ids) & FORBIDDEN_IDS)
    suffix = UUID(campaign.campaign_id).hex
    prefix = "b2bq_" + suffix
    for actual, expected in (
        (campaign.container_name, f"b2bq-{suffix}-postgres"),
        (campaign.network_name, prefix + "_net"), (campaign.volume_name, prefix + "_data"),
        (campaign.database, prefix), (campaign.host, f"b2bq-{suffix}-postgres"),
        (campaign.cluster_name, "b2bq-" + suffix),
    ):
        require(type(actual) is str and actual not in FORBIDDEN_NAMES and actual == expected)
    require(type(campaign.roles) is tuple and all(type(role) is str for role in campaign.roles))
    require(campaign.roles == tuple(prefix + "_" + kind for kind in ROLE_KINDS))
    require(type(campaign.port) is int and campaign.port not in FORBIDDEN_PORTS and campaign.port == 5432)
    require(type(campaign.server_version_num) is int and campaign.server_version_num == 170010)
    require(type(campaign.subnet) is str and type(campaign.server_address) is str)
    network = IPv4Network(campaign.subnet, strict=True)
    require(24 <= network.prefixlen <= 28)
    require(any(network.subnet_of(IPv4Network(block)) for block in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16")))
    require(not network.overlaps(IPv4Network("172.30.91.0/28")))
    address = IPv4Address(campaign.server_address)
    require(address in network and address not in (network.network_address, network.broadcast_address))
    return campaign


@guarded
def destination_fingerprint(campaign):
    return _fingerprint(asdict(validate_campaign(campaign)))


@guarded
def validate_plan(plan):
    require(type(plan) is MigrationPlan and type(plan.operation) is str and plan.operation in PLAN_SLICES)
    require(type(plan.publications) is tuple)
    start, end = PLAN_SLICES[plan.operation]
    expected = PUBLICATIONS[start:end]
    require(len(plan.publications) == len(expected))
    for actual, published in zip(plan.publications, expected):
        require(type(actual) is Publication)
        require(all(type(getattr(actual, key)) is str for key in ("revision", "path", "sha256")))
        require(actual.parent is None or type(actual.parent) is str)
        require(actual == published)
    require(plan.initial_revision is None if start == 0 else type(plan.initial_revision) is str)
    require(plan.initial_revision == expected[0].parent and type(plan.final_revision) is str and plan.final_revision == expected[-1].revision)
    return plan


@guarded
def migration_plan(operation, publications):
    require(type(operation) is str and operation in PLAN_SLICES and type(publications) is tuple and len(publications) > 0)
    require(all(type(item) is Publication for item in publications))
    return validate_plan(MigrationPlan(operation, publications[0].parent, publications[-1].revision, publications))


@guarded
def plan_fingerprint(plan):
    return _fingerprint({"reference_head": REFERENCE_HEAD, "plan": asdict(validate_plan(plan))})


@guarded
def approval_canonical(campaign, plan, approval, *, now):
    validate_campaign(campaign)
    validate_plan(plan)
    require(type(approval) is Approval)
    text(approval.authority_id)
    require(type(approval.campaign_id) is str and approval.campaign_id == campaign.campaign_id)
    require(type(approval.operation) is str and approval.operation == plan.operation)
    for value in (approval.destination_sha256, approval.plan_sha256):
        digest(value)
    require(approval.destination_sha256 == destination_fingerprint(campaign) and approval.plan_sha256 == plan_fingerprint(plan))
    for instant in (now, approval.issued_at, approval.expires_at):
        utc(instant)
    require(approval.issued_at <= now < approval.expires_at)
    require(timedelta(0) < approval.expires_at - approval.issued_at <= timedelta(minutes=15))
    body = asdict(approval)
    for key in ("issued_at", "expires_at"):
        body[key] = body[key].isoformat(timespec="microseconds")
    return _canonical({"format": "b2b-qualification-approval-v1", "envelope": body})


@guarded
def review_approval(campaign, plan, approval, authority, *, now):
    envelope = approval_canonical(campaign, plan, approval, now=now)
    expected = sha256(envelope.encode("ascii")).hexdigest()
    claim = authority.authenticate(authority_id=approval.authority_id, envelope_sha256=expected)
    require(type(claim) is AuthorityClaim and type(claim.claimed_authenticated) is bool and claim.claimed_authenticated)
    require(type(claim.authority_id) is str and type(claim.envelope_sha256) is str)
    require(claim.authority_id == approval.authority_id and claim.envelope_sha256 == expected)
    return Review("unverified_authority_claim_only")


def _expected_facts(campaign, kind, role, revision, pid):
    if kind == "docker":
        return dict(engine_id=campaign.engine_id, container_id=campaign.container_id,
                    container_name=campaign.container_name, network_id=campaign.network_id,
                    network_name=campaign.network_name, volume_name=campaign.volume_name,
                    image_sha256=campaign.image_sha256, platform="linux/amd64",
                    network_internal="true", members=",".join(sorted((campaign.container_id, campaign.runner_id))),
                    volume_target="/var/lib/postgresql/data", extra_mounts="", published_ports="",
                    privileged="false", restart_policy="no", state="running")
    if kind == "postgres":
        return dict(database=campaign.database, instance_id=campaign.instance_id,
                    cluster_name=campaign.cluster_name, session_user=role, current_user=role,
                    server_address=campaign.server_address, server_port=str(campaign.port),
                    version_num=str(campaign.server_version_num), backend_pid=pid,
                    revision=revision, superuser="false", createdb="false", createrole="false",
                    replication="false", bypassrls="false")
    return dict(sslmode="verify-full", ca_sha256=campaign.ca_sha256,
                verified_host=campaign.host, tls_in_use="true", backend_pid=pid)


@guarded
def review_observations(campaign, observations, *, now, revision):
    validate_campaign(campaign)
    utc(now)
    require(type(revision) is str and revision in ("empty", *(p.revision for p in PUBLICATIONS)))
    require(type(observations) is tuple and len(observations) == 9)
    grouped = {}
    for observation in observations:
        require(type(observation) is Observation)
        require(type(observation.kind) is str and observation.kind in ("docker", "postgres", "tls"))
        require(type(observation.provenance) is str and observation.provenance in ("synthetic", "unverified_external"))
        text(observation.source_id)
        identifier(observation.connection_id)
        require(type(observation.campaign_id) is str and observation.campaign_id == campaign.campaign_id)
        digest(observation.destination_sha256)
        require(observation.destination_sha256 == destination_fingerprint(campaign))
        utc(observation.started_at)
        utc(observation.observed_at)
        require(timedelta(0) <= observation.observed_at - observation.started_at <= timedelta(seconds=10))
        require(timedelta(0) <= now - observation.observed_at <= timedelta(seconds=30))
        require(type(observation.facts) is tuple and len(observation.facts) <= 25)
        for pair in observation.facts:
            require(type(pair) is tuple and len(pair) == 2 and all(type(value) is str for value in pair))
            require(len(pair[0]) <= 64 and len(pair[1]) <= 256)
        require(observation.facts == tuple(sorted(observation.facts)))
        facts = dict(observation.facts)
        require(len(facts) == len(observation.facts))
        role = facts.get("session_user", "") if observation.kind == "postgres" else ""
        if observation.kind != "docker":
            pid = facts.get("backend_pid", "")
            require(re.fullmatch(r"[1-9][0-9]{0,9}", pid) is not None)
            if observation.kind == "postgres":
                require(role in campaign.roles)
        else:
            pid = ""
        require(facts == _expected_facts(campaign, observation.kind, role, revision, pid))
        key = (observation.kind, observation.connection_id)
        require(key not in grouped)
        grouped[key] = (observation, facts)
    require(sum(kind == "docker" for kind, _ in grouped) == 1)
    pg = [(cid, value) for (kind, cid), value in grouped.items() if kind == "postgres"]
    require(len(pg) == 4 and {facts["session_user"] for _, (_, facts) in pg} == set(campaign.roles))
    require(len({facts["backend_pid"] for _, (_, facts) in pg}) == 4)
    for cid, (observation, facts) in pg:
        tls, tls_facts = grouped[("tls", cid)]
        require(tls_facts["backend_pid"] == facts["backend_pid"])
        require(tls.provenance == observation.provenance)
        require(tls.started_at == observation.started_at and tls.observed_at == observation.observed_at)
    return Review("injected_observations_only")


def request_execution(*args, **kwargs):
    """Unconditional refusal, without inspecting inputs or calling an authority."""
    deny(ExecutionDisabled)


def require_real_attestation(*args, **kwargs):
    """No provenance string or synthetic datum can become a real attestation."""
    deny(ExecutionDisabled)


@guarded
def validate_journal(campaign, journal):
    validate_campaign(campaign)
    require(type(journal) is EffectJournal)
    require(type(journal.campaign_id) is str and journal.campaign_id == campaign.campaign_id)
    digest(journal.destination_sha256)
    require(journal.destination_sha256 == destination_fingerprint(campaign))
    require(type(journal.entries) is tuple and len(journal.entries) <= 1000)
    previous = None
    for entry in journal.entries:
        require(type(entry) is Effect)
        require(type(entry.operation) is str and entry.operation in (*PLAN_SLICES, *(s.identifier for s in SCENARIOS)))
        require(type(entry.outcome) is str and entry.outcome in OUTCOMES)
        utc(entry.at)
        if previous is not None:
            require(previous.outcome != "uncertain" and previous.at <= entry.at)
        if entry.evidence_sha256 is not None:
            digest(entry.evidence_sha256)
        require(entry.outcome not in ("commit_confirmed", "rollback_confirmed") or entry.evidence_sha256 is not None)
        previous = entry
    return journal


@guarded
def append_effect(campaign, journal, entry):
    validate_journal(campaign, journal)
    return validate_journal(campaign, EffectJournal(journal.campaign_id, journal.destination_sha256, journal.entries + (entry,)))


@guarded
def journal_summary(campaign, journal):
    validate_journal(campaign, journal)
    return {"stage": "declared_effects_only", "execution_authorized": False,
            "uncertain": any(e.outcome == "uncertain" for e in journal.entries),
            "outcomes": tuple(e.outcome for e in journal.entries)}


# Catalogue descriptions only: no SQL, callable actions or execution dispatcher.
SCENARIOS = tuple(Scenario(identifier, category, precondition, action, expected,
                           "Independent bounded observations and before/after state", stop)
                  for identifier, category, precondition, action, expected, stop in (
    ("migration_initial", "migrations", "Approved empty isolated schema", "Install exact historical and account plans", "Exact account revision", "Unexpected schema or revision"),
    ("migration_sessions", "migrations", "Account revision, empty or existing accounts", "Apply session publication", "Exact columns, composite FK, CHECKs and indexes; accounts unchanged", "Unexpected object or row change"),
    ("migration_analysis", "migrations", "Session revision", "Apply analysis publication", "Only CHECK extended; no grants created", "Automatic grant or historical regression"),
    ("migration_refusal", "migrations", "Divergent schema, source or scope", "Submit divergent plan", "Refusal before effects", "Any operation accepted"),
    ("session_create_read", "sessions", "Approved synthetic admission, active account", "Create then read with fresh connection", "Confirmed session, no raw secret stored", "Success before commit or secret disclosure"),
    ("session_idle_expiry", "sessions", "Session at idle boundary", "Read or touch", "Exclusive expiry refusal", "Session accepted"),
    ("session_absolute_expiry", "sessions", "Session at absolute boundary", "Read or rotate", "Refusal without lifetime extension", "Session accepted or expiry extended"),
    ("session_revoke", "sessions", "Live session", "Revoke and reread", "Old reference refused", "Old reference accepted"),
    ("session_rotate", "sessions", "Live session", "Rotate", "Successor and predecessor changed atomically", "Partial state"),
    ("session_bulk_revoke", "sessions", "Administrative authority; expired and suspended cases", "Revoke all for user", "All unrevoked sessions invalidated", "Missed session or missing authority accepted"),
    ("session_integrity", "sessions", "Isolated inconsistent pairs and invalid values", "Attempt invalid writes", "FK, PK and CHECK refuse covered invalid data", "Invalid row committed"),
    ("session_infinity", "sessions", "Isolated infinite timestamp fixtures", "Check SQL and adapter behavior separately", "Document SQL gaps; no usable invalid session", "Invalid session accepted"),
    ("session_suspension", "sessions", "Account suspended under user lock", "Read, create and rotate", "Refusal", "Session accepted"),
    ("session_rollback", "sessions", "Rotation fault before commit", "Fail after successor insert", "No partial effect after rollback", "Persisted partial state"),
    ("lock_expiry", "concurrency", "Two connections and blocked user row", "Resume after expiry", "Clock checked after lock; refusal", "Stale time accepted"),
    ("concurrent_rotation", "concurrency", "Two connections, same old session", "Rotate concurrently", "At most one success from old reference", "Two successes"),
    ("concurrent_revocation", "concurrency", "Rotation/revocation on same user", "Exercise both lock orders", "Serialized coherent outcomes", "Reusable revoked session"),
    ("bulk_create_race", "concurrency", "Bulk revocation and creation", "Exercise both orders", "User lock respected; later login distinguished", "Revocation bypass"),
    ("lock_failure", "concurrency", "Bounded deliberate lock wait or deadlock", "Exceed timeout", "Closed failure, rollback and no retry", "Unbounded wait or implicit retry"),
    ("commit_uncertain", "concurrency", "Dedicated lost-acknowledgement fault", "Lose commit confirmation", "Uncertain result, no secret delivery or retry", "Automatic success, retry or cleanup"),
    ("permission_history", "authorization", "All roles and historical permissions", "Check allowed combinations", "Historical ceilings preserved", "Permission regression"),
    ("permission_analysis", "authorization", "All roles", "Attempt analysis grant and role forgery", "Only actual company_admin ceiling", "Escalation"),
    ("permission_explicit", "authorization", "Active admin without grant", "Evaluate before and after explicit grant", "Deny then allow exact company", "Implicit grant"),
    ("permission_scope", "authorization", "Inactive membership or company B request", "Evaluate scoped permission", "Refusal", "Cross-company or inactive access"),
    ("runtime_minimal", "privileges", "Minimal role and no sequence grants", "Exercise store and row locks", "Operations succeed without elevation", "Stronger role used"),
    ("runtime_denials", "privileges", "Normal bounded transaction as runtime", "Attempt DDL, business writes and administration", "ACL refusal, business state unchanged", "Forbidden operation succeeds"),
))
