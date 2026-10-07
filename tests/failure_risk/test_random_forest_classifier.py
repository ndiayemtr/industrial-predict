import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal
from sklearn.exceptions import NotFittedError

from app.ml.random_forest_classifier import FailureRiskRandomForestClassifier
from failure_risk.support import training_data


class RandomForestClassifierTests(unittest.TestCase):
    def test_fit_predict_and_probabilities_with_real_model(self):
        X, y = training_data()
        before_x, before_y = X.copy(deep=True), y.copy(deep=True)
        classifier = FailureRiskRandomForestClassifier(n_estimators=20)
        self.assertIsNone(classifier.fit(X, y))
        predicted = classifier.predict(X)
        assert_series_equal(predicted, y.astype(predicted.dtype).rename("failure_prediction"))
        probabilities = classifier.predict_proba(X)
        self.assertEqual(probabilities.name, "failure_probability")
        self.assertEqual(probabilities.index.tolist(), X.index.tolist())
        self.assertTrue(probabilities.between(0, 1).all())
        np.testing.assert_allclose(probabilities, classifier.model.predict_proba(X)[:, 1])
        assert_frame_equal(X, before_x)
        assert_series_equal(y, before_y)

    def test_feature_importances_are_named_sorted_and_normalized(self):
        X, y = training_data()
        classifier = FailureRiskRandomForestClassifier(n_estimators=20)
        classifier.fit(X, y)
        result = classifier.feature_importances(X.columns.tolist())
        self.assertEqual(result.columns.tolist(), ["feature", "importance"])
        self.assertEqual(result.feature.tolist(), ["value", "constant"])
        self.assertEqual(result.importance.tolist(), [1, 0])
        self.assertEqual(result.index.tolist(), [0, 1])
        self.assertAlmostEqual(result.importance.sum(), 1)

    def test_custom_hyperparameters_configure_fitted_trees(self):
        X, y = training_data()
        classifier = FailureRiskRandomForestClassifier(n_estimators=7, max_depth=2,
                                                       min_samples_leaf=2, max_features=1, random_state=17)
        classifier.fit(X, y)
        self.assertEqual(len(classifier.model.estimators_), 7)
        self.assertEqual(classifier.model.random_state, 17)
        self.assertEqual(classifier.model.class_weight, "balanced")
        for tree in classifier.model.estimators_:
            self.assertEqual(tree.max_depth, 2)
            self.assertLessEqual(tree.get_depth(), 2)
            self.assertEqual(tree.min_samples_leaf, 2)
            self.assertEqual(tree.max_features_, 1)

    def test_max_features_variants_are_supported(self):
        X, y = training_data()
        for max_features, expected in (("sqrt", 1), (0.5, 1), (None, 2)):
            with self.subTest(max_features=max_features):
                classifier = FailureRiskRandomForestClassifier(n_estimators=3, max_features=max_features)
                classifier.fit(X, y)
                self.assertEqual(classifier.model.estimators_[0].max_features_, expected)

    def test_default_hyperparameters(self):
        params = FailureRiskRandomForestClassifier().model.get_params()
        for parameter, expected in (("n_estimators", 200), ("max_depth", None),
                                    ("min_samples_leaf", 1), ("max_features", "sqrt")):
            self.assertEqual(params[parameter], expected)

    def test_empty_x(self):
        _, y = training_data()
        with self.assertRaisesRegex(ValueError, "X must not be empty"):
            FailureRiskRandomForestClassifier().fit(pd.DataFrame(), y)

    def test_empty_y(self):
        X, _ = training_data()
        with self.assertRaisesRegex(ValueError, "y must not be empty"):
            FailureRiskRandomForestClassifier().fit(X, pd.Series(dtype="int8"))

    def test_incompatible_lengths(self):
        X, y = training_data()
        with self.assertRaisesRegex(ValueError, "same number of rows"):
            FailureRiskRandomForestClassifier().fit(X, y.iloc[:-1])

    def test_single_class(self):
        X, y = training_data()
        for label in (0, 1):
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "two classes"):
                FailureRiskRandomForestClassifier().fit(X, y * 0 + label)

    def test_feature_names_wrong_length(self):
        X, y = training_data()
        classifier = FailureRiskRandomForestClassifier(n_estimators=3)
        classifier.fit(X, y)
        for names in ([], ["one"], ["one", "two", "three"]):
            with self.subTest(names=names), self.assertRaisesRegex(ValueError, "feature_names length"):
                classifier.feature_importances(names)

    def test_predict_before_fit(self):
        X, _ = training_data()
        classifier = FailureRiskRandomForestClassifier()
        for method in (classifier.predict, classifier.predict_proba):
            with self.assertRaises(NotFittedError):
                method(X)
