from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal
from sklearn.exceptions import NotFittedError

from app.ml.rul_baseline_regressor import RULBaselineRegressor
from app.ml.rul_random_forest_regressor import RULRandomForestRegressor
from app.ml.rul_evaluator import RULEvaluator


def test_baseline_predicts_median_and_preserves_index(training_data):
    X, y = training_data
    model = RULBaselineRegressor()
    assert model.fit(X, y) is None
    assert model.model.strategy == "median"
    # Median 48 differs from mean 96, so this catches a changed strategy.
    expected = pd.Series([48.] * len(X), index=X.index, name="rul_prediction_hours")
    assert_series_equal(model.predict(X), expected)


def test_baseline_empty_prediction_does_not_require_fit():
    assert_series_equal(RULBaselineRegressor().predict(pd.DataFrame()),
                        pd.Series(dtype="float64", name="rul_prediction_hours"))


@pytest.mark.parametrize("model_class", [RULBaselineRegressor, RULRandomForestRegressor])
@pytest.mark.parametrize("invalid, message", [("X", "X must not be empty"),
                                              ("y", "y must not be empty"),
                                              ("length", "same number of rows")])
def test_fit_validation(model_class, invalid, message, training_data):
    X, y = training_data
    if invalid == "X":
        X = pd.DataFrame()
    elif invalid == "y":
        y = pd.Series(dtype="float64")
    else:
        y = y.iloc[:-1]
    model = model_class()
    model.model = Mock()
    with pytest.raises(ValueError, match=message):
        model.fit(X, y)
    model.model.fit.assert_not_called()


@pytest.mark.parametrize("model_class", [RULBaselineRegressor, RULRandomForestRegressor])
def test_predict_before_fit(model_class, training_data):
    with pytest.raises(NotFittedError):
        model_class().predict(training_data[0])


def test_random_forest_fit_predict(training_data):
    X, y = training_data
    before_x, before_y = X.copy(deep=True), y.copy(deep=True)
    model = RULRandomForestRegressor(n_estimators=7, max_depth=3, min_samples_leaf=1,
                                     max_features=None, random_state=17)
    assert model.fit(X, y) is None
    result = model.predict(X)
    assert_series_equal(result, pd.Series(model.model.predict(X), index=X.index,
                                         name="rul_prediction_hours"))
    assert result.ge(0).all()
    assert len(model.model.estimators_) == 7
    assert model.model.random_state == 17
    assert_frame_equal(X, before_x)
    assert_series_equal(y, before_y)


def test_random_forest_clips_negative_predictions(training_data):
    model = RULRandomForestRegressor()
    model.model = Mock()
    model.model.predict.return_value = np.array([-10., 0., 8.])
    X = training_data[0].iloc[:3]
    assert_series_equal(model.predict(X), pd.Series([0., 0., 8.], index=X.index,
                                                   name="rul_prediction_hours"))


def test_random_forest_rejects_negative_targets(training_data):
    X, y = training_data
    y.iloc[0] = -1.
    with pytest.raises(ValueError, match="non-negative RUL"):
        RULRandomForestRegressor().fit(X, y)


def test_feature_importances_are_named_sorted_and_normalized(fitted_model, training_data):
    result = fitted_model.feature_importances(training_data[0].columns.tolist())
    assert result.columns.tolist() == ["feature", "importance"]
    assert result.feature.tolist() == ["value", "constant"]
    assert result.importance.tolist() == pytest.approx([1., 0.])
    assert result.importance.is_monotonic_decreasing
    assert result.importance.sum() == pytest.approx(1.)
    assert result.index.tolist() == [0, 1]


@pytest.mark.parametrize("names", [[], ["one"], ["one", "two", "three"]])
def test_feature_importances_wrong_length(fitted_model, names):
    with pytest.raises(ValueError, match="feature_names length"):
        fitted_model.feature_importances(names)


def test_evaluator_exact_metrics():
    # Errors [-1, 1, -2]: MAE 4/3, MSE 2, SSE 6 and SST 8 => R2 .25.
    result = RULEvaluator().evaluate(pd.Series([1., 3., 5.]), pd.Series([2., 2., 7.]))
    assert result == pytest.approx({"mae": 4 / 3, "rmse": np.sqrt(2), "r2": .25})
    assert all(isinstance(value, float) for value in result.values())


def test_evaluator_perfect_predictions():
    y = pd.Series([0., 24., 168.])
    assert RULEvaluator().evaluate(y, y) == {"mae": 0., "rmse": 0., "r2": 1.}


@pytest.mark.parametrize("actual,predicted,message", [
    ([], [1.], "y_true must not be empty"),
    ([1.], [], "y_pred must not be empty"),
    ([1., 2.], [1.], "same number of rows"),
])
def test_evaluator_invalid_data(actual, predicted, message):
    with pytest.raises(ValueError, match=message):
        RULEvaluator().evaluate(pd.Series(actual, dtype="float64"),
                                pd.Series(predicted, dtype="float64"))
