import itertools
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch

from app.ml.health_score.anomaly_health import AnomalyHealthCalculator
from app.ml.health_score.data_quality_health import DataQualityHealthCalculator
from app.ml.health_score.failure_health import FailureHealthCalculator
from app.ml.health_score.maintenance_health import MaintenanceHealthCalculator
from app.ml.health_score.schemas import HealthScoreComponents, HealthScoreResult, HealthScoreWeights


class FailureHealthTests(unittest.TestCase):
    def test_endpoints_intermediate_values_and_rounding(self):
        for probability, expected in ((0, 100), (1, 0), (0.25, 75), (0.5, 50), (0.123456, 87.65)):
            with self.subTest(probability=probability):
                self.assertEqual(FailureHealthCalculator().calculate(probability), expected)

    def test_outside_probability_interval(self):
        for probability in (-0.001, 1.001):
            with self.subTest(probability=probability), self.assertRaisesRegex(ValueError, "failure_probability"):
                FailureHealthCalculator().calculate(probability)


class AnomalyHealthTests(unittest.TestCase):
    def test_endpoints_intermediate_values_and_rounding(self):
        for score, expected in ((0, 100), (1, 0), (0.25, 75), (0.5, 50), (0.123456, 87.65)):
            with self.subTest(score=score):
                self.assertEqual(AnomalyHealthCalculator().calculate(score), expected)

    def test_outside_score_interval(self):
        for score in (-0.001, 1.001):
            with self.subTest(score=score), self.assertRaisesRegex(ValueError, "anomaly_score"):
                AnomalyHealthCalculator().calculate(score)


class DataQualityHealthTests(unittest.TestCase):
    def test_all_valid_warning_invalid(self):
        for counts, expected in (((10, 0, 0), 100), ((0, 10, 0), 50), ((0, 0, 10), 0)):
            with self.subTest(counts=counts):
                self.assertEqual(DataQualityHealthCalculator().calculate(
                    valid_count=counts[0], warning_count=counts[1], invalid_count=counts[2]), expected)

    def test_mixture_and_rounding(self):
        self.assertEqual(DataQualityHealthCalculator().calculate(valid_count=6, warning_count=2, invalid_count=2), 70)
        self.assertEqual(DataQualityHealthCalculator().calculate(valid_count=1, warning_count=0, invalid_count=2), 33.33)

    def test_each_negative_count(self):
        for field in ("valid_count", "warning_count", "invalid_count"):
            counts = dict(valid_count=2, warning_count=2, invalid_count=2)
            counts[field] = -1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                DataQualityHealthCalculator().calculate(**counts)

    def test_zero_observations(self):
        with self.assertRaisesRegex(ValueError, "At least one"):
            DataQualityHealthCalculator().calculate(valid_count=0, warning_count=0, invalid_count=0)


class MaintenanceHealthTests(unittest.TestCase):
    def test_no_indicators(self):
        self.assertEqual(MaintenanceHealthCalculator().calculate(), 100)

    def test_individual_penalties(self):
        for field, expected in (("corrective_in_progress", 60), ("overdue_maintenance", 70), ("planned_soon", 90)):
            with self.subTest(field=field):
                self.assertEqual(MaintenanceHealthCalculator().calculate(**{field: True}), expected)

    def test_all_combinations_cumulate_penalties_and_stay_nonnegative(self):
        combinations = list(itertools.product((False, True), repeat=3))
        for indicators, expected in zip(combinations, [100, 90, 70, 60, 60, 50, 30, 20], strict=True):
            with self.subTest(indicators=indicators):
                score = MaintenanceHealthCalculator().calculate(
                    corrective_in_progress=indicators[0], overdue_maintenance=indicators[1], planned_soon=indicators[2])
                self.assertEqual(score, expected)
                self.assertGreaterEqual(score, 0)

    def test_floor_when_penalties_exceed_one_hundred(self):
        calculator = MaintenanceHealthCalculator()
        # Current flags total 80; exercise the defensive floor with a larger penalty.
        with patch.object(calculator, "CORRECTIVE_IN_PROGRESS_PENALTY", 120):
            self.assertEqual(calculator.calculate(corrective_in_progress=True), 0)


class DomainSchemaTests(unittest.TestCase):
    def test_default_weights(self):
        self.assertEqual(HealthScoreWeights(), HealthScoreWeights(0.4, 0.3, 0.15, 0.15))

    def test_immutable_components_weights_and_result(self):
        components = HealthScoreComponents(80, 90, 70, 60)
        result = HealthScoreResult(78.5, "good", components)
        self.assertIs(result.components, components)
        for instance, field in ((components, "failure_health"), (HealthScoreWeights(), "failure_risk"), (result, "health_score")):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(instance, field, 0)
