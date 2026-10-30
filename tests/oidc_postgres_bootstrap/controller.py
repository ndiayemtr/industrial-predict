"""Deterministic in-memory control model; no operational executor or collector."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from functools import wraps
from hashlib import sha256
import json
import re
from uuid import UUID

from oidc_postgres_support import CampaignContract, validate_contract


MAX_VALIDITY = timedelta(minutes=10)
MAX_PROOF_AGE = timedelta(seconds=5)
CLOCK_TOLERANCE = timedelta(milliseconds=1)
_FAILURE_FACTS = (("outcome", "confirmed_failure"), ("effects", "bounded_known"))
_REQUIRED_ARTIFACTS = frozenset({
    "bootstrap.sh", "controller.py", "validation.py", "openssl.cnf.in", "roles.sql.in",
    "postgresql.local.conf.in", "postgresql.tls.conf.in", "pg_hba.local.conf.in", "pg_hba.tls.conf.in",
})


class ControlRejected(ValueError):
    def __init__(self):
        super().__init__("OIDC offline control data rejected")


def _raise_public():
    try:
        raise ControlRejected() from None
    except ControlRejected as error:
        error.__context__ = None
        error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _guarded(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            pass
        _raise_public()
    return checked


def _mutation(function):
    @wraps(function)
    def checked(self, *args, **kwargs):
        if self._mutation_active:
            # Sequential reentrance is a security event, not a retry request.
            self._halt(uncertain=function.__name__ != "invalidate" and self._pending is not None)
            if function.__name__ == "invalidate":
                kind = ResultKind.UNCERTAIN if self._lifecycle is Lifecycle.UNCERTAIN else ResultKind.INVALIDATED
                return Decision(kind, None)
            return Decision(ResultKind.REFUSED, None)
        self._mutation_active = True
        try:
            return function(self, *args, **kwargs)
        finally:
            # Only release the local guard; never restore lifecycle or state.
            self._mutation_active = False
    return checked


class _Opaque:
    __slots__ = ()

    def __repr__(self):
        return f"<{type(self).__name__}: offline>"

    def __bool__(self):
        _raise_public()

    @property
    def execution_authorized(self):
        return False


class Phase(Enum):
    PREPARATION = "preparation"
    RECREATION_AUTHORIZED = "recreation_authorized"
    NEW_CONTAINER_INSPECTED = "new_container_inspected"
    LOCAL_BOOTSTRAP = "local_bootstrap"
    TLS_CONFIGURATION = "tls_configuration"
    FINAL_ATTESTATION = "final_attestation"


class Operation(Enum):
    RECREATE = "recreate"
    INSPECT_NEW = "inspect_new"
    BOOTSTRAP_LOCAL = "bootstrap_local"
    CONFIGURE_TLS = "configure_tls"
    ATTEST_FINAL = "attest_final"


class Lifecycle(Enum):
    READY = "ready"
    PENDING = "pending"
    COMPLETE = "complete"
    INVALIDATED = "invalidated"
    UNCERTAIN = "uncertain"


class ResultKind(Enum):
    DESCRIBED = "action_description_only"
    SUCCESS = "success_attested_by_injected_data"
    REFUSED = "refused"
    FAILURE = "confirmed_failure"
    UNCERTAIN = "uncertain"
    INVALIDATED = "invalidated"


class AuthorityDecision(Enum):
    ATTESTED = "attested_by_injected_authority"
    UNATTESTED = "unattested"
    REFUSED = "refused"


class Provenance(Enum):
    EXTERNAL_HUMAN_APPROVAL = "external_human_approval_claim"


class EvidenceStage(Enum):
    BEFORE = "before"
    AFTER = "after"


@dataclass(frozen=True, slots=True, repr=False)
class ArtifactDigest(_Opaque):
    name: str
    sha256: str


@dataclass(frozen=True, slots=True, repr=False)
class ClockSample(_Opaque):
    utc: datetime
    monotonic_ns: int


class Clock(ABC):
    @abstractmethod
    def sample(self) -> ClockSample:
        """Injected clock only; no default global clock exists."""


@dataclass(frozen=True, slots=True, repr=False)
class ControllerContract(_Opaque):
    campaign: CampaignContract
    session_id: str
    collector_session_id: str
    engine_id: str
    git_revision: str
    artifacts: tuple[ArtifactDigest, ...]


@dataclass(frozen=True, slots=True, repr=False)
class Approval(_Opaque):
    approval_id: str
    external_reference: str
    provenance: Provenance
    controller_session_id: str
    campaign: CampaignContract
    engine_id: str
    git_revision: str
    artifacts: tuple[ArtifactDigest, ...]
    operations: tuple[Operation, ...]
    phases: tuple[Phase, ...]
    not_before: datetime
    expires_at: datetime
    preconditions: tuple[tuple[str, str], ...]
    postconditions: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True, repr=False)
class AuthorityVerdict(_Opaque):
    decision: AuthorityDecision
    approval_id: str
    external_reference: str
    provenance: Provenance
    controller_session_id: str
    approval_digest: str


class ApprovalAuthority(ABC):
    @abstractmethod
    def authenticate(self, approval: Approval) -> AuthorityVerdict:
        """Future independent executor boundary; no real implementation here.

        A Python object or implementation of this interface proves no authenticity.
        Test doubles may assert ATTESTED; that is a simulation, never a capability.
        """


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceEnvelope(_Opaque):
    declared_source: str
    engine_id: str
    campaign: CampaignContract
    controller_session_id: str
    collector_session_id: str
    phase: Phase
    stage: EvidenceStage
    started_at: datetime
    ended_at: datetime
    started_ns: int
    ended_ns: int
    git_revision: str
    artifacts: tuple[ArtifactDigest, ...]
    observations: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True, repr=False)
class ActionDescription(_Opaque):
    approval_id: str
    approval_digest: str
    session_id: str
    campaign_id: str
    engine_id: str
    container_id: str
    network_id: str
    operation: Operation
    phase: Phase


@dataclass(frozen=True, slots=True, repr=False)
class Decision(_Opaque):
    kind: ResultKind
    action: ActionDescription | None


@dataclass(frozen=True, slots=True, repr=False)
class StateSnapshot(_Opaque):
    phase: Phase
    lifecycle: Lifecycle
    container_id: str
    used_approvals: tuple[str, ...]


# Fixed transition policy, not conditions invented by each approval/caller.
# Claimed facts below must eventually be acquired from real independent sources.
_POLICIES = (
    (Operation.RECREATE, Phase.PREPARATION, Phase.RECREATION_AUTHORIZED, "docker-inspector",
     (("state", "created"), ("started", "never"), ("network_members", "none"), ("artifacts", "reviewed")),
     (("state", "created"), ("entrypoint", "controlled"), ("mounts", "tmpfs_only"),
      ("ports", "loopback_only"), ("limits", "768m_1cpu"), ("restart", "no"))),
    (Operation.INSPECT_NEW, Phase.RECREATION_AUTHORIZED, Phase.NEW_CONTAINER_INSPECTED, "docker-inspector",
     (("state", "created"), ("creation_receipt", "recorded")),
     (("identity", "exact_new_id"), ("configuration", "exact_manifest"), ("dev_p101", "unchanged"))),
    (Operation.BOOTSTRAP_LOCAL, Phase.NEW_CONTAINER_INSPECTED, Phase.LOCAL_BOOTSTRAP, "local-inspector",
     (("generation", "first"), ("pgdata", "empty"), ("tmpfs", "verified"), ("authority", "separate_phase")),
     (("version", "17.10"), ("auth", "scram-sha-256"), ("transport", "private_unix"),
      ("tcp", "absent"), ("roles", "restricted"), ("table_oidc", "absent"))),
    (Operation.CONFIGURE_TLS, Phase.LOCAL_BOOTSTRAP, Phase.TLS_CONFIGURATION, "tls-inspector",
     (("tcp", "absent"), ("roles", "restricted"), ("container", "same_generation")),
     (("tls", "verified"), ("san", "IP:127.0.0.1"), ("hba", "restricted"),
      ("bootstrap_login", "disabled"), ("container", "same_generation"))),
    (Operation.ATTEST_FINAL, Phase.TLS_CONFIGURATION, Phase.FINAL_ATTESTATION, "sql-inspector",
     (("tls", "verified"), ("hba", "restricted")),
     (("sql_identity", "exact"), ("sessions", "three_independent_pids"), ("client", "verify-full"),
      ("source", "observed_expected"), ("privileges", "restricted"), ("table_oidc", "absent"))),
)


def _require(condition):
    if not condition:
        raise ControlRejected()


def _uuid(value):
    _require(type(value) is str)
    parsed = UUID(value)
    _require(str(parsed) == value and parsed.int != 0)


def _hex(value, length=64):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value) is not None)
    _require(value != "0" * length)


def _utc(value):
    _require(type(value) is datetime and value.tzinfo is timezone.utc)


def _shape(value, cls):
    _require(type(value) is cls)
    for field in fields(cls):
        item = getattr(value, field.name)
        if field.type is CampaignContract:
            validate_contract(item)
        elif field.type is datetime:
            _utc(item)
        elif field.type in (str, int, bool):
            _require(type(item) is field.type)
        elif isinstance(field.type, type) and issubclass(field.type, Enum):
            _require(type(item) is field.type)
        else:
            _require(type(item) is tuple)


def _artifacts(values):
    _require(type(values) is tuple and len(values) > 0)
    names = []
    for artifact in values:
        _shape(artifact, ArtifactDigest)
        _require(re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}", artifact.name) is not None)
        _require(".." not in artifact.name)
        _hex(artifact.sha256)
        names.append(artifact.name)
    _require(names == sorted(set(names)) and set(names) == _REQUIRED_ARTIFACTS)


def _facts(values):
    _require(type(values) is tuple and len(values) > 0)
    names = []
    for pair in values:
        _require(type(pair) is tuple and len(pair) == 2)
        _require(all(type(item) is str and re.fullmatch(r"[A-Za-z0-9_:.-]{1,80}", item) is not None for item in pair))
        names.append(pair[0])
    _require(len(names) == len(set(names)))


def _policy(operation):
    _require(type(operation) is Operation)
    return next(row for row in _POLICIES if row[0] is operation)


def _contract(contract):
    _shape(contract, ControllerContract)
    for value in (contract.session_id, contract.collector_session_id, contract.engine_id):
        _uuid(value)
    _hex(contract.git_revision, 40)
    _artifacts(contract.artifacts)
    _require(contract.campaign.server_version_num == 170010)
    return contract


def _approval(approval):
    _shape(approval, Approval)
    for value in (approval.approval_id, approval.external_reference, approval.controller_session_id, approval.engine_id):
        _uuid(value)
    _hex(approval.git_revision, 40)
    _artifacts(approval.artifacts)
    _require(timedelta(0) < approval.expires_at - approval.not_before <= MAX_VALIDITY)
    _require(len(approval.operations) == len(approval.phases) == 1)
    policy = _policy(approval.operations[0])
    _require(type(approval.phases[0]) is Phase and approval.phases[0] is policy[2])
    _facts(approval.preconditions)
    _facts(approval.postconditions)
    _require(approval.preconditions == policy[4] and approval.postconditions == policy[5])
    return approval


def _evidence(evidence):
    _shape(evidence, EvidenceEnvelope)
    for value in (evidence.engine_id, evidence.controller_session_id, evidence.collector_session_id):
        _uuid(value)
    _hex(evidence.git_revision, 40)
    _artifacts(evidence.artifacts)
    _facts(evidence.observations)
    _require(evidence.declared_source in ("docker-inspector", "local-inspector", "tls-inspector", "sql-inspector"))
    _require(0 <= evidence.started_ns <= evidence.ended_ns)
    _require(timedelta(0) <= evidence.ended_at - evidence.started_at <= MAX_PROOF_AGE)
    _require(evidence.ended_ns - evidence.started_ns <= _ns(MAX_PROOF_AGE))
    _coherent(evidence.ended_at - evidence.started_at, evidence.ended_ns - evidence.started_ns)
    return evidence


def _ns(duration):
    return (duration // timedelta(microseconds=1)) * 1000


def _coherent(utc_duration, monotonic_ns):
    _require(utc_duration >= timedelta(0) and monotonic_ns >= 0)
    _require(abs(_ns(utc_duration) - monotonic_ns) <= _ns(CLOCK_TOLERANCE))


@_guarded
def controller_contract(**values):
    return _contract(ControllerContract(**values))


@_guarded
def approval_contract(**values):
    return _approval(Approval(**values))


@_guarded
def evidence_envelope(**values):
    return _evidence(EvidenceEnvelope(**values))


def _canonical(value):
    if isinstance(value, Enum):
        return value.value
    if type(value) is datetime:
        return value.isoformat()
    if type(value) is tuple:
        return [_canonical(item) for item in value]
    if hasattr(type(value), "__dataclass_fields__"):
        return {field.name: _canonical(getattr(value, field.name)) for field in fields(value)}
    return value


@_guarded
def approval_fingerprint(approval):
    _approval(approval)
    return sha256(json.dumps(_canonical(approval), sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


class Controller(_Opaque):
    """Linear, process-local state and replay ledger. Never dispatches an action.

    The mutable ledger prevents reusing old snapshots through THIS instance.
    It is neither durable nor a multi-process/cryptographic security boundary.
    """

    @_guarded
    def __init__(self, contract, clock):
        self._contract = _contract(contract)
        _require(isinstance(clock, Clock))
        self._clock = clock
        self._phase = Phase.PREPARATION
        self._lifecycle = Lifecycle.READY
        self._container_id = contract.campaign.container_id
        self._used = set()
        self._external_used = set()
        self._last_time = None
        self._time_anchor = None
        self._pending = None
        self._mutation_active = False

    @property
    def state(self):
        return StateSnapshot(self._phase, self._lifecycle, self._container_id, tuple(sorted(self._used)))

    def _halt(self, *, uncertain=False):
        if self._lifecycle not in (Lifecycle.INVALIDATED, Lifecycle.UNCERTAIN):
            self._lifecycle = Lifecycle.UNCERTAIN if uncertain else Lifecycle.INVALIDATED
        self._pending = None

    def _integrity(self):
        return (id(self._contract), self._contract.session_id, self._contract.collector_session_id,
                self._phase, self._lifecycle, self._container_id, id(self._pending),
                frozenset(self._used), frozenset(self._external_used),
                id(self._last_time), id(self._time_anchor))

    def _callback(self, function, *args):
        expected = self._integrity()
        result = function(*args)
        if self._integrity() != expected:
            self._halt(uncertain=self._pending is not None)
            raise ControlRejected()
        return result

    def _sample(self):
        sample = self._callback(self._clock.sample)
        _shape(sample, ClockSample)
        _require(sample.monotonic_ns >= 0)
        for previous in (self._last_time, self._time_anchor):
            if previous is not None:
                _coherent(sample.utc - previous.utc, sample.monotonic_ns - previous.monotonic_ns)
        if self._time_anchor is None:
            self._time_anchor = sample
        self._last_time = sample
        return sample

    def _destination(self):
        return replace(self._contract.campaign, container_id=self._container_id)

    def _proof(self, proof, approval, stage, now, *, failure=False):
        _evidence(proof)
        contract = self._contract
        operation = approval.operations[0]
        policy = _policy(operation)
        _require(proof.engine_id == contract.engine_id)
        _require(proof.controller_session_id == contract.session_id)
        _require(proof.collector_session_id == contract.collector_session_id)
        _require(proof.artifacts == contract.artifacts and proof.git_revision == contract.git_revision)
        _require(proof.phase is policy[2] and proof.stage is stage and proof.declared_source == policy[3])
        expected = self._destination()
        if operation is Operation.RECREATE and stage is EvidenceStage.AFTER and not failure:
            # Creation returns an ID unknown before the operation. Only that
            # field may change; all other manifest fields remain exact.
            _require(proof.campaign.container_id != self._container_id)
            expected = replace(expected, container_id=proof.campaign.container_id)
        _require(proof.campaign == expected)
        expected_facts = _FAILURE_FACTS if failure else (policy[4] if stage is EvidenceStage.BEFORE else policy[5])
        _require(proof.observations == expected_facts)
        _require(timedelta(0) <= now.utc - proof.ended_at <= MAX_PROOF_AGE)
        _require(0 <= now.monotonic_ns - proof.ended_ns <= _ns(MAX_PROOF_AGE))
        _coherent(now.utc - proof.ended_at, now.monotonic_ns - proof.ended_ns)

    def _valid_window(self, approval, now):
        _require(approval.not_before <= now.utc < approval.expires_at)

    @_guarded
    @_mutation
    def request(self, approval, authority, before):
        if self._lifecycle is not Lifecycle.READY:
            return Decision(ResultKind.REFUSED, None)
        try:
            now = self._sample()
        except Exception:
            self._halt()
            return Decision(ResultKind.REFUSED, None)
        try:
            _approval(approval)
            _require(approval.approval_id not in self._used)
            _require(approval.external_reference not in self._external_used)
            _require(approval.controller_session_id == self._contract.session_id)
            _require(approval.campaign == self._destination() and approval.engine_id == self._contract.engine_id)
            _require(approval.artifacts == self._contract.artifacts and approval.git_revision == self._contract.git_revision)
            policy = _policy(approval.operations[0])
            _require(self._phase is policy[1])
            self._valid_window(approval, now)
            deadline = now.monotonic_ns + _ns(approval.expires_at - now.utc)
            _require(isinstance(authority, ApprovalAuthority))
            verdict = self._callback(authority.authenticate, approval)
            _shape(verdict, AuthorityVerdict)
            _require(verdict.decision is AuthorityDecision.ATTESTED)
            _require(verdict.approval_id == approval.approval_id and verdict.external_reference == approval.external_reference)
            _require(verdict.provenance is approval.provenance and verdict.controller_session_id == approval.controller_session_id)
            digest = approval_fingerprint(approval)
            _require(verdict.approval_digest == digest)
            # Consume an attested reference even if a subsequent precondition fails.
            self._used.add(approval.approval_id)
            self._external_used.add(approval.external_reference)
        except Exception:
            return Decision(ResultKind.REFUSED, None)
        try:
            now = self._sample()  # Recheck after time spent at the authority boundary.
        except Exception:
            self._halt()
            return Decision(ResultKind.REFUSED, None)
        try:
            self._valid_window(approval, now)
            _require(now.monotonic_ns < deadline)
            self._proof(before, approval, EvidenceStage.BEFORE, now)
            action = ActionDescription(approval.approval_id, digest, self._contract.session_id,
                approval.campaign.campaign_id, approval.engine_id, self._container_id,
                approval.campaign.network_id, approval.operations[0], policy[2])
            self._pending = (approval, action, now, deadline)
            self._lifecycle = Lifecycle.PENDING
            return Decision(ResultKind.DESCRIBED, action)
        except Exception:
            return Decision(ResultKind.REFUSED, None)

    @_guarded
    @_mutation
    def record(self, approval_id, outcome, after=None):
        if self._lifecycle is not Lifecycle.PENDING or self._pending is None:
            return Decision(ResultKind.REFUSED, None)
        approval, action, issued, deadline = self._pending
        try:
            _require(type(approval_id) is str and approval_id == action.approval_id)
            _require(type(outcome) is ResultKind)
            _require(outcome in (ResultKind.SUCCESS, ResultKind.FAILURE, ResultKind.UNCERTAIN))
            now = self._sample()
            self._valid_window(approval, now)
            _require(now.monotonic_ns < deadline)
            if outcome is ResultKind.UNCERTAIN:
                self._lifecycle = Lifecycle.UNCERTAIN
            elif outcome is ResultKind.FAILURE:
                self._proof(after, approval, EvidenceStage.AFTER, now, failure=True)
                _require(after.started_at >= issued.utc and after.started_ns >= issued.monotonic_ns)
                self._lifecycle = Lifecycle.INVALIDATED
            else:
                self._proof(after, approval, EvidenceStage.AFTER, now)
                _require(after.started_at >= issued.utc and after.started_ns >= issued.monotonic_ns)
                if action.operation is Operation.RECREATE:
                    self._container_id = after.campaign.container_id
                self._phase = action.phase
                self._lifecycle = (Lifecycle.COMPLETE if action.phase is Phase.FINAL_ATTESTATION else Lifecycle.READY)
            self._pending = None
            return Decision(outcome, None)
        except Exception:
            # Once described/consumed, absent or mismatching results are uncertain.
            self._halt(uncertain=True)
            return Decision(ResultKind.UNCERTAIN, None)

    @_guarded
    @_mutation
    def invalidate(self):
        if self._lifecycle is Lifecycle.UNCERTAIN:
            return Decision(ResultKind.UNCERTAIN, None)
        self._halt()
        return Decision(ResultKind.INVALIDATED, None)
