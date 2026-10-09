import unittest
from dataclasses import replace

from app.ml.health_score.classifier import HealthLevelClassifier
from app.ml.health_score.explainer import HealthScoreExplainer
from app.ml.health_score.schemas import HealthScoreComponents


class ClassifierTests(unittest.TestCase):
    def test_all_exact_boundaries(self):
        for score, level in ((100, "healthy"), (85, "healthy"), (84.99, "good"), (70, "good"),
                             (69.99, "degraded"), (50, "degraded"), (49.99, "poor"), (30, "poor"),
                             (29.99, "critical"), (0, "critical")):
            with self.subTest(score=score):
                self.assertEqual(HealthLevelClassifier().classify(score), level)

    def test_outside_interval(self):
        for score in (-0.01, 100.01):
            with self.subTest(score=score), self.assertRaisesRegex(ValueError, "health_score"):
                HealthLevelClassifier().classify(score)


class ExplainerTests(unittest.TestCase):
    def test_weakest_components_sorted_with_default_top_n(self):
        components = HealthScoreComponents(80, 90, 70, 60)
        self.assertEqual(HealthScoreExplainer().explain(components), [
            "maintenance_health is one of the weakest components with a score of 60.00",
            "data_quality_health is one of the weakest components with a score of 70.00"])

    def test_custom_top_n_and_more_than_available(self):
        components = HealthScoreComponents(20, 60, 90, 40)
        explainer = HealthScoreExplainer()
        self.assertEqual(explainer.explain(components, top_n=1), [
            "failure_health is one of the weakest components with a score of 20.00"])
        result = explainer.explain(components, top_n=10)
        self.assertEqual(len(result), 4)
        self.assertEqual([reason.split()[0] for reason in result], [
            "failure_health", "maintenance_health", "anomaly_health", "data_quality_health"])

    def test_invalid_top_n(self):
        for top_n in (0, -1):
            with self.subTest(top_n=top_n), self.assertRaisesRegex(ValueError, "top_n"):
                HealthScoreExplainer().explain(HealthScoreComponents(100, 100, 100, 100), top_n=top_n)

    def test_each_invalid_component(self):
        components = HealthScoreComponents(80, 90, 70, 60)
        for field in ("failure_health", "anomaly_health", "data_quality_health", "maintenance_health"):
            for value in (-0.01, 100.01):
                with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, field):
                    HealthScoreExplainer().explain(replace(components, **{field: value}))
