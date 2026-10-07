import unittest
from datetime import timedelta, timezone

import pandas as pd
from pandas.testing import assert_frame_equal

from app.data_pipeline.failure_labeler import FailureLabeler
from failure_risk.support import START, maintenance, measurements


class FailureLabelerTests(unittest.TestCase):
    def test_invalid_horizon_even_on_empty_measurements(self):
        for source in (pd.DataFrame(), measurements()):
            for horizon in (0, -1):
                with self.subTest(empty=source.empty, horizon=horizon), self.assertRaisesRegex(ValueError, "horizon_hours"):
                    FailureLabeler().build(source, maintenance(), horizon_hours=horizon)

    def test_empty_measurements_add_typed_label_columns(self):
        for source in (pd.DataFrame(), measurements().iloc[:0]):
            before = source.copy(deep=True)
            result = FailureLabeler().build(source, pd.DataFrame())
            self.assertTrue(result.empty)
            self.assertEqual(result.columns.tolist(), source.columns.tolist() + [
                "failure_within_horizon", "next_failure_at", "time_to_failure_hours"])
            self.assertEqual(str(result.next_failure_at.dtype), "datetime64[ns, UTC]")
            self.assertEqual(str(result.time_to_failure_hours.dtype), "Float64")
            assert_frame_equal(source, before)

    def test_missing_measurement_columns(self):
        for column in ("equipment_id", "timestamp"):
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                FailureLabeler().build(measurements().drop(columns=column), maintenance())

    def test_missing_maintenance_columns(self):
        for column in ("equipment_id", "maintenance_type", "started_at"):
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, column):
                FailureLabeler().build(measurements(), maintenance().drop(columns=column))

    def test_corrective_within_and_exactly_at_horizon(self):
        result = FailureLabeler().build(measurements((0, 12)), maintenance((24,)))
        self.assertEqual(result.failure_within_horizon.tolist(), [1, 1])
        self.assertEqual(result.next_failure_at.tolist(), [pd.Timestamp(START + timedelta(hours=24))] * 2)
        self.assertEqual(result.time_to_failure_hours.tolist(), [24, 12])

    def test_corrective_outside_horizon_has_no_label_or_failure_metadata(self):
        result = FailureLabeler().build(measurements((0,)), maintenance((24.001,)))
        self.assertEqual(result.failure_within_horizon.tolist(), [0])
        self.assertTrue(result.next_failure_at.isna().all())
        self.assertTrue(result.time_to_failure_hours.isna().all())

    def test_noncorrective_maintenance_does_not_label(self):
        for kind in ("preventive", "inspection", "predictive"):
            with self.subTest(kind=kind):
                result = FailureLabeler().build(measurements((0,)), maintenance((1,), kind=kind))
                self.assertEqual(result.failure_within_horizon.tolist(), [0])
                self.assertTrue(result.next_failure_at.isna().all())

    def test_past_and_simultaneous_failures_are_not_future(self):
        result = FailureLabeler().build(measurements((0,)), maintenance((-2, 0)))
        self.assertEqual(result.failure_within_horizon.tolist(), [0])
        self.assertTrue(result.next_failure_at.isna().all())

    def test_multiple_failures_choose_nearest_future_per_equipment(self):
        source = pd.concat([measurements((0, 15)), measurements((0,), equipment=20)], ignore_index=True)
        records = pd.concat([maintenance((20, -1, 10)), maintenance((3,), equipment=20)], ignore_index=True)
        before_source, before_records = source.copy(deep=True), records.copy(deep=True)
        result = FailureLabeler().build(source, records)
        self.assertEqual(result.failure_within_horizon.tolist(), [1, 1, 1])
        self.assertEqual(result.time_to_failure_hours.tolist(), [10, 5, 3])
        self.assertEqual(result.next_failure_at.tolist(), [pd.Timestamp(START + timedelta(hours=h)) for h in (10, 20, 3)])
        assert_frame_equal(source, before_source)
        assert_frame_equal(records, before_records)

    def test_empty_valid_maintenance_and_invalid_started_at_are_ignored(self):
        records = maintenance()
        records["started_at"] = ["invalid-date"]
        for candidate in (maintenance(()), records):
            result = FailureLabeler().build(measurements(), candidate)
            self.assertEqual(result.failure_within_horizon.tolist(), [0, 0, 0])
            self.assertTrue(result.next_failure_at.isna().all())

    def test_utc_conversion_compares_instants_across_offsets(self):
        source = measurements((0, 0))
        source["timestamp"] = [START.astimezone(timezone(timedelta(hours=5, minutes=30))),
                               START.astimezone(timezone(timedelta(hours=-4)))]
        records = maintenance((2,))
        records["started_at"] = [(START + timedelta(hours=2)).astimezone(timezone(timedelta(hours=-7)))]
        result = FailureLabeler().build(source, records, horizon_hours=2)
        self.assertEqual(str(result.timestamp.dt.tz), "UTC")
        self.assertEqual(str(result.next_failure_at.dt.tz), "UTC")
        self.assertEqual(result.timestamp.tolist(), [pd.Timestamp(START)] * 2)
        self.assertEqual(result.time_to_failure_hours.tolist(), [2, 2])
        self.assertEqual(result.failure_within_horizon.tolist(), [1, 1])

    def test_dst_offset_change_uses_elapsed_time_not_wall_clock(self):
        source = measurements((0,))
        source["timestamp"] = [pd.Timestamp("2026-03-29T01:30:00+01:00")]
        records = maintenance()
        records["started_at"] = [pd.Timestamp("2026-03-29T03:30:00+02:00")]
        result = FailureLabeler().build(source, records, horizon_hours=1)
        self.assertEqual(result.failure_within_horizon.tolist(), [1])
        self.assertEqual(result.time_to_failure_hours.tolist(), [1])
        self.assertEqual(result.next_failure_at.iloc[0], pd.Timestamp("2026-03-29T01:30:00Z"))

    def test_naive_timestamps_are_interpreted_as_utc(self):
        source = measurements((0,))
        source["timestamp"] = [START.replace(tzinfo=None)]
        records = maintenance((1,))
        records["started_at"] = [(START + timedelta(hours=1)).replace(tzinfo=None)]
        result = FailureLabeler().build(source, records)
        self.assertEqual(result.timestamp.iloc[0], pd.Timestamp(START))
        self.assertEqual(result.time_to_failure_hours.tolist(), [1])

    def test_repeated_indices_do_not_contaminate_labels_between_equipment(self):
        # Concatenated sensor/equipment frames commonly retain duplicate indices.
        source = pd.concat([measurements((0,), equipment=10), measurements((0,), equipment=20)])
        result = FailureLabeler().build(source, maintenance((1,), equipment=10))
        self.assertEqual(result.index.tolist(), [0, 0])
        self.assertEqual(result.failure_within_horizon.tolist(), [1, 0])
        self.assertEqual(result.time_to_failure_hours.iloc[0], 1)
        self.assertTrue(pd.isna(result.time_to_failure_hours.iloc[1]))
        self.assertTrue(pd.isna(result.next_failure_at.iloc[1]))

    def test_repeated_indices_keep_distinct_next_failures_within_equipment(self):
        source = measurements((0, 12, 48))
        source.index = [7, 7, 7]
        before = source.copy(deep=True)
        result = FailureLabeler().build(source, maintenance((1, 15)))
        self.assertEqual(result.index.tolist(), [7, 7, 7])
        self.assertEqual(result.failure_within_horizon.tolist(), [1, 1, 0])
        self.assertEqual(result.time_to_failure_hours.iloc[:2].tolist(), [1, 3])
        self.assertEqual(result.next_failure_at.iloc[:2].tolist(), [
            pd.Timestamp(START + timedelta(hours=1)), pd.Timestamp(START + timedelta(hours=15))])
        self.assertTrue(pd.isna(result.time_to_failure_hours.iloc[2]))
        self.assertTrue(pd.isna(result.next_failure_at.iloc[2]))
        assert_frame_equal(source, before)
