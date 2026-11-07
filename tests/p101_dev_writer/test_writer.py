"""Offline doubles only. No PostgreSQL locking/durability claim is made here."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from psycopg.pq import TransactionStatus
from sqlalchemy import inspect
from sqlalchemy.orm import SessionTransactionOrigin

from app.core.caller_session import CallerUnauthenticated
from app.p101_dev.contracts import Abstained, AbstentionCode, Rejected, RejectionCode
from app.services import p101_dev_writer as writer
from app.services.p101_dev_orchestration import PersistenceState, PredictionDraft
from p101_dev_orchestration.test_orchestration import scenario
from p101_dev_sql.test_loader import db, no_live_database


@pytest.fixture
def case(scenario):
    service, original, request = scenario
    plan = service.prepare(**request).prepared
    database = original.db
    database.connection.get_transaction.return_value.is_active = True
    database.connection.get_isolation_level.return_value = "SERIALIZABLE"
    destination = writer.PostgreSQLDestination("synthetic", "writer", "writer", "192.0.2.1", 5432)
    proof = dict(database="synthetic", session_user="writer", current_user="writer",
                 server_address="192.0.2.1", server_port=5432, isolation="serializable", read_only="off")
    execute = database.connection.execute.side_effect
    def query(statement):
        if statement is writer.CONNECTION_SQL:
            result = Mock()
            result.mappings.return_value.one.return_value = dict(proof)
            return result
        return execute(statement)
    database.connection.execute.side_effect = query
    provider = Mock()
    provider.current_caller.side_effect = lambda **kwargs: original.current_caller(database.session, **kwargs)
    read_context = Mock(side_effect=AssertionError("Unexpected read lifecycle"))
    port = writer.P101PostgreSQLWriter(destination=destination, caller_provider=provider, read_context=read_context)
    database.connection.execute.reset_mock()
    database.queries.clear()
    return SimpleNamespace(db=database, port=port, provider=provider, original=original, plan=plan,
                           now=plan.prepared_at+timedelta(seconds=5), proof=proof, read_context=read_context)


def preflight(case, **overrides):
    return case.port.preflight(case.db.session, **(dict(plan=case.plan, now=case.now) | overrides))


def assert_no_mutation(case):
    for target in (case.db.session, case.db.connection):
        for name in ("commit", "rollback", "close"):
            getattr(target, name).assert_not_called()
    for name in ("add", "flush", "refresh", "connection", "begin"):
        getattr(case.db.session, name).assert_not_called()


def test_authorized_computed_preflight_is_only_a_transient_mapping(case):
    record = preflight(case)
    assert inspect(record).transient and record.id is None
    assert (record.equipment_id, record.sensor_id, record.measurement_id) == (303, 404, 11)
    assert record.score == 1 and record.is_alert is True and record.prediction_type == "anomaly"
    assert record.details == case.plan.draft.computed.details
    assert record.created_at == case.now
    assert len(case.db.queries) == 3
    assert all("public." in sql for sql, params in case.db.queries)
    assert_no_mutation(case)


@pytest.mark.parametrize("fault", ["no_grant", "other_company", "revoked", "stale", "actor", "browser_decision"])
def test_fresh_authority_refused_before_source_queries(case, fault):
    def current(**kwargs):
        if fault == "revoked": raise CallerUnauthenticated()
        value = case.original.current_caller(case.db.session, **kwargs)
        if fault == "browser_decision": return case.db.arguments["authorization"]
        if fault == "stale": return replace(value, refreshed_at=value.refreshed_at-timedelta(seconds=1))
        if fault == "actor": return replace(value, identity=replace(value.identity, subject="other"))
        member = value.memberships[0]
        member = replace(member, permissions=frozenset()) if fault == "no_grant" else replace(member, company_id=999)
        return replace(value, memberships=(member,))
    case.provider.current_caller.side_effect = current
    with pytest.raises(writer.WriterRefused): preflight(case)
    assert not case.db.queries
    assert_no_mutation(case)


@pytest.mark.parametrize("fault", ["site", "equipment", "sensor", "target", "value", "phantom", "missing",
                                  "fingerprint", "score", "key"])
def test_changed_sources_and_forged_results_refused(case, fault):
    if fault == "site": case.db.chain[0]["site_company_id"] = 999
    elif fault == "equipment": case.db.chain[0]["equipment_site_id"] = 999
    elif fault == "sensor": case.db.chain[0]["sensor_equipment_id"] = 999
    elif fault == "target": case.db.target[0]["sensor_id"] = 999
    elif fault == "value": case.db.refs[0]["value"] = 500
    elif fault == "phantom": case.db.refs.append(dict(case.db.refs[0], id=999))
    elif fault == "missing": case.db.refs.pop()
    elif fault == "key": case.plan = replace(case.plan, key="f"*64)
    else:
        result = case.plan.draft.computed
        result = replace(result, input_sha256="f"*64) if fault == "fingerprint" else replace(result, score=0)
        case.plan = replace(case.plan, draft=PredictionDraft(result))
    with pytest.raises(writer.WriterRefused): preflight(case)
    assert_no_mutation(case)


@pytest.mark.parametrize("fault", ["destination", "role", "address", "port", "read_only", "server_isolation",
    "autocommit", "ambiguous_autocommit", "inerror", "invalidated", "closed", "no_tx", "nested",
    "autobegin", "autoflush", "dirty", "bind", "schema", "isolation", "dialect", "inactive"])
def test_connection_contract_fails_closed(case, fault):
    db = case.db
    if fault == "destination": case.proof["database"] = "other"
    elif fault == "role": case.proof["current_user"] = "other"
    elif fault == "address": case.proof["server_address"] = "192.0.2.2"
    elif fault == "port": case.proof["server_port"] = 5433
    elif fault == "read_only": case.proof["read_only"] = "on"
    elif fault == "server_isolation": case.proof["isolation"] = "read committed"
    elif fault == "autocommit": db.driver.autocommit = True
    elif fault == "ambiguous_autocommit": db.driver.autocommit = 0
    elif fault == "inerror": db.driver.info.transaction_status = TransactionStatus.INERROR
    elif fault == "invalidated": db.connection.invalidated = True
    elif fault == "closed": db.connection.closed = True
    elif fault == "no_tx": db.connection.in_transaction.return_value = False
    elif fault == "nested": db.session.in_nested_transaction.return_value = True
    elif fault == "autobegin": db.session.get_transaction.return_value.origin = SessionTransactionOrigin.AUTOBEGIN
    elif fault == "autoflush": db.session.autoflush = True
    elif fault == "dirty": db.session.dirty = {object()}
    elif fault == "bind": db.session.get_bind.return_value = object()
    elif fault == "schema": db.connection.get_execution_options.return_value = {"schema_translate_map": {"public": "other"}}
    elif fault == "isolation": db.connection.get_isolation_level.return_value = "REPEATABLE READ"
    elif fault == "dialect": db.connection.dialect.name = "sqlite"
    else: db.session.is_active = False
    with pytest.raises(writer.WriterRefused): preflight(case)
    case.provider.current_caller.assert_not_called()
    assert not db.queries
    assert_no_mutation(case)


def test_transaction_replaced_during_source_read_refused(case):
    execute = case.db.connection.execute.side_effect
    def changed(statement):
        result = execute(statement)
        if len(case.db.queries) == 3:
            case.db.connection.get_transaction.return_value = SimpleNamespace(is_active=True)
        return result
    case.db.connection.execute.side_effect = changed
    with pytest.raises(writer.WriterRefused): preflight(case)
    assert_no_mutation(case)


@pytest.mark.parametrize("result", [Abstained(AbstentionCode.ZERO_STD, 11, 10), Rejected(RejectionCode.INVALID_INPUT, "snapshot")])
def test_non_computed_never_queries_or_maps(case, result):
    with pytest.raises(writer.WriterRefused):
        preflight(case, plan=replace(case.plan, draft=PredictionDraft(result)))
    case.db.connection.execute.assert_not_called()
    assert_no_mutation(case)


def test_all_write_boundaries_refuse_even_after_successful_preflight(case):
    preflight(case)
    case.db.connection.execute.reset_mock()
    with pytest.raises(writer.WriterRefused):
        with case.port.write(): pytest.fail("unreachable")
    with pytest.raises(writer.WriterRefused):
        case.port.lock_and_reload(case.db.session, plan=case.plan, authorization=case.db.arguments["authorization"], now=case.now)
    with pytest.raises(writer.WriterRefused):
        case.port.reserve_and_stage(case.db.session, key=case.plan.key, draft=case.plan.draft, created_at=case.now)
    with pytest.raises(writer.WriterRefused): case.port.finish(case.db.session)
    case.db.connection.execute.assert_not_called()
    case.read_context.assert_not_called()
    assert_no_mutation(case)


def test_duplicate_restart_and_concurrent_attempts_all_hit_barrier(case):
    # No in-memory reservation masquerading as durable uniqueness.
    def attempt(_):
        with pytest.raises(writer.WriterRefused):
            case.port.reserve_and_stage(case.db.session, key=case.plan.key, draft=case.plan.draft, created_at=case.now)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(attempt, range(12)))
    replacement = writer.P101PostgreSQLWriter(destination=case.port._destination,
        caller_provider=case.provider, read_context=case.read_context)
    with pytest.raises(writer.WriterRefused):
        replacement.reserve_and_stage(case.db.session, key=case.plan.key, draft=case.plan.draft, created_at=case.now)
    case.db.connection.execute.assert_not_called()
    assert_no_mutation(case)


def test_failure_before_commit_has_no_retry_or_sensitive_cause(case):
    case.db.connection.execute.side_effect = RuntimeError("PRIVATE_DATABASE_VALUE")
    with pytest.raises(writer.WriterRefused) as caught: preflight(case)
    assert case.db.connection.execute.call_count == 1
    assert str(caught.value) == "P101_DEV_WRITER_REFUSED"
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert_no_mutation(case)


def test_orchestrator_with_concrete_port_refuses_and_consumes_plan(scenario):
    service, original, request = scenario
    concrete = writer.P101PostgreSQLWriter(
        destination=writer.PostgreSQLDestination("synthetic", "writer", "writer", "192.0.2.1", 5432),
        caller_provider=Mock(), read_context=original.read)
    from app.services.p101_dev_orchestration import P101DevOrchestrator, OrchestrationError
    concrete._provider.current_caller.side_effect = lambda **kwargs: original.current_caller(original.db.session, **kwargs)
    orchestrator = P101DevOrchestrator(port=concrete, clock=lambda: original.db.arguments["observed_at"])
    plan = orchestrator.prepare(**request).prepared
    report = orchestrator.persist(plan)
    assert report.state is PersistenceState.REFUSED and report.prediction_id is None
    with pytest.raises(OrchestrationError): orchestrator.persist(plan)
    assert not original.rows and "stage" not in original.events
