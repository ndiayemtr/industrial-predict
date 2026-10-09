from datetime import timedelta, timezone

from predictions.support import PredictionCase, START, as_utc
from app.schemas.prediction_record import PredictionRecordRead


class PredictionRepositoryTests(PredictionCase):
    def test_create_roundtrips_all_fields_and_json(self):
        measurement = self.measurement()
        source = dict(sensor_id=1, measurement_id=measurement.id, prediction_type="failure_risk",
            score=75, level="high", is_alert=True, model_name="rf", model_version="v2",
            horizon_hours=24, details={"probability": 0.75, "nested": {"values": [1, True, None]}})
        record = self.prediction(**source)
        record_id = record.id
        self.assertIsNotNone(record_id)
        self.db.expunge_all()
        loaded = self.predictions.get_by_id(record_id)
        for field, expected in source.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(loaded, field), expected)
        self.assertEqual(as_utc(loaded.predicted_at), START)
        self.assertEqual(as_utc(loaded.created_at), START)
        self.assertEqual(PredictionRecordRead.model_validate(loaded).id, record_id)

    def test_get_by_id_missing(self):
        self.assertIsNone(self.predictions.get_by_id(999))

    def test_equipment_history_order_by_timestamp_then_id_desc(self):
        self.seed_predictions()
        self.assertEqual(self.ids(self.predictions.get_by_equipment_id(1)),
                         self.ids([self.latest, self.tie_last, self.tie_first, self.early]))
        self.assertEqual(self.ids(self.predictions.get_by_equipment_id(2)), [self.foreign.id])
        self.assertEqual(self.predictions.get_by_equipment_id(999), [])

    def test_equipment_and_type_filter_and_order(self):
        self.seed_predictions()
        # Same type and time: later id must win.
        tie = self.prediction(predicted_at=self.tie_last.predicted_at)
        self.assertEqual(self.ids(self.predictions.get_by_equipment_and_type(1, "anomaly")),
                         self.ids([tie, self.tie_last, self.early]))
        self.assertEqual(self.predictions.get_by_equipment_and_type(1, "unknown"), [])

    def test_latest_equipment_and_type_uses_id_tiebreak(self):
        self.seed_predictions()
        tie = self.prediction(predicted_at=self.tie_last.predicted_at)
        self.assertEqual(self.predictions.get_latest_by_equipment_and_type(1, "anomaly").id, tie.id)
        self.assertEqual(self.predictions.get_latest_by_equipment_and_type(1, "health_score").id, self.latest.id)
        self.assertIsNone(self.predictions.get_latest_by_equipment_and_type(999, "anomaly"))

    def test_pagination_offset_limit_and_empty_page(self):
        self.seed_predictions()
        self.assertEqual(self.ids(self.predictions.get_paginated(equipment_id=1, offset=1, limit=2)),
                         self.ids([self.tie_last, self.tie_first]))
        self.assertEqual(self.predictions.get_paginated(equipment_id=1, offset=10, limit=2), [])

    def test_count_all_scoped_to_equipment(self):
        self.seed_predictions()
        self.assertEqual(self.predictions.count_all(equipment_id=1), 4)
        self.assertEqual(self.predictions.count_all(equipment_id=2), 1)
        self.assertEqual(self.predictions.count_all(equipment_id=999), 0)

    def test_all_filters_on_both_items_and_count(self):
        self.seed_predictions()
        for filters, expected in self.filter_cases():
            with self.subTest(filters=filters):
                result = self.predictions.get_paginated(equipment_id=1, offset=0, limit=100, **filters)
                self.assertEqual(self.ids(result), self.ids(expected))
                self.assertEqual(self.predictions.count_all(equipment_id=1, **filters), len(expected))

    def test_postgresql_timezone_offsets_compare_instants(self):
        if self.engine.dialect.name != "postgresql":
            self.skipTest("Requires DASHBOARD_TEST_DATABASE_URL (PostgreSQL timestamptz; SQLite drops offsets)")
        offset_time = START.astimezone(timezone(timedelta(hours=5, minutes=30)))
        record = self.prediction(predicted_at=offset_time)
        rows = self.predictions.get_paginated(equipment_id=1, offset=0, limit=10, start_time=START, end_time=START)
        self.assertEqual(self.ids(rows), [record.id])
        self.assertEqual(as_utc(rows[0].predicted_at), START)
        self.assertEqual(self.predictions.count_all(equipment_id=1, start_time=START, end_time=START), 1)
