"""State-machine simulations only, not PostgreSQL atomicity/concurrency proofs."""

from copy import deepcopy
from dataclasses import replace

import pytest

from app.p101_postgres.mapping import map_prediction, validate_read, validate_sources
from app.p101_postgres.runtime import ContentConflict, GuardRejected, PersistenceError
from app.p101_postgres.service import P101PersistenceService
from p101_postgres.conftest import NOW


class SimulatedDatabaseError(Exception):
    def __init__(self, state=None): self.sqlstate = state


class Transaction:
    def __init__(self, session): self.session = session
    def commit(self):
        self.session.events.append("commit")
        if self.session.commit_error: raise self.session.commit_error


class SimulatedSession:
    def __init__(self, commit_error=None):
        self.commit_error = commit_error
        self.new, self.dirty, self.deleted = set(), set(), set()
        self.events = []
    def in_transaction(self): return False
    def begin(self): self.events.append("begin"); return Transaction(self)
    def rollback(self): self.events.append("rollback")
    def close(self): self.events.append("close")


class SimulatedRepository:
    def __init__(self, session, dossier, sources, *, existing=False, mixed=False, failure=None):
        self.session, self.dossier, self.sources = session, dossier, sources
        self.already, self.mixed, self.failure = existing, mixed, failure
        self.reserved = 0
    def step(self, name):
        self.session.events.append(name)
        if self.failure == name: raise ValueError("simulated failure")
    def lock_sources(self): self.step("sources"); return self.sources
    def clock(self): self.step("clock"); return NOW
    def next_id(self): self.step("next_id"); self.reserved += 1; return 9000 + self.reserved
    def reserve(self, target, prediction_id, created_at):
        self.step("reserve")
        existing = self.already or self.mixed and self.reserved == 2
        return not existing, {"prediction_id": prediction_id} if existing else None
    def existing(self, dossier, target, mapping, ledger):
        self.step("existing")
        row = map_prediction(dossier, target, mapping, ledger["prediction_id"], NOW)
        validate_read(dossier, target, mapping, row)
        return row
    def insert_prediction(self, row): self.step("insert")
    def check_constraints(self): self.step("constraints")
    def find(self, target):
        self.step("find")
        if not self.already: return None
        return {"prediction_id": 9001 if target.identity.value.endswith("011") else 9002}


def service(config, verifier, dossier, sources, *, session=None, existing=False, mixed=False, failure=None):
    session = session or SimulatedSession()
    repository = SimulatedRepository(session, dossier, sources, existing=existing, mixed=mixed, failure=failure)
    def guard(session, config): session.events.append("guard")
    instance = P101PersistenceService(config, verifier, session_factory=lambda: session,
        repository_factory=lambda session: repository, guard=guard, clock=lambda: NOW)
    return instance, session


def test_simulated_pair_has_one_commit_and_all_reservations_before_insert(config, verifier, dossier, sources, approval):
    instance, session = service(config, verifier, dossier, sources)
    before = deepcopy(dossier)
    result = instance.persist(dossier, approval)
    assert result.status == "created" and len(result.records) == 2 and dossier == before
    assert [row["score"] for row in result.records] == [0, 1]
    events = session.events
    assert events[:3] == ["begin", "guard", "sources"]
    assert events.count("commit") == 1 and events.count("insert") == 2 and "rollback" not in events
    assert max(i for i, event in enumerate(events) if event == "reserve") < events.index("insert")
    assert events.index("constraints") < events.index("commit") and events[-1] == "close"


def test_simulated_existing_pair_has_no_prediction_insert(config, verifier, dossier, sources, approval):
    instance, session = service(config, verifier, dossier, sources, existing=True)
    assert instance.persist(dossier, approval).status == "existing"
    assert session.events.count("existing") == 2 and "insert" not in session.events


def test_simulated_partial_pair_rolls_back(config, verifier, dossier, sources, approval):
    instance, session = service(config, verifier, dossier, sources, mixed=True)
    with pytest.raises(ContentConflict): instance.persist(dossier, approval)
    assert session.events.count("rollback") == 1 and "commit" not in session.events


@pytest.mark.parametrize("failure", ["sources", "clock", "next_id", "reserve", "insert", "constraints"])
def test_simulated_failure_rolls_back_whole_attempt(config, verifier, dossier, sources, approval, failure):
    instance, session = service(config, verifier, dossier, sources, failure=failure)
    with pytest.raises(PersistenceError): instance.persist(dossier, approval)
    assert session.events.count("rollback") == 1 and "commit" not in session.events
    assert session.events[-1] == "close"


def test_rejected_effective_guard_precedes_all_writes(config, verifier, dossier, sources, approval):
    instance, session = service(config, verifier, dossier, sources)
    def reject(*args): raise GuardRejected("simulated identity mismatch")
    instance._guard = reject
    with pytest.raises(GuardRejected): instance.persist(dossier, approval)
    assert session.events == ["begin", "rollback", "close"]


def test_bad_approval_and_incomplete_dossier_never_open_session(config, verifier, dossier, approval):
    def forbidden(): raise AssertionError("Session must not open")
    instance = P101PersistenceService(config, verifier, session_factory=forbidden, clock=lambda: NOW)
    with pytest.raises(GuardRejected): instance.persist(dossier, replace(approval, signature="bad"))
    with pytest.raises(PersistenceError): instance.persist(replace(dossier, targets=dossier.targets[:1]), approval)


@pytest.mark.parametrize("state", ["08006", "40003", None])
def test_simulated_commit_disconnect_is_explicitly_unknown(config, verifier, dossier, sources, approval, state):
    session = SimulatedSession(commit_error=SimulatedDatabaseError(state))
    instance, _ = service(config, verifier, dossier, sources, session=session)
    result = instance.persist(dossier, approval)
    assert result.status == "commit_unknown" and result.records == []
    assert "rollback" not in session.events and session.events[-1] == "close"


def test_simulated_commit_constraint_error_is_known_abort(config, verifier, dossier, sources, approval):
    session = SimulatedSession(commit_error=SimulatedDatabaseError("23514"))
    instance, _ = service(config, verifier, dossier, sources, session=session)
    with pytest.raises(PersistenceError): instance.persist(dossier, approval)
    assert session.events.count("rollback") == 1


def test_simulated_deadlock_retry_is_bounded_and_reguarded(config, verifier, dossier, sources, approval):
    sessions = [SimulatedSession(commit_error=SimulatedDatabaseError("40P01")) for _ in range(3)]
    iterator = iter(sessions)
    instance = P101PersistenceService(config, verifier, session_factory=lambda: next(iterator),
        repository_factory=lambda s: SimulatedRepository(s, dossier, sources),
        guard=lambda s,c: s.events.append("guard"), clock=lambda: NOW)
    with pytest.raises(PersistenceError): instance.persist(dossier, approval)
    assert all(s.events.count("begin") == s.events.count("guard") == s.events.count("rollback") == 1 for s in sessions)


@pytest.mark.parametrize("present,status", [(True,"existing"), (False,"not_observed")])
def test_simulated_resolution_never_reserves_or_inserts(config, verifier, dossier, sources, approval, present, status):
    instance, session = service(config, verifier, dossier, sources, existing=present)
    result = instance.resolve(dossier, approval)
    assert result.status == status
    assert not {"next_id", "reserve", "insert", "commit"} & set(session.events)
    assert session.events[-2:] == ["rollback", "close"]
