import pytest
from fastapi.testclient import TestClient

from app.api.routes import equipment as equipment_routes
from app.core.database import get_db
from app.main import app
from app.schemas.rul import RULPredictionRead


@pytest.fixture
def client(monkeypatch, prediction_service):
    # Keep the real Route -> Service path; mock repositories, model and persistence.
    monkeypatch.setattr(equipment_routes, "RULPredictionService", lambda db: prediction_service)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: None
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def post(client, features=None, equipment_id=42):
    return client.post(f"/api/v1/equipments/{equipment_id}/rul", json={
        "features": {"vibration": 2., "temperature": 80.} if features is None else features})


def test_nominal_response_and_json_schema(client, prediction_service):
    response = post(client)
    assert response.status_code == 200, response.text
    assert response.json() == {"equipment_id": 42, "rul_hours": 48.5, "rul_level": "warning"}
    assert RULPredictionRead.model_validate(response.json()).model_dump() == response.json()
    assert isinstance(response.json()["equipment_id"], int)
    assert isinstance(response.json()["rul_hours"], float)
    assert isinstance(response.json()["rul_level"], str)
    prediction_service.prediction_service.persist_rul.assert_called_once()


def test_missing_equipment_returns_404(client, prediction_service):
    prediction_service.equipment_repository.get_by_id.return_value = None
    response = post(client, equipment_id=999)
    assert response.status_code == 404
    assert response.json() == {"detail": "Equipment not found"}
    prediction_service.model_store.load.assert_not_called()
    prediction_service.prediction_service.persist_rul.assert_not_called()


@pytest.mark.parametrize("features,detail", [
    ({"temperature": 80.}, "Missing RUL features: vibration"),
    ({"temperature": 80., "vibration": 2., "pressure": 3.}, "Unexpected RUL features: pressure"),
])
def test_invalid_model_features_return_422(client, prediction_service, features, detail):
    response = post(client, features)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    prediction_service.model_store.load.return_value.predict.assert_not_called()
    prediction_service.prediction_service.persist_rul.assert_not_called()


def test_missing_model_returns_503(client, prediction_service):
    prediction_service.model_store.load.side_effect = FileNotFoundError("RUL model artifact not found")
    response = post(client)
    assert response.status_code == 503
    assert response.json() == {"detail": "RUL model artifact not found"}
    prediction_service.prediction_service.persist_rul.assert_not_called()


@pytest.mark.parametrize("payload", [{}, {"features": []}, {"features": {"temperature": "invalid"}}])
def test_malformed_request_returns_422_without_service_call(client, prediction_service, payload):
    response = client.post("/api/v1/equipments/42/rul", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][:2] == ["body", "features"]
    prediction_service.equipment_repository.get_by_id.assert_not_called()


def test_openapi_declares_rul_response_schema(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/equipments/{equipment_id}/rul"]["post"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/RULPredictionRead"}
    response_schema = schema["components"]["schemas"]["RULPredictionRead"]
    assert set(response_schema["required"]) == {"equipment_id", "rul_hours", "rul_level"}
    assert response_schema["properties"]["rul_hours"]["minimum"] == 0
