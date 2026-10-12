from datetime import datetime, timezone

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.core.config import settings
from app.ml.rul_model_store import RULModelStore
from app.ml.rul_schemas import RULPredictionResult
from app.schemas.rul import RULPredictionRead, RULPredictionRequest


def test_load_order_predict_and_automatic_persistence(prediction_service):
    service = prediction_service
    request = RULPredictionRequest(features={"vibration": 2., "temperature": 80.})
    before = datetime.now(timezone.utc)
    result = service.predict_for_equipment(42, request)
    after = datetime.now(timezone.utc)
    assert isinstance(result, RULPredictionRead)
    assert result.model_dump() == {"equipment_id": 42, "rul_hours": 48.5, "rul_level": "warning"}
    service.equipment_repository.get_by_id.assert_called_once_with(42)
    service.model_store.load.assert_called_once_with(settings.rul_model_path)
    model = service.model_store.load.return_value
    model.predict.assert_called_once()
    assert_frame_equal(model.predict.call_args.args[0],
                       pd.DataFrame({"temperature": [80.], "vibration": [2.]}))
    assert request.features == {"vibration": 2., "temperature": 80.}
    service.prediction_service.persist_rul.assert_called_once()
    args = service.prediction_service.persist_rul.call_args.kwargs
    assert args["equipment_id"] == 42
    assert args["result"] == RULPredictionResult(48.5, "warning")
    assert args["model_name"] == "rul_random_forest"
    assert before <= args["predicted_at"] <= after
    assert args["predicted_at"].tzinfo == timezone.utc


def test_missing_equipment_does_not_load_or_persist(prediction_service):
    prediction_service.equipment_repository.get_by_id.return_value = None
    with pytest.raises(LookupError, match="Equipment not found"):
        prediction_service.predict_for_equipment(999, RULPredictionRequest(features={}))
    prediction_service.equipment_repository.get_by_id.assert_called_once_with(999)
    prediction_service.model_store.load.assert_not_called()
    prediction_service.prediction_service.persist_rul.assert_not_called()


@pytest.mark.parametrize("features,message", [
    ({"temperature": 80.}, "Missing RUL features: vibration"),
    ({"temperature": 80., "vibration": 2., "pressure": 10.}, "Unexpected RUL features: pressure"),
    ({}, "Missing RUL features: temperature, vibration"),
])
def test_invalid_features_do_not_predict_or_persist(prediction_service, features, message):
    with pytest.raises(ValueError, match=message):
        prediction_service.predict_for_equipment(42, RULPredictionRequest(features=features))
    prediction_service.model_store.load.return_value.predict.assert_not_called()
    prediction_service.prediction_service.persist_rul.assert_not_called()


def test_missing_model_does_not_persist(prediction_service):
    prediction_service.model_store.load.side_effect = FileNotFoundError("missing artifact")
    with pytest.raises(FileNotFoundError, match="missing artifact"):
        prediction_service.predict_for_equipment(42, RULPredictionRequest(features={}))
    prediction_service.prediction_service.persist_rul.assert_not_called()


def test_no_prediction_does_not_persist(prediction_service):
    prediction_service.model_store.load.return_value.predict.return_value = pd.Series(dtype="float64")
    with pytest.raises(ValueError, match="No RUL prediction produced"):
        prediction_service.predict_for_equipment(42, RULPredictionRequest(
            features={"temperature": 80., "vibration": 2.}))
    prediction_service.prediction_service.persist_rul.assert_not_called()


def test_service_loads_real_temporary_model(prediction_service, fitted_model, tmp_path, monkeypatch):
    path = tmp_path / "model.joblib"
    RULModelStore().save(fitted_model, path)
    monkeypatch.setattr(settings, "rul_model_path", path)
    prediction_service.model_store = RULModelStore()
    result = prediction_service.predict_for_equipment(42, RULPredictionRequest(
        features={"constant": 1., "value": 2.}))
    expected = fitted_model.predict(pd.DataFrame({"value": [2.], "constant": [1.]})).iloc[0]
    assert result.rul_hours == pytest.approx(expected)
    prediction_service.prediction_service.persist_rul.assert_called_once()
