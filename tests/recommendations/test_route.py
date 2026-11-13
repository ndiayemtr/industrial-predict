"""Protected HTTP contracts with synthetic sessions and SQLite business fixtures.

No dependency override bypasses the production bearer, permission or company
guards. PostgreSQL session storage/configuration are doubles, not qualified I/O.
"""

import base64
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select, func, MetaData, Table, Column, Integer, UniqueConstraint
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.api.routes import equipment
from app.application_session_store import PostgresApplicationSessionStore, SessionStoreRejected, session_reference
from app.b2b_runtime import B2BRouteRuntime
from app.core.authorization import AccountState, CompanyMembership, MembershipState, Permission, Role, VerifiedIdentity
from app.core.caller_session import CurrentCaller, Reason
from app.core.database_runtime import SqlRuntime
from app.core.orm import Base
from app.models.maintenance_recommendation import MaintenanceRecommendation
from app.schemas.maintenance_recommendation import MaintenanceRecommendationRead
from app.schemas.prediction_record import PredictionRecordCreate
from app.schemas.recommendation import RecommendationRead
from app.services.prediction_service import PredictionService
from recommendations.support import START, filter_cases
from dashboard.support import DatabaseCase


SESSION_SECRET = base64.urlsafe_b64encode(b'r' * 32).rstrip(b'=').decode()


@pytest.fixture(autouse=True)
def sqlite_only(monkeypatch):
    # Also close the optional PostgreSQL path in the shared Dashboard fixture.
    monkeypatch.setenv('DASHBOARD_TEST_DATABASE_URL', 'sqlite:///:memory:')
    def forbidden(*args, **kwargs):
        raise AssertionError('PostgreSQL access forbidden in recommendation HTTP tests')
    monkeypatch.setattr(psycopg, 'connect', forbidden)
    monkeypatch.setattr(psycopg.Connection, 'connect', forbidden)
    original = Engine.connect
    def local_connect(engine, *args, **kwargs):
        if engine.dialect.name != 'sqlite':
            forbidden()
        return original(engine, *args, **kwargs)
    monkeypatch.setattr(Engine, 'connect', local_connect)


@pytest.fixture
def db(sqlite_only):
    # B2B metadata contains PostgreSQL-specific CHECKs. Only the eight industrial
    # tables belong in the existing SQLite business fixture, not B2B storage.
    names = ('companies','sites','equipments','sensors','measurements',
             'maintenance_records','prediction_records','maintenance_recommendations')
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False}, hide_parameters=True)
    @event.listens_for(engine, 'connect')
    def foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            # The existing PredictionRecord ORM has a nullable journal FK. Keep
            # its target key present for SQLite's FK resolver, with no journal
            # rows or P101 operations; every prediction here remains unjournaled.
            journal_key = Table('p101_prediction_operations', MetaData(),
                Column('id', Integer, nullable=False), Column('prediction_id', Integer, nullable=False),
                UniqueConstraint('id', 'prediction_id'))
            journal_key.create(connection)
            Base.metadata.create_all(connection, tables=[Base.metadata.tables[name] for name in names])
            with Session(connection, join_transaction_mode='rollback_only') as session:
                DatabaseCase.seed_assets(SimpleNamespace(db=session))
                yield session
            transaction.rollback()
    finally:
        engine.dispose()


def membership(*permissions, company=1, state=MembershipState.ACTIVE):
    return CompanyMembership(17, company, state, Role.COMPANY_ADMIN, frozenset(permissions))


