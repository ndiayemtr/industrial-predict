"""Injected authority/transaction claims only, never real authentication or SQL writes."""

from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.core.authorization import AccountState, CompanyMembership, MembershipState, Permission, Role, VerifiedIdentity
from app.core.caller_session import CurrentCaller, SessionReference, CallerUnauthenticated
from app.p101_dev.contracts import Abstained, Computed, Rejected
from app.schemas.prediction_record import PredictionRecordCreate
from app.services.p101_dev_orchestration import (
    AnalysisOutcome, DuplicatePrediction, OrchestrationError, P101DevOrchestrator, PersistenceState as S,
)
from p101_dev_sql.test_loader import db, no_live_database


PRIVATE = "SECRET_DRIVER_AND_IDENTITY_DIAGNOSTIC"


class PortDouble:
    def __init__(self, db):
        self.db = db
        self.reference = SessionReference("a"*64)
        self.identity = VerifiedIdentity(17, "https://issuer.example", "synthetic-subject", AccountState.ACTIVE)
        self.member = CompanyMembership(17, 101, MembershipState.ACTIVE, Role.COMPANY_ADMIN,
                                        frozenset({Permission.PREDICTIONS_ANALYZE}))
        self.write_session = Mock(spec=Session)
        self.write_session.is_active = True
        self.write_session.in_transaction.return_value = True
        self.write_session.in_nested_transaction.return_value = False
        self.write_session.get_bind.return_value.get_transaction.return_value = SimpleNamespace(is_active=True)
        self.events, self.rows, self.staged, self.reserved = [], [], [], set()
        self.read_caller = self.write_caller = None
        self.changed = None
        self.ack = S.COMMIT_CONFIRMED
        self.stage_error = self.enter_error = self.read_error = self.cleanup_error = False
        self.commit_error = False
        self.commit_first = False
        self.keep_read_open = False
        self.last_snapshot = None

    @contextmanager
    def read(self):
        self.events.append("read_enter")
        try:
            yield self.db.session
        finally:
            self.events.append("read_exit")
            if not self.keep_read_open:
                self.db.connection.get_transaction.return_value.is_active = False
        if self.read_error: raise RuntimeError(PRIVATE)

    @contextmanager
    def write(self):
        self.events.append("write_enter")
        if self.enter_error: raise RuntimeError(PRIVATE)
        try:
            yield self.write_session
        except BaseException:
            self.staged.clear()
            raise
        finally:
            self.events.append("write_exit")
        if self.cleanup_error: raise RuntimeError(PRIVATE)

    def current_caller(self, session, *, reference, now):
        phase = "read" if session is self.db.session else "write"
        self.events.append(phase+"_caller")
        override = self.read_caller if phase == "read" else self.write_caller
        if override is not None: return override(reference, now)
        return CurrentCaller(reference, self.identity, (self.member,), now)

    def lock_and_reload(self, session, *, plan, authorization, now):
        assert session is self.write_session
        assert authorization.company_id == 101 and authorization.permission is Permission.PREDICTIONS_ANALYZE
        self.events.append("locked_reload")
        current = replace(plan.snapshot, observed_at=now)
        if self.changed: current = self.changed(current)
        self.last_snapshot = current
        return current

    def reserve_and_stage(self, session, *, key, draft, created_at):
        assert session is self.write_session and session is not self.db.session
        self.events.append("stage")
        if key in self.reserved: raise DuplicatePrediction()
        self.reserved.add(key)
        self.staged.append(draft.values(created_at=created_at))
        if self.stage_error: raise RuntimeError(PRIVATE)
        return 7

    def finish(self, session):
        assert session is self.write_session
        self.events.append("finish")
        if self.commit_error:
            if self.commit_first: self.rows.extend(self.staged)
            raise RuntimeError(PRIVATE)
        if self.ack is S.COMMIT_CONFIRMED: self.rows.extend(self.staged)
        self.staged.clear()
        return self.ack


@pytest.fixture
def scenario(db):
    port = PortDouble(db)
    times = iter([db.arguments["observed_at"], db.arguments["observed_at"]+timedelta(seconds=5)])
    service = P101DevOrchestrator(port=port, clock=lambda: next(times))
    request = dict(reference=port.reference, company_id=101, equipment_id=303, sensor_id=404,
                   target_measurement_id=11, event_cutoff=db.arguments["event_cutoff"],
                   provenance=db.arguments["provenance"])
    return service, port, request


def assert_no_stage(port):
    assert "stage" not in port.events and "finish" not in port.events and not port.rows


