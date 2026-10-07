import unittest

import pandas as pd

from app.ml.evaluator import FailureRiskEvaluator


class EvaluatorTests(unittest.TestCase):
    def test_metrics_confusion_matrix_and_roc_auc(self):
        # TN=2, FP=1, FN=1, TP=2. Eight of nine positive/negative pairs ordered.
        result = FailureRiskEvaluator().evaluate(pd.Series([0, 0, 0, 1, 1, 1]),
                                                 pd.Series([0, 0, 1, 0, 1, 1]),
                                                 pd.Series([0.1, 0.2, 0.6, 0.4, 0.8, 0.9]))
        for key in ("accuracy", "precision", "recall", "f1"):
            with self.subTest(metric=key):
                self.assertAlmostEqual(result[key], 2 / 3)
        for key, expected in (("true_negative", 2), ("false_positive", 1),
                              ("false_negative", 1), ("true_positive", 2)):
            self.assertEqual(result[key], expected)
        self.assertAlmostEqual(result["roc_auc"], 8 / 9)

    def test_asymmetric_metrics_do_not_swap_precision_and_recall(self):
        result = FailureRiskEvaluator().evaluate(pd.Series([0, 0, 1, 1, 1]), pd.Series([0, 1, 1, 1, 1]))
        self.assertAlmostEqual(result["accuracy"], 0.8)
        self.assertAlmostEqual(result["precision"], 0.75)
        self.assertEqual(result["recall"], 1)
        self.assertAlmostEqual(result["f1"], 6 / 7)

    def test_single_class_has_no_auc_and_fixed_binary_confusion_matrix(self):
        for label in (0, 1):
            with self.subTest(label=label):
                result = FailureRiskEvaluator().evaluate(pd.Series([label, label]), pd.Series([label, label]), pd.Series([label, label]))
                self.assertIsNone(result["roc_auc"])
                self.assertEqual(result["accuracy"], 1)
                self.assertEqual(result["true_negative"], 2 if label == 0 else 0)
                self.assertEqual(result["true_positive"], 2 if label == 1 else 0)
                self.assertEqual(result["false_negative"], 0)
                self.assertEqual(result["false_positive"], 0)

    def test_auc_without_probabilities_is_none(self):
        result = FailureRiskEvaluator().evaluate(pd.Series([0, 1]), pd.Series([0, 1]))
        self.assertIsNone(result["roc_auc"])

    def test_no_predicted_positive_has_zero_precision_recall_f1(self):
        result = FailureRiskEvaluator().evaluate(pd.Series([0, 1]), pd.Series([0, 0]))
        for key in ("precision", "recall", "f1"):
            self.assertEqual(result[key], 0)

    def test_incompatible_prediction_length(self):
        with self.assertRaisesRegex(ValueError, "y_true and y_pred"):
            FailureRiskEvaluator().evaluate(pd.Series([0, 1]), pd.Series([0]))

    def test_incompatible_probability_length(self):
        with self.assertRaisesRegex(ValueError, "y_true and y_proba"):
            FailureRiskEvaluator().evaluate(pd.Series([0, 1]), pd.Series([0, 1]), pd.Series([0.1]))

    def test_empty_y_true(self):
        with self.assertRaisesRegex(ValueError, "y_true must not be empty"):
            FailureRiskEvaluator().evaluate(pd.Series(dtype="int8"), pd.Series(dtype="int8"))