@pytest.fixture
def authority(db, monkeypatch):
    reference = session_reference(SESSION_SECRET)
    identity = VerifiedIdentity(17, 'https://accounts.google.com', 'synthetic-route-subject', AccountState.ACTIVE)
    state = SimpleNamespace(memberships=(membership(Permission.PREDICTIONS_READ, Permission.MAINTENANCE_WRITE),),
                            identity=identity, error=None)
    # Each request gets a separate Session on the shared isolated connection.
    connection = db.connection()
    factory = Mock(side_effect=lambda: Session(connection, autoflush=False, join_transaction_mode='rollback_only'))
    engine = SimpleNamespace(echo=False, hide_parameters=True, logger=Mock())
    engine.logger.isEnabledFor.return_value = False
    sql = SqlRuntime(engine, factory)
    store = PostgresApplicationSessionStore(sql, admission_provider=SimpleNamespace(admit=Mock()), clock=lambda: START)
    def caller(session, *, reference: object, now):
        if state.error:
            raise state.error
        if reference != session_reference(SESSION_SECRET):
            raise SessionStoreRejected(Reason.SESSION_MISMATCH)
        if state.identity.account_state is not AccountState.ACTIVE:
            raise SessionStoreRejected(Reason.ACCOUNT_INACTIVE)
        # Match the store contract: inactive memberships carry no effective grants.
        memberships = tuple(replace(m, permissions=frozenset()) if m.state is MembershipState.INACTIVE
                            else m for m in state.memberships)
        return CurrentCaller(reference, state.identity, memberships, now)
    store.current_caller_in_transaction = Mock(side_effect=caller)
    runtime = B2BRouteRuntime(sql=sql, sessions=store, clock=lambda: START)
    def configure(session):
        # A transport/session double only: SQLite cannot implement SET LOCAL or
        # PostgreSQL lock semantics. The actual authorizer and scope query run.
        assert session.get_bind().dialect.name == 'sqlite'
        assert session.autoflush is False
    monkeypatch.setattr(runtime, '_configure', configure)
    return SimpleNamespace(runtime=runtime, store=store, state=state, factory=factory, reference=reference)


@pytest.fixture
def client(authority):
    app = FastAPI()
    app.include_router(equipment.router, prefix='/api/v1')
    app.state.b2b_runtime = authority.runtime
    with TestClient(app) as test_client:
        test_client.headers['Authorization'] = 'Bearer ' + SESSION_SECRET
        yield test_client


def seed_predictions(db):
    service = PredictionService(db)
    # An older severe RUL must not win over the latest RUL; another equipment
    # must not contribute its severe signal either.
    rows = [(1, "rul", 1., None, START),
            (1, "rul", 48., None, START + timedelta(hours=1)),
            (1, "anomaly", .1, None, START),
            (1, "failure_risk", 99., {"failure_probability": .2}, START),
            (1, "health_score", 90., None, START),
            (2, "rul", 0., None, START + timedelta(days=1))]
    for equipment_id, kind, score, details, timestamp in rows:
        service.create(PredictionRecordCreate(equipment_id=equipment_id, prediction_type=kind,
            score=score, details=details, predicted_at=timestamp))


def test_post_201_schema_and_automatic_persistence(client, db, repository, authority):
    seed_predictions(db)
    response = client.post("/api/v1/equipments/1/recommendations")
    assert response.status_code == 201, response.text
    assert authority.store.current_caller_in_transaction.call_count == 2  # entry + before_commit
    data = response.json()
    assert set(data) == {"equipment_id", "priority", "recommendation_type", "title", "reason",
                         "recommended_action", "signals"}
    assert data["equipment_id"] == 1
    assert data["priority"] == "high"
    assert data["recommendation_type"] == "planned_maintenance"
    assert data["signals"] == dict(anomaly_score=.1, failure_probability=.2, health_score=90., rul_hours=48.)
    assert all(isinstance(data[field], str) and data[field].strip() for field in [
        "title", "reason", "recommended_action"])
    assert RecommendationRead.model_validate(data).model_dump() == data
    db.expunge_all()
    records, total = repository.list_by_equipment(equipment_id=1)
    assert total == len(records) == 1
    saved = MaintenanceRecommendationRead.model_validate(records[0])
    assert saved.model_dump(exclude={"id", "generated_at", "created_at"}) == data
    assert saved.generated_at is not None and saved.created_at is not None
    assert repository.list_by_equipment(equipment_id=2) == ([], 0)


def test_post_partial_signals(client, db, repository):
    PredictionService(db).create(PredictionRecordCreate(equipment_id=1, prediction_type="anomaly",
                                                       score=.5, predicted_at=START))
    response = client.post("/api/v1/equipments/1/recommendations")
    assert response.status_code == 201, response.text
    assert response.json()["recommendation_type"] == "monitoring"
    assert response.json()["signals"] == dict(anomaly_score=.5, failure_probability=None,
                                              health_score=None, rul_hours=None)
    assert repository.list_by_equipment(equipment_id=1)[1] == 1


@pytest.mark.parametrize("method", ["post", "get"])
def test_missing_equipment_refused_by_scope_before_business_lookup(client, repository, method):
    response = getattr(client, method)("/api/v1/equipments/999/recommendations")
    assert response.status_code == 403
    assert response.json() == {"detail": "B2B_FORBIDDEN"}
    assert repository.list_by_equipment(equipment_id=999) == ([], 0)


