from types import SimpleNamespace
from unittest.mock import create_autospec

import pandas as pd
import pytest

# Reuse the existing safe DB configuration before importing application services.
from dashboard.support import DatabaseCase
from app.ml.rul_model_store import RULModelStore
from app.ml.rul_random_forest_regressor import RULRandomForestRegressor
from app.repositories.equipment_repository import EquipmentRepository
from app.services.prediction_service import PredictionService
from app.services.rul_prediction_service import RULPredictionService


@pytest.fixture
def training_data():
    X = pd.DataFrame({"value": [0., 1., 2., 3., 4., 5.], "constant": [1.] * 6},
                     index=[10, 20, 30, 40, 50, 60])
    return X, pd.Series([0., 12., 24., 72., 168., 300.], index=X.index, name="rul_hours")


@pytest.fixture
def fitted_model(training_data):
    model = RULRandomForestRegressor(n_estimators=10, max_features=None)
    model.fit(*training_data)
    return model


@pytest.fixture
def db():
    case = DatabaseCase(methodName="runTest")
    try:
        case.setUp()
        yield case.db
    finally:
        case.doCleanups()


@pytest.fixture
def prediction_service():
    service = RULPredictionService(None)
    service.equipment_repository = create_autospec(EquipmentRepository, instance=True)
    service.equipment_repository.get_by_id.return_value = SimpleNamespace(id=42)
    service.model_store = create_autospec(RULModelStore, instance=True)
    model = create_autospec(RULRandomForestRegressor, instance=True)
    model.model = SimpleNamespace(feature_names_in_=["temperature", "vibration"])
    model.predict.return_value = pd.Series([48.5], name="rul_prediction_hours")
    service.model_store.load.return_value = model
    service.prediction_service = create_autospec(PredictionService, instance=True)
    return service
