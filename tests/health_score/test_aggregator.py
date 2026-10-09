import unittest
from dataclasses import replace

from app.ml.health_score.aggregator import HealthScoreAggregator
from app.ml.health_score.schemas import HealthScoreComponents, HealthScoreWeights


COMPONENTS = HealthScoreComponents(80, 90, 70, 60)


class AggregatorTests(unittest.TestCase):
    def test_default_weights_produce_expected_score(self):
        self.assertEqual(HealthScoreAggregator().calculate(COMPONENTS), 78.5)
        self.assertEqual(HealthScoreAggregator().calculate(COMPONENTS, HealthScoreWeights()), 78.5)

    def test_each_component_outside_interval(self):
        for field in ("failure_health", "anomaly_health", "data_quality_health", "maintenance_health"):
            for value in (-0.01, 100.01):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                    HealthScoreAggregator().calculate(replace(COMPONENTS, **{field: value}))

    def test_component_endpoints_and_rounding(self):
        aggregator = HealthScoreAggregator()
        self.assertEqual(aggregator.calculate(HealthScoreComponents(0, 0, 0, 0)), 0)
        self.assertEqual(aggregator.calculate(HealthScoreComponents(100, 100, 100, 100)), 100)
        self.assertEqual(aggregator.calculate(HealthScoreComponents(80.1234, 90, 70, 60)), 78.55)

    def test_each_negative_weight_even_when_total_is_one(self):
        fields = ("failure_risk", "anomaly", "data_quality", "maintenance")
        for field in fields:
            values = {name: 0.0 for name in fields}
            values[field] = -0.1
            values[next(name for name in fields if name != field)] = 1.1
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, field):
                HealthScoreAggregator().calculate(COMPONENTS, HealthScoreWeights(**values))

    def test_weight_sum_must_be_one(self):
        for weights in (HealthScoreWeights(0, 0, 0, 0), HealthScoreWeights(0.3, 0.3, 0.15, 0.15),
                        HealthScoreWeights(0.5, 0.3, 0.15, 0.15)):
            with self.subTest(weights=weights), self.assertRaisesRegex(ValueError, "sum to 1.0"):
                HealthScoreAggregator().calculate(COMPONENTS, weights)

    def test_valid_custom_and_zero_individual_weights(self):
        aggregator = HealthScoreAggregator()
        self.assertEqual(aggregator.calculate(COMPONENTS, HealthScoreWeights(0.25, 0.25, 0.25, 0.25)), 75)
        self.assertEqual(aggregator.calculate(COMPONENTS, HealthScoreWeights(1, 0, 0, 0)), 80)
