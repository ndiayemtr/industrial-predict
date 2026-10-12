import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.ml.rul_classifier import RULLevelClassifier
from app.ml.rul_prediction_explainer import RULPredictionExplainer


@pytest.mark.parametrize("hours,level", [(0., "critical"), (23.99, "critical"),
    (24., "critical"), (24.01, "warning"), (71.99, "warning"), (72., "warning"),
    (72.01, "watch"), (167.99, "watch"), (168., "watch"), (168.01, "healthy"),
    (1000., "healthy")])
def test_default_threshold_boundaries(hours, level):
    assert RULLevelClassifier().classify(hours) == level


def test_negative_rul_rejected():
    with pytest.raises(ValueError, match="non-negative"):
        RULLevelClassifier().classify(-.01)


@pytest.mark.parametrize("kwargs,message", [
    ({"critical_hours": 0}, "critical_hours"), ({"critical_hours": -1}, "critical_hours"),
    ({"warning_hours": 24}, "warning_hours"), ({"warning_hours": 23}, "warning_hours"),
    ({"watch_hours": 72}, "watch_hours"), ({"watch_hours": 71}, "watch_hours"),
])
def test_constructor_threshold_validation(kwargs, message):
    with pytest.raises(ValueError, match=message):
        RULLevelClassifier(**kwargs)


def test_custom_thresholds():
    classifier = RULLevelClassifier(critical_hours=1, warning_hours=2, watch_hours=3)
    assert [classifier.classify(x) for x in [1, 2, 3, 4]] == ["critical", "warning", "watch", "healthy"]


@pytest.fixture
def importances():
    return pd.DataFrame({"feature": ["pressure", "temperature", "vibration"],
                         "importance": [.1, .6, .3]}, index=[9, 4, 7])


@pytest.mark.parametrize("top_n,count", [(1, 1), (2, 2), (5, 3)])
def test_explainer_sorts_limits_and_formats_percentages(importances, top_n, count):
    before = importances.copy(deep=True)
    result = RULPredictionExplainer().explain_global(importances, top_n=top_n)
    assert result.feature.tolist() == ["temperature", "vibration", "pressure"][:count]
    assert result.importance.tolist() == pytest.approx([.6, .3, .1][:count])
    assert result.importance_percent.tolist() == pytest.approx([60., 30., 10.][:count])
    assert result.index.tolist() == list(range(count))
    assert_frame_equal(importances, before)


def test_text_summary(importances):
    assert RULPredictionExplainer().build_summary(importances, top_n=2) == (
        "Most influential RUL features: temperature (60.0%), vibration (30.0%)")


def test_empty_importances():
    source = pd.DataFrame(columns=["feature", "importance"])
    result = RULPredictionExplainer().explain_global(source)
    assert result is not source
    assert_frame_equal(result, source)
    assert RULPredictionExplainer().build_summary(source) == "No feature importance available."


@pytest.mark.parametrize("method", ["explain_global", "build_summary"])
@pytest.mark.parametrize("top_n", [0, -1])
def test_invalid_top_n(importances, method, top_n):
    with pytest.raises(ValueError, match="top_n"):
        getattr(RULPredictionExplainer(), method)(importances, top_n=top_n)


@pytest.mark.parametrize("column", ["feature", "importance"])
def test_missing_importance_columns(importances, column):
    with pytest.raises(ValueError, match=column):
        RULPredictionExplainer().explain_global(importances.drop(columns=column))