@pytest.mark.parametrize("unusable_prediction", [False, True])
def test_post_without_usable_signals_422(client, db, repository, unusable_prediction):
    if unusable_prediction:
        PredictionService(db).create(PredictionRecordCreate(equipment_id=1, prediction_type="failure_risk",
            score=90., details={}, predicted_at=START))
    response = client.post("/api/v1/equipments/1/recommendations")
    assert response.status_code == 422
    assert response.json() == {"detail": "At least one recommendation signal is required"}
    assert repository.list_by_equipment(equipment_id=1) == ([], 0)


def test_get_200_exact_pagination_and_item_schema(client, history):
    response = client.get("/api/v1/equipments/1/recommendations")
    assert response.status_code == 200, response.text
    data = response.json()
    assert set(data) == {"items", "page", "page_size", "total", "pages"}
    assert {key: value for key, value in data.items() if key != "items"} == dict(
        page=1, page_size=20, total=4, pages=1)
    assert [item["id"] for item in data["items"]] == [history[name].id for name in [
        "latest", "tie_last", "tie_first", "early"]]
    for item in data["items"]:
        assert set(item) == {"id", "equipment_id", "priority", "recommendation_type", "title",
                             "reason", "recommended_action", "signals", "generated_at", "created_at"}
        assert MaintenanceRecommendationRead.model_validate(item).equipment_id == 1


@pytest.mark.parametrize("page,names", [(1, ["latest", "tie_last"]),
                                       (2, ["tie_first", "early"]), (3, [])])
def test_get_pagination(client, history, page, names):
    response = client.get("/api/v1/equipments/1/recommendations", params={"page": page, "page_size": 2})
    assert response.status_code == 200, response.text
    data = response.json()
    assert [item["id"] for item in data["items"]] == [history[name].id for name in names]
    assert (data["page"], data["page_size"], data["total"], data["pages"]) == (page, 2, 4, 2)


@pytest.mark.parametrize("filters,names", filter_cases())
def test_get_all_filters_and_filtered_totals(client, history, filters, names):
    params = {key: value.isoformat() if hasattr(value, "isoformat") else value for key, value in filters.items()}
    params["page_size"] = 1
    response = client.get("/api/v1/equipments/1/recommendations", params=params)
    assert response.status_code == 200, response.text
    data = response.json()
    assert [item["id"] for item in data["items"]] == [history[name].id for name in names[:1]]
    assert data["total"] == len(names)
    assert data["pages"] == len(names)


def test_get_empty_existing_equipment(client):
    response = client.get("/api/v1/equipments/1/recommendations")
    assert response.status_code == 200
    assert response.json() == dict(items=[], page=1, page_size=20, total=0, pages=0)


@pytest.mark.parametrize("params,field", [
    ({"page": 0}, "page"), ({"page": -1}, "page"), ({"page": "invalid"}, "page"),
    ({"page_size": 0}, "page_size"), ({"page_size": -1}, "page_size"),
    ({"page_size": 101}, "page_size"), ({"page_size": "invalid"}, "page_size"),
    ({"priority": "urgent"}, "priority"), ({"recommendation_type": "shutdown"}, "recommendation_type"),
    ({"start_time": "invalid"}, "start_time"), ({"end_time": "invalid"}, "end_time"),
])
def test_get_query_validation_422(client, params, field):
    response = client.get("/api/v1/equipments/1/recommendations", params=params)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", field]


@pytest.mark.parametrize("page_size", [1, 100])
def test_page_size_boundaries_are_accepted(client, page_size):
    response = client.get("/api/v1/equipments/1/recommendations", params={"page": 1, "page_size": page_size})
    assert response.status_code == 200
    assert response.json()["page_size"] == page_size


def test_openapi_response_models(client):
    schema = client.get("/openapi.json").json()
    path = schema["paths"]["/api/v1/equipments/{equipment_id}/recommendations"]
    assert path["post"]["responses"]["201"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RecommendationRead"}
    get_schema = path["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    assert schema["components"]["schemas"][get_schema]["properties"]["items"]["items"] == {
        "$ref": "#/components/schemas/MaintenanceRecommendationRead"}


@pytest.fixture
def denied_business(db, monkeypatch):
    """Deny cases must not instantiate a business service or emit any DML."""
    reads, writes = Mock(), Mock()
    monkeypatch.setattr(equipment, 'MaintenanceRecommendationService', reads)
    monkeypatch.setattr(equipment, 'RecommendationService', writes)
    statements = []
    connection = db.connection()
    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split(None, 1)[0].upper())
    event.listen(connection, 'before_cursor_execute', capture)
    before = db.scalar(select(func.count()).select_from(MaintenanceRecommendation))
    try:
        yield
        reads.assert_not_called()
        writes.assert_not_called()
        assert db.scalar(select(func.count()).select_from(MaintenanceRecommendation)) == before
        assert not {'INSERT', 'UPDATE', 'DELETE'} & set(statements)
    finally:
        event.remove(connection, 'before_cursor_execute', capture)


