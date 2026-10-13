from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.schemas.maintenance_recommendation import MaintenanceRecommendationRead
from app.schemas.prediction_record import PredictionRecordCreate
from app.schemas.recommendation import RecommendationRead
from app.services.prediction_service import PredictionService
from recommendations.support import START, filter_cases


@pytest.fixture
def client(db):
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


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


def test_post_201_schema_and_automatic_persistence(client, db, repository):
    seed_predictions(db)
    response = client.post("/api/v1/equipments/1/recommendations")
    assert response.status_code == 201, response.text
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
def test_missing_equipment_404(client, repository, method):
    response = getattr(client, method)("/api/v1/equipments/999/recommendations")
    assert response.status_code == 404
    assert response.json() == {"detail": "Equipment not found"}
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