def test_authorized_computed_path_prepares_then_separately_stages(scenario):
    service, port, request = scenario
    analysis = service.prepare(**request)  # Uses the actual DEV-2 loader with mocked SQL Session.
    assert type(analysis) is AnalysisOutcome and type(analysis.result) is Computed
    plan = analysis.prepared
    assert plan is not None and not analysis.real_attested
    assert port.events == ["read_enter", "read_caller", "read_exit"]
    assert_no_stage(port)
    values = plan.draft.values(created_at=plan.prepared_at)
    dto = PredictionRecordCreate.model_validate({k:v for k,v in values.items() if k != "created_at"})
    assert dto.equipment_id == 303 and dto.sensor_id == 404 and dto.measurement_id == 11
    assert dto.prediction_type.value == "anomaly" and dto.score == 1 and dto.is_alert is True
    assert values["model_version"] == "p101-dev-stat-v1"
    assert values["details"] == analysis.result.details
    values["details"].clear()
    assert plan.draft.values(created_at=plan.prepared_at)["details"] == analysis.result.details
    report = service.persist(plan)
    assert report.state is S.COMMIT_CONFIRMED and report.prediction_id == 7 and not report.real_attested
    assert port.events.index("read_exit") < port.events.index("write_enter") < port.events.index("write_caller")
    assert port.events.index("write_caller") < port.events.index("locked_reload") < port.events.index("stage")
    assert port.rows[0]["details"] == analysis.result.details
    assert port.rows[0]["created_at"] > plan.prepared_at
    assert port.last_snapshot.observed_at > plan.snapshot.observed_at
    for name in ("commit", "rollback", "flush", "close"):
        getattr(port.db.session, name).assert_not_called()
        getattr(port.db.connection, name if name != "flush" else "commit").assert_not_called()


@pytest.mark.parametrize("fault", ["no_grant", "inactive_membership", "revoked_user", "wrong_company",
    "wrong_reference", "stale_caller", "typed_decision_only"])
def test_read_authority_denied_before_business_loading(scenario, fault):
    service, port, request = scenario
    def caller(reference, now):
        identity, member = port.identity, port.member
        if fault == "no_grant": member = replace(member, permissions=frozenset())
        elif fault == "inactive_membership": member = replace(member, state=MembershipState.INACTIVE, permissions=frozenset())
        elif fault == "revoked_user": raise CallerUnauthenticated()
        elif fault == "wrong_company": member = replace(member, company_id=999)
        elif fault == "wrong_reference": reference = SessionReference("b"*64)
        elif fault == "stale_caller": now -= timedelta(seconds=1)
        elif fault == "typed_decision_only": return port.db.arguments["authorization"]
        return CurrentCaller(reference, identity, (member,), now)
    port.read_caller = caller
    with pytest.raises(OrchestrationError): service.prepare(**request)
    port.db.connection.execute.assert_not_called()
    assert_no_stage(port)


def test_effective_sql_company_mismatch_refuses_before_measures(scenario):
    service, port, request = scenario
    port.db.chain[0].update(company_id=999, site_company_id=999)
    with pytest.raises(OrchestrationError): service.prepare(**request)
    assert len(port.db.queries) == 1 and not port.rows


@pytest.mark.parametrize("fault,expected", [("missing_history", Abstained), ("provenance", Rejected),
                                           ("quality", Abstained), ("constant", Abstained)])
def test_abstention_and_rejection_have_no_persistence_plan(scenario, fault, expected):
    service, port, request = scenario
    if fault == "missing_history": port.db.refs = port.db.refs[:3]
    elif fault == "provenance": request["provenance"] = replace(request["provenance"], source_id="")
    elif fault == "quality": port.db.refs[0]["quality"] = "bad"
    else:
        for row in port.db.refs: row["value"] = 65
    analysis = service.prepare(**request)
    assert type(analysis.result) is expected and analysis.prepared is None
    with pytest.raises(OrchestrationError): service.persist(analysis.prepared)
    assert "write_enter" not in port.events
    assert_no_stage(port)


@pytest.mark.parametrize("fault", ["revoked_session", "revoked_grant", "inactive_membership", "suspended_user", "different_actor"])
def test_fresh_write_authority_revocation_prevents_staging(scenario, fault):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    def caller(reference, now):
        identity, member = port.identity, port.member
        if fault == "revoked_session": raise CallerUnauthenticated()
        elif fault == "revoked_grant": member = replace(member, permissions=frozenset())
        elif fault == "inactive_membership": member = replace(member, state=MembershipState.INACTIVE, permissions=frozenset())
        elif fault == "suspended_user": identity = replace(identity, account_state=AccountState.SUSPENDED)
        else:
            identity, member = replace(identity, user_id=91), replace(member, user_id=91)
        return CurrentCaller(reference, identity, (member,), now)
    port.write_caller = caller
    assert service.persist(plan).state is S.REFUSED
    assert "locked_reload" not in port.events
    assert_no_stage(port)


