import unittest
from unittest.mock import patch

from app.ml.health_score.calculator import HealthScoreCalculator
from app.ml.health_score.schemas import HealthScoreComponents, HealthScoreResult, HealthScoreWeights
from health_score.support import payload


class CalculatorTests(unittest.TestCase):
    def test_real_orchestration_components_score_and_level(self):
        result = HealthScoreCalculator().calculate(**payload())
        self.assertEqual(result, HealthScoreResult(78.5, "good", HealthScoreComponents(80, 90, 70, 60)))

    def test_best_and_worst_cases(self):
        best = HealthScoreCalculator().calculate(**payload(failure_probability=0, anomaly_score=0,
                    valid_count=1, warning_count=0, invalid_count=0, corrective_in_progress=False))
        self.assertEqual(best.health_score, 100)
        self.assertEqual(best.health_level, "healthy")
        worst = HealthScoreCalculator().calculate(**payload(failure_probability=1, anomaly_score=1,
                    valid_count=0, warning_count=0, invalid_count=1, overdue_maintenance=True, planned_soon=True))
        self.assertEqual(worst.components, HealthScoreComponents(0, 0, 0, 20))
        self.assertEqual(worst.health_score, 3)
        self.assertEqual(worst.health_level, "critical")

    def test_custom_weights(self):
        result = HealthScoreCalculator().calculate(**payload(), weights=HealthScoreWeights(0.25, 0.25, 0.25, 0.25))
        self.assertEqual(result.health_score, 75)
        self.assertEqual(result.health_level, "good")

    def test_real_subcomponent_validation_errors_propagate(self):
        for overrides, message in (({"failure_probability": -0.1}, "failure_probability"),
                                   ({"anomaly_score": 1.1}, "anomaly_score"),
                                   ({"valid_count": -1}, "valid_count"),
                                   ({"valid_count": 0, "warning_count": 0, "invalid_count": 0}, "At least one")):
            with self.subTest(overrides=overrides), self.assertRaisesRegex(ValueError, message):
                HealthScoreCalculator().calculate(**payload(**overrides))
        with self.assertRaisesRegex(ValueError, "sum to 1.0"):
            HealthScoreCalculator().calculate(**payload(), weights=HealthScoreWeights(0, 0, 0, 0))

    def test_maintenance_errors_are_not_swallowed(self):
        calculator = HealthScoreCalculator()
        error = ValueError("maintenance failure")
        with patch.object(calculator.maintenance_health_calculator, "calculate", side_effect=error):
            with self.assertRaises(ValueError) as caught:
                calculator.calculate(**payload())
        self.assertIs(caught.exception, error)
