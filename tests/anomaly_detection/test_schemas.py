import unittest

from pydantic import ValidationError

from app.anomaly_detection.schemas import AnomalyResult
from anomaly_detection.support import START


class AnomalyResultTests(unittest.TestCase):
    def result(self, score):
        return AnomalyResult(measurement_id=1, sensor_id=2, timestamp=START,
                             anomaly_score=score, is_anomaly=score >= 0.6, method="unified")

    def test_scores_within_closed_interval_are_accepted(self):
        for score in (0, 0.25, 0.6, 1):
            with self.subTest(score=score):
                self.assertEqual(self.result(score).anomaly_score, score)

    def test_negative_score_is_rejected(self):
        with self.assertRaises(ValidationError) as context:
            self.result(-0.01)
        self.assertEqual(context.exception.errors()[0]["loc"], ("anomaly_score",))

    def test_score_above_one_is_rejected(self):
        with self.assertRaises(ValidationError) as context:
            self.result(1.01)
        self.assertEqual(context.exception.errors()[0]["loc"], ("anomaly_score",))
