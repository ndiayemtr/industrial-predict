from unittest.mock import create_autospec

import pandas as pd
import pytest

from app.ml.rul_classifier import RULLevelClassifier
from app.ml.rul_random_forest_regressor import RULRandomForestRegressor
from app.ml.rul_schemas import RULPredictionResult
from app.services.rul_service import RULService


def test_model_predictions_are_classified_and_mapped():
    model = create_autospec(RULRandomForestRegressor, instance=True)
    model.predict.return_value = pd.Series([24., 72., 168., 169.], index=[5, 8, 2, 1])
    features = pd.DataFrame({"value": [1, 2, 3, 4]}, index=[5, 8, 2, 1])
    result = RULService(model).predict(features)
    assert result == [RULPredictionResult(24., "critical"), RULPredictionResult(72., "warning"),
                      RULPredictionResult(168., "watch"), RULPredictionResult(169., "healthy")]
    assert all(isinstance(row.rul_hours, float) for row in result)
    assert model.predict.call_args.args[0] is features
    model.predict.assert_called_once()


def test_custom_classifier_is_applied():
    model = create_autospec(RULRandomForestRegressor, instance=True)
    model.predict.return_value = pd.Series([10.])
    classifier = RULLevelClassifier(critical_hours=1., warning_hours=2., watch_hours=3.)
    assert RULService(model, classifier).predict(pd.DataFrame({"value": [1]})) == [
        RULPredictionResult(10., "healthy")]


def test_empty_features_do_not_call_model():
    model = create_autospec(RULRandomForestRegressor, instance=True)
    assert RULService(model).predict(pd.DataFrame()) == []
    model.predict.assert_not_called()


def test_negative_model_output_is_rejected():
    model = create_autospec(RULRandomForestRegressor, instance=True)
    model.predict.return_value = pd.Series([-1.])
    with pytest.raises(ValueError, match="non-negative"):
        RULService(model).predict(pd.DataFrame({"value": [1]}))
