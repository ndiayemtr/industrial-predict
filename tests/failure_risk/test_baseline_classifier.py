import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal
from sklearn.exceptions import NotFittedError

from app.ml.baseline_classifier import FailureRiskBaselineClassifier
from failure_risk.support import training_data


class BaselineClassifierTests(unittest.TestCase):
    def test_fit_predict_and_probabilities_with_real_model(self):
        X, y = training_data()
        before_x, before_y = X.copy(deep=True), y.copy(deep=True)
        classifier = FailureRiskBaselineClassifier()
        self.assertIsNone(classifier.fit(X, y))
        predicted = classifier.predict(X)
        assert_series_equal(predicted, y.astype(predicted.dtype).rename("failure_prediction"))
        probabilities = classifier.predict_proba(X)
        self.assertEqual(probabilities.name, "failure_probability")
        self.assertEqual(probabilities.index.tolist(), X.index.tolist())
        self.assertTrue(probabilities.between(0, 1).all())
        self.assertTrue((probabilities.iloc[:4] < 0.5).all())
        self.assertTrue((probabilities.iloc[4:] > 0.5).all())
        np.testing.assert_allclose(probabilities, classifier.model.predict_proba(X)[:, 1])
        assert_frame_equal(X, before_x)
        assert_series_equal(y, before_y)

    def test_empty_x(self):
        _, y = training_data()
        with self.assertRaisesRegex(ValueError, "X must not be empty"):
            FailureRiskBaselineClassifier().fit(pd.DataFrame(), y)

    def test_empty_y(self):
        X, _ = training_data()
        with self.assertRaisesRegex(ValueError, "y must not be empty"):
            FailureRiskBaselineClassifier().fit(X, pd.Series(dtype="int8"))

    def test_incompatible_lengths(self):
        X, y = training_data()
        with self.assertRaisesRegex(ValueError, "same number of rows"):
            FailureRiskBaselineClassifier().fit(X, y.iloc[:-1])

    def test_single_class(self):
        X, y = training_data()
        for label in (0, 1):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "two classes"):
                FailureRiskBaselineClassifier().fit(X, y * 0 + label)

    def test_predict_before_fit(self):
        X, _ = training_data()
        classifier = FailureRiskBaselineClassifier()
        for method in (classifier.predict, classifier.predict_proba):
            with self.assertRaises(NotFittedError):
                method(X)
