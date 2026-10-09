"""Reuse isolated SQL fixtures; seed fixed prediction timestamps and tie cases."""

from datetime import timedelta, timezone

from dashboard.support import DatabaseCase, START
from app.models.prediction_record import PredictionRecord
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction_record import PredictionRecordCreate


def create_data(**overrides):
    values = dict(equipment_id=1, prediction_type="anomaly", score=0.8,
                  predicted_at=START)
    values.update(overrides)
    return PredictionRecordCreate(**values)


def as_utc(value):
    # SQLite drops timezone metadata; PostgreSQL retains aware datetimes.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class PredictionCase(DatabaseCase):
    def setUp(self):
        super().setUp()
        self.predictions = PredictionRepository(self.db)

    def prediction(self, **overrides):
        values = dict(equipment_id=1, prediction_type="anomaly", score=0.8,
                      predicted_at=START, created_at=START)
        values.update(overrides)
        record = PredictionRecord(**values)
        return self.predictions.create(record)

    def seed_predictions(self):
        self.early = self.prediction(level="high", is_alert=True)
        self.tie_first = self.prediction(prediction_type="failure_risk", score=40,
            level="medium", is_alert=False, predicted_at=START + timedelta(hours=1))
        self.tie_last = self.prediction(level="low", is_alert=False,
            predicted_at=START + timedelta(hours=1))
        self.latest = self.prediction(prediction_type="health_score", score=85, level="good",
            predicted_at=START + timedelta(hours=2))
        self.foreign = self.prediction(equipment_id=2, level="high", is_alert=True,
            predicted_at=START + timedelta(hours=3))

    @staticmethod
    def ids(records):
        return [record.id for record in records]

    def filter_cases(self):
        return [
            ({"prediction_type": "anomaly"}, [self.tie_last, self.early]),
            ({"level": "medium"}, [self.tie_first]),
            ({"is_alert": True}, [self.early]),
            ({"is_alert": False}, [self.tie_last, self.tie_first]),
            ({"start_time": START + timedelta(hours=1)}, [self.latest, self.tie_last, self.tie_first]),
            ({"end_time": START + timedelta(hours=1)}, [self.tie_last, self.tie_first, self.early]),
            ({"start_time": START + timedelta(hours=1), "end_time": START + timedelta(hours=1)},
             [self.tie_last, self.tie_first]),
            ({"prediction_type": "anomaly", "level": "low", "is_alert": False,
              "start_time": START, "end_time": START + timedelta(hours=1)}, [self.tie_last]),
            ({"level": "unknown"}, []),
        ]
