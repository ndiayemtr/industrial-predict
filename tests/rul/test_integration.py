import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_db
from app.data_pipeline.rul_dataset import RULDatasetBuilder
from app.main import app
from app.ml.rul_classifier import RULLevelClassifier
from app.ml.rul_evaluator import RULEvaluator
from app.ml.rul_model_store import RULModelStore
from app.ml.rul_preparer import RULPreparer
from app.ml.rul_random_forest_regressor import RULRandomForestRegressor
from app.repositories.prediction_repository import PredictionRepository


def test_training_to_api_and_automatic_repository_persistence(db, tmp_path, monkeypatch):
    measurements = pd.DataFrame({"equipment_id": [1, 1, 1, 1],
        "timestamp": pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-05"], utc=True),
        "temperature": [90., 80., 70., 60.], "vibration": [4., 3., 2., 1.]})
    maintenance = pd.DataFrame({"equipment_id": [1], "maintenance_type": ["corrective"],
                                "started_at": ["2026-01-04T00:00:00Z"]})
    dataset = RULDatasetBuilder().build(measurements, maintenance)
    X, y = RULPreparer().prepare(dataset)
    assert y.tolist() == [72., 48., 24.]
    assert X.columns.tolist() == ["temperature", "vibration"]
    model = RULRandomForestRegressor(n_estimators=10, max_features=None)
    model.fit(X, y)
    assert RULEvaluator().evaluate(y, model.predict(X))["mae"] >= 0.
    path = tmp_path / "trained" / "rul.joblib"
    RULModelStore().save(model, path)
    monkeypatch.setattr(settings, "rul_model_path", path)
    expected = float(model.predict(pd.DataFrame({"temperature": [80.], "vibration": [3.]})).iloc[0])
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/equipments/1/rul", json={
                "features": {"vibration": 3., "temperature": 80.}})
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
    assert response.status_code == 200, response.text
    assert response.json() == {"equipment_id": 1, "rul_hours": expected,
                               "rul_level": RULLevelClassifier().classify(expected)}
    db.expunge_all()
    repository = PredictionRepository(db)
    records = repository.get_by_equipment_id(1)
    assert len(records) == 1
    record = records[0]
    assert record.prediction_type == "rul"
    assert record.score == pytest.approx(expected)
    assert record.level == response.json()["rul_level"]
    assert record.model_name == "rul_random_forest"
    assert record.details == {"rul_hours": expected}