@pytest.mark.parametrize('method', ['get', 'post'])
@pytest.mark.parametrize('header', [None, 'Bearer invalid', 'Bearer a.b.c'])
def test_missing_or_malformed_session_is_401_before_sql(client, authority, denied_business, method, header):
    client.headers.pop('Authorization')
    response = getattr(client, method)('/api/v1/equipments/1/recommendations',
                                     headers={} if header is None else {'Authorization': header})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == 'Bearer'
    authority.factory.assert_not_called()
    authority.store.current_caller_in_transaction.assert_not_called()


@pytest.mark.parametrize('method', ['get', 'post'])
def test_unregistered_canonical_session_is_401(client, authority, denied_business, method):
    unknown = base64.urlsafe_b64encode(b'u' * 32).rstrip(b'=').decode()
    response = getattr(client, method)('/api/v1/equipments/1/recommendations',
                                     headers={'Authorization': 'Bearer ' + unknown})
    assert response.status_code == 401


@pytest.mark.parametrize('method', ['get', 'post'])
def test_revoked_session_is_401(client, authority, denied_business, method):
    authority.state.error = SessionStoreRejected(Reason.REVOKED)
    assert getattr(client, method)('/api/v1/equipments/1/recommendations').status_code == 401


@pytest.mark.parametrize('method', ['get', 'post'])
@pytest.mark.parametrize('authenticated', [False, True])
def test_missing_runtime_never_falls_back_to_get_db(client, authority, denied_business, method, authenticated):
    del client.app.state.b2b_runtime
    if not authenticated:
        client.headers.pop('Authorization')
    response = getattr(client, method)('/api/v1/equipments/1/recommendations')
    assert response.status_code == (503 if authenticated else 401)
    authority.factory.assert_not_called()
    authority.store.current_caller_in_transaction.assert_not_called()


@pytest.mark.parametrize('method', ['get', 'post'])
@pytest.mark.parametrize('fault', ['no_grants', 'inactive_membership', 'foreign_company', 'suspended_user'])
def test_valid_session_without_active_company_permission_is_403(client, authority, denied_business, method, fault):
    if fault == 'no_grants':
        authority.state.memberships = (membership(),)
    elif fault == 'inactive_membership':
        authority.state.memberships = (membership(Permission.PREDICTIONS_READ, Permission.MAINTENANCE_WRITE,
                                                 state=MembershipState.INACTIVE),)
    elif fault == 'foreign_company':
        authority.state.memberships = (membership(Permission.PREDICTIONS_READ, Permission.MAINTENANCE_WRITE, company=2),)
    else:
        authority.state.identity = replace(authority.state.identity, account_state=AccountState.SUSPENDED)
    assert getattr(client, method)('/api/v1/equipments/1/recommendations').status_code == 403


@pytest.mark.parametrize('permissions', [(Permission.PREDICTIONS_READ,), (Permission.MAINTENANCE_WRITE,)])
def test_post_requires_both_explicit_permissions(client, authority, denied_business, permissions):
    authority.state.memberships = (membership(*permissions),)
    assert client.post('/api/v1/equipments/1/recommendations').status_code == 403


def test_permissions_cannot_be_combined_between_companies(client, authority, denied_business):
    authority.state.memberships = (membership(Permission.PREDICTIONS_READ, company=1),
                                   membership(Permission.MAINTENANCE_WRITE, company=2))
    assert client.post('/api/v1/equipments/1/recommendations').status_code == 403


@pytest.mark.parametrize('method', ['get', 'post'])
def test_client_scope_parameters_cannot_authorize_foreign_equipment(client, denied_business, method):
    # Fixture equipment 4 belongs to company 2; this caller has only company 1.
    response = getattr(client, method)('/api/v1/equipments/4/recommendations',
        params={'company_id': 1, 'user_id': 17, 'role': 'company_admin'})
    assert response.status_code == 403


def test_read_requires_no_maintenance_write_grant(client, authority):
    authority.state.memberships = (membership(Permission.PREDICTIONS_READ),)
    response = client.get('/api/v1/equipments/1/recommendations')
    assert response.status_code == 200
    assert response.json()['items'] == []
