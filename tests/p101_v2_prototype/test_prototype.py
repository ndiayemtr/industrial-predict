import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import unittest

from prototype import (
    CADENCE_SECONDS,
    POLICY_VERSION,
    TOLERANCE_SECONDS,
    QualificationInputError,
    build_report,
    parse_naive_timestamp,
    select_first_window,
)


def make_schedule(*, offsets=None, missing_day=None, tie_day=None):
    target = 2_000_000_000
    offsets = offsets or {}
    values = []
    for day in range(10, 0, -1):
        due = target - day * CADENCE_SECONDS
        if day == missing_day:
            continue
        if day == tie_day:
            values.extend((due - 5, due + 5))
        else:
            values.append(due + offsets.get(day, 0))
    values.append(target)
    return sorted(values), target


class PrototypeTests(unittest.TestCase):
    def test_inclusive_ten_second_tolerance_is_accepted(self):
        times, _ = make_schedule(offsets={3: 10})
        selected = select_first_window(times)
        self.assertIsNotNone(selected)
        self.assertEqual(max(abs(value) for value in selected.offsets_seconds), 10)
        self.assertIn(10, selected.offsets_seconds)

    def test_observation_outside_tolerance_is_not_selected(self):
        times, _ = make_schedule(offsets={3: 11})
        self.assertIsNone(select_first_window(times))

    def test_equal_distance_candidates_reject_the_window(self):
        times, _ = make_schedule(tie_day=4)
        self.assertIsNone(select_first_window(times))

    def test_missing_daily_reference_rejects_the_window(self):
        times, _ = make_schedule(missing_day=6)
        self.assertIsNone(select_first_window(times))

    def test_duplicate_timestamp_is_rejected(self):
        times, _ = make_schedule()
        times.insert(2, times[2])
        with self.assertRaisesRegex(QualificationInputError, "strictly increasing and unique"):
            select_first_window(times)

    def test_each_source_observation_is_used_once_inside_window(self):
        times, _ = make_schedule(offsets={day: (-1 if day % 2 else 1) for day in range(1, 11)})
        selected = select_first_window(times)
        self.assertIsNotNone(selected)
        chosen = (selected.target_index, *selected.reference_indices)
        self.assertEqual(len(chosen), 11)
        self.assertEqual(len(set(chosen)), 11)

    def test_source_timestamp_with_offset_is_not_mislabeled_utc(self):
        with self.assertRaisesRegex(QualificationInputError, "source-naive"):
            parse_naive_timestamp("2020-01-01T00:00:00+00:00")

    def test_report_preserves_original_fields_and_marks_quality_unqualified(self):
        with self.subTest("authentic raw strings survive report construction"):
            import tempfile

            with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
                tmp_path = Path(directory)
                csv_path = tmp_path / "MetroPT3(AirCompressor).csv"
                manifest_path = tmp_path / "provenance.json"
                target = datetime(2025, 1, 11, 12, 0, 0)
                header = [
                    "", "timestamp", "TP2", "TP3", "H1", "DV_pressure", "Reservoirs",
                    "Oil_temperature", "Motor_current", "COMP", "DV_eletric", "Towers",
                    "MPG", "LPS", "Pressure_switch", "Oil_level", "Caudal_impulses",
                ]
                rows = []
                for day in range(10, 0, -1):
                    when = target - timedelta(days=day)
                    rows.append([
                        str(day * 10), when.isoformat(sep=" "), "1", "2", "3", "4", "5",
                        f"{50 + day}.123400", "5.5", "0.0", "1.0", "0.0", "0.0", "0.0",
                        "0.0", "1.0", "0.0",
                    ])
                rows.append([
                    "110", target.isoformat(sep=" "), "1", "2", "3", "4", "5", "77.500000",
                    "5.8", "0.0", "1.0", "0.0", "0.0", "0.0", "0.0", "1.0", "0.0",
                ])
                with csv_path.open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(header)
                    writer.writerows(rows)
                digest = hashlib.sha256(csv_path.read_bytes()).hexdigest().upper()
                manifest_path.write_text(json.dumps({
                    "extracted_files": [{"filename": csv_path.name, "sha256": digest}],
                }), encoding="utf-8")

                report = build_report(csv_path, manifest_path)
                self.assertEqual(report.policy_version, POLICY_VERSION)
                self.assertEqual(report.target.timestamp_original, target.isoformat(sep=" "))
                self.assertEqual(report.target.temperature_original, "77.500000")
                self.assertEqual(report.target.temperature_value, 77.5)
                self.assertEqual(report.target.csv_line, 12)
                self.assertTrue(report.references[0].temperature_original.endswith(".123400"))
                self.assertEqual(report.references[0].unit, "°C")
                self.assertTrue(report.no_duplicate_timestamps)
                self.assertTrue(report.no_reused_rows_within_window)
                self.assertEqual(report.quality_status, "NON QUALIFIÉ")
                self.assertEqual(report.target.quality_status, "NON QUALIFIÉ")
                self.assertTrue(report.exploratory_statistics["interpretation"].startswith("statistique expérimentale"))

    def test_v2_protocol_is_distinct_and_does_not_call_v1(self):
        source = Path(__file__).with_name("prototype.py").read_text(encoding="utf-8")
        self.assertTrue(POLICY_VERSION.startswith("p101-v2-"))
        self.assertEqual(TOLERANCE_SECONDS, 10)
        self.assertNotIn("app.p101_dev", source)
        self.assertNotIn("evaluate_snapshot", source)
        self.assertNotIn("evaluate(", source)


if __name__ == "__main__":
    unittest.main()
