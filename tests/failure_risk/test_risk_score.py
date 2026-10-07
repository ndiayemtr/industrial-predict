import unittest

import pandas as pd
from pandas.testing import assert_series_equal

from app.ml.risk_score import FailureRiskScorer


class RiskScorerTests(unittest.TestCase):
    def test_probabilities_scores_levels_and_exact_boundaries(self):
        source = pd.Series([0, 0.2499, 0.25, 0.4999, 0.5, 0.7499, 0.75, 1], index=[8, 3, 7, 2, 9, 4, 1, 6])
        before = source.copy(deep=True)
        result = FailureRiskScorer().build(source)
        self.assertEqual(result.columns.tolist(), ["failure_probability", "risk_score", "risk_level"])
        assert_series_equal(result.failure_probability, source.rename("failure_probability"))
        assert_series_equal(result.risk_score, (source * 100).rename("risk_score"))
        self.assertEqual(result.risk_level.tolist(), ["low", "low", "medium", "medium", "high", "high", "critical", "critical"])
        self.assertTrue(result.risk_score.between(0, 100).all())
        assert_series_equal(source, before)

    def test_negative_probability(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            FailureRiskScorer().build(pd.Series([0.5, -0.001]))

    def test_probability_above_one(self):
        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            FailureRiskScorer().build(pd.Series([0.5, 1.001]))

    def test_empty_series(self):
        result = FailureRiskScorer().build(pd.Series(dtype=float))
        self.assertTrue(result.empty)
        self.assertEqual(result.columns.tolist(), ["failure_probability", "risk_score", "risk_level"])