@pytest.mark.parametrize("fault", ["company", "equipment", "sensor", "target", "reference", "quality", "extra", "provenance", "stale_observation"])
def test_locked_source_changes_prevent_staging(scenario, fault):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    def changed(snapshot):
        if fault == "company": return replace(snapshot, chain=replace(snapshot.chain, company_id=999, site_company_id=999))
        if fault == "equipment": return replace(snapshot, chain=replace(snapshot.chain, equipment_id=999, sensor_equipment_id=999))
        if fault == "sensor": return replace(snapshot, chain=replace(snapshot.chain, sensor_id=999))
        if fault == "target": return replace(snapshot, target=replace(snapshot.target, value=71))
        if fault == "reference": return replace(snapshot, references=(replace(snapshot.references[0], value=66), *snapshot.references[1:]))
        if fault == "quality": return replace(snapshot, references=(replace(snapshot.references[0], quality="bad"), *snapshot.references[1:]))
        if fault == "extra": return replace(snapshot, references=(*snapshot.references, replace(snapshot.target, id=12)))
        if fault == "provenance": return replace(snapshot, provenance=replace(snapshot.provenance, source_id="changed-source"))
        return replace(snapshot, observed_at=snapshot.observed_at-timedelta(seconds=1))
    port.changed = changed
    assert service.persist(plan).state is S.REFUSED
    assert_no_stage(port)


@pytest.mark.parametrize("fault", ["read_exit", "write_enter", "stage"])
def test_transaction_failures_are_not_success_and_never_retried(scenario, fault):
    service, port, request = scenario
    if fault == "read_exit":
        port.read_error = True
        with pytest.raises(OrchestrationError): service.prepare(**request)
        assert "write_enter" not in port.events
        return
    plan = service.prepare(**request).prepared
    port.enter_error, port.stage_error = fault == "write_enter", fault == "stage"
    report = service.persist(plan)
    assert report.state is (S.UNCERTAIN if fault == "stage" else S.REFUSED)
    assert report.prediction_id is None and not port.rows
    with pytest.raises(OrchestrationError): service.persist(plan)
    assert port.events.count("write_enter") == 1


@pytest.mark.parametrize("commit_first", [False, True])
def test_lost_commit_acknowledgement_is_terminal_without_retry(scenario, commit_first):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    port.commit_error, port.commit_first = True, commit_first
    report = service.persist(plan)
    assert report.state is S.UNCERTAIN and report.prediction_id is None
    assert len(port.rows) == int(commit_first)
    with pytest.raises(OrchestrationError): service.persist(plan)
    assert port.events.count("finish") == 1 and port.events.count("stage") == 1
    assert PRIVATE not in repr(report)


@pytest.mark.parametrize("ack", [S.ROLLBACK_CONFIRMED, S.UNCERTAIN, True])
def test_explicit_finish_outcomes_are_not_promoted_to_success(scenario, ack):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    port.ack = ack
    report = service.persist(plan)
    assert report.state is (S.ROLLBACK_CONFIRMED if ack is S.ROLLBACK_CONFIRMED else S.UNCERTAIN)
    assert report.prediction_id is None and not port.rows
    with pytest.raises(OrchestrationError): service.persist(plan)


def test_confirmed_commit_is_preserved_if_resource_cleanup_fails(scenario):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    port.cleanup_error = True
    report = service.persist(plan)
    assert report.state is S.COMMIT_CONFIRMED and report.cleanup_failed and report.prediction_id == 7
    assert len(port.rows) == 1


def test_duplicate_reservation_never_stages_second_prediction(scenario):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    port.reserved.add(plan.key)
    assert service.persist(plan).state is S.REFUSED
    assert not port.staged and not port.rows and "finish" not in port.events


def test_altered_or_foreign_plan_cannot_replace_registered_plan(scenario):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    with pytest.raises(OrchestrationError): service.persist(replace(plan, key="f"*64))
    assert "write_enter" not in port.events
    assert service.persist(plan).state is S.COMMIT_CONFIRMED


def test_write_cannot_reuse_read_session(scenario):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    port.write_session = port.db.session
    assert service.persist(plan).state is S.REFUSED
    assert_no_stage(port)


def test_read_transaction_must_have_ended_before_returning_a_plan(scenario):
    service, port, request = scenario
    port.keep_read_open = True
    with pytest.raises(OrchestrationError): service.prepare(**request)
    assert_no_stage(port)


def test_new_session_cannot_reuse_read_transaction(scenario):
    service, port, request = scenario
    plan = service.prepare(**request).prepared
    port.write_session.get_bind.return_value = port.db.connection
    assert service.persist(plan).state is S.REFUSED
    assert_no_stage(port)
