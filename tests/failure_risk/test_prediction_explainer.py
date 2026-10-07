import unittest

import pandas as pd
from pandas.testing import assert_frame_equal

from app.ml.prediction_explainer import FailureRiskPredictionExplainer


def importances():
    return pd.DataFrame({"feature": ["temperature", "vibration", "pressure", "rate"],
                         "importance": [0.1, 0.6, 0.25, 0.05]}, index=[8, 2, 9, 3])


class PredictionExplainerTests(unittest.TestCase):
    def test_sorted_importances_percentages_and_top_n(self):
        source = importances()
        before = source.copy(deep=True)
        result = FailureRiskPredictionExplainer().explain_global(source, top_n=2)
        self.assertEqual(result.feature.tolist(), ["vibration", "pressure"])
        self.assertEqual(result.importance.tolist(), [0.6, 0.25])
        self.assertEqual(result.importance_percent.tolist(), [60, 25])
        self.assertEqual(result.index.tolist(), [0, 1])
        assert_frame_equal(source, before)

    def test_default_top_n_and_more_requested_than_available(self):
        explainer = FailureRiskPredictionExplainer()
        default = explainer.explain_global(importances())
        self.assertEqual(default.feature.tolist(), ["vibration", "pressure", "temperature", "rate"])
        assert_frame_equal(default, explainer.explain_global(importances(), top_n=10))
        self.assertEqual(len(explainer.explain_global(importances(), top_n=1)), 1)

    def test_invalid_top_n_even_on_empty_frame_and_in_summary(self):
        explainer = FailureRiskPredictionExplainer()
        for source in (pd.DataFrame(), importances()):
            for top_n in (0, -1):
                for method in (explainer.explain_global, explainer.build_summary):
                    with self.subTest(empty=source.empty, top_n=top_n, method=method.__name__), self.assertRaisesRegex(ValueError, "top_n"):
                        method(source, top_n=top_n)

    def test_missing_required_columns(self):
        for column in ("feature", "importance"):
            for method in (FailureRiskPredictionExplainer().explain_global, FailureRiskPredictionExplainer().build_summary):
                with self.subTest(column=column, method=method.__name__), self.assertRaisesRegex(ValueError, column):
                    method(importances().drop(columns=column))

    def test_empty_frame_and_summary(self):
        for source in (pd.DataFrame(), importances().iloc[:0]):
            result = FailureRiskPredictionExplainer().explain_global(source)
            self.assertIsNot(result, source)
            assert_frame_equal(result, source)
            self.assertEqual(FailureRiskPredictionExplainer().build_summary(source), "No feature importance available.")

    def test_summary_text_sorted_top_n_and_rounding(self):
        source = importances()
        self.assertEqual(FailureRiskPredictionExplainer().build_summary(source),
                         "Most influential features: vibration (60.0%), pressure (25.0%), temperature (10.0%)")
        self.assertEqual(FailureRiskPredictionExplainer().build_summary(source, top_n=1),
                         "Most influential features: vibration (60.0%)")
        source = pd.DataFrame({"feature": ["value"], "importance": [0.12345]})
        self.assertEqual(FailureRiskPredictionExplainer().build_summary(source),
                         "Most influential features: value (12.3%)")
