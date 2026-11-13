import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from operational import (
    OPERATIONAL_RULE_VERSION,
    assess_windows,
    build_operational_report,
    classify_motor_current,
    encode_operational_signature,
)
from prototype import CADENCE_SECONDS


def schedule(target):
    timestamps = [target - day * CADENCE_SECONDS for day in range(10, 0, -1)]
    timestamps.append(target)
    return timestamps


class OperationalComparabilityTests(unittest.TestCase):
    def _write_tiny_dataset(self, directory, *, comparable):
        root = Path(directory)
        csv_path = root / "MetroPT3(AirCompressor).csv"
        manifest_path = root / "provenance.json"
        header = [
            "", "timestamp", "Oil_temperature", "COMP", "DV_eletric",
            "Oil_level", "Motor_current",
        ]
        target = datetime(2025, 1, 11, 12, 0)
        rows = []
        for i, day in enumerate(range(10, 0, -1)):
            timestamp = target - timedelta(days=day)
            comp, dv = ("1.0", "0.0") if comparable or i % 2 == 0 else ("0.0", "1.0")
            rows.append([str(10 * (i + 1)), timestamp.isoformat(sep=" "), f"{50 + i}.1250",
                         comp, dv, "1.0", "0.04" if comp == "1.0" else "7.0"])
        rows.append(["110", target.isoformat(sep=" "), "79.2500", "1.0", "0.0", "1.0", "0.04"])
        with csv_path.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(header)
            writer.writerows(rows)
        digest = hashlib.sha256(csv_path.read_bytes()).hexdigest().upper()
        manifest_path.write_text(json.dumps({
            "extracted_files": [{"filename": csv_path.name, "sha256": digest}],
        }), encoding="utf-8")
        return csv_path, manifest_path

    def test_official_digital_definitions_classify_loaded_and_off_or_offloaded(self):
        loaded_low_oil = encode_operational_signature("0.0", "1.0", "1.0", "5.7")
        off_or_offloaded_ok = encode_operational_signature("1.0", "0.0", "0.0", "0.04")
        self.assertNotEqual(loaded_low_oil, 0)
        self.assertNotEqual(off_or_offloaded_ok, 0)
        self.assertNotEqual(loaded_low_oil, off_or_offloaded_ok)

    def test_conflicting_or_nonbinary_digital_states_are_unknown(self):
        self.assertEqual(encode_operational_signature("0", "0", "0", "1"), 0)
        self.assertEqual(encode_operational_signature("1", "1", "1", "1"), 0)
        self.assertEqual(encode_operational_signature("0.5", "1", "0", "1"), 0)
        self.assertEqual(encode_operational_signature("0", "1", "0", "NaN"), 0)

    def test_oil_level_low_is_a_warning_state_not_an_invalid_signature(self):
        oil_low = encode_operational_signature("0", "1", "1", "5.8")
        oil_expected = encode_operational_signature("0", "1", "0", "5.8")
        self.assertNotEqual(oil_low, 0)
        self.assertNotEqual(oil_expected, 0)
        self.assertNotEqual(oil_low, oil_expected)

    def test_all_rows_same_mode_and_oil_flag_are_comparable(self):
        times = schedule(2_000_000_000)
        result = assess_windows(times, [2] * 11, [2] * 11)
        self.assertEqual(result.temporal_windows, 1)
        self.assertEqual(result.digitally_comparable_windows, 1)
        self.assertEqual(result.comparable_windows, 1)
        self.assertEqual(result.unknown_or_conflicting_state, 0)

    def test_mixed_operating_mode_rejects_window(self):
        times = schedule(2_000_000_000)
        states = [1] * 11
        states[4] = 3
        currents = [2] * 11
        currents[4] = 0
        result = assess_windows(times, states, currents)
        self.assertEqual(result.temporal_windows, 1)
        self.assertEqual(result.comparable_windows, 0)
        self.assertEqual(result.mixed_operating_mode, 1)

    def test_mixed_oil_level_flag_rejects_comparability_without_invalidating_rows(self):
        times = schedule(2_000_000_000)
        states = [1] * 11
        states[4] = 2
        result = assess_windows(times, states, [2] * 11)
        self.assertEqual(result.temporal_windows, 1)
        self.assertEqual(result.comparable_windows, 0)
        self.assertEqual(result.mixed_oil_level_flag, 1)

    def test_unknown_operational_state_rejects_window(self):
        times = schedule(2_000_000_000)
        states = [1] * 11
        states[2] = 0
        result = assess_windows(times, states, [2] * 11)
        self.assertEqual(result.comparable_windows, 0)
        self.assertEqual(result.unknown_or_conflicting_state, 1)

    def test_current_category_ties_and_digital_mismatches_are_rejected(self):
        self.assertEqual(classify_motor_current("2.0"), 255)
        self.assertEqual(classify_motor_current("5.5"), 255)
        times = schedule(2_000_000_000)
        mismatched = assess_windows(times, [2] * 11, [2] * 10 + [1])
        self.assertEqual(mismatched.comparable_windows, 0)
        self.assertEqual(mismatched.invalid_or_conflicting_current, 1)

    def test_current_category_must_match_across_window(self):
        times = schedule(2_000_000_000)
        mixed = assess_windows(times, [4] * 11, [0] * 10 + [1])
        self.assertEqual(mixed.digitally_comparable_windows, 1)
        self.assertEqual(mixed.comparable_windows, 0)
        self.assertEqual(mixed.mixed_current_category, 1)

    def test_report_keeps_low_oil_warning_and_nonqualified_status(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            csv_path, manifest_path = self._write_tiny_dataset(directory, comparable=True)
            report = build_operational_report(csv_path, manifest_path)
        self.assertEqual(report.temporal_windows_at_plus_minus_10s, 1)
        self.assertEqual(report.digitally_comparable_windows, 1)
        self.assertEqual(report.operationally_comparable_windows, 1)
        self.assertEqual(report.selected_window.quality_status, "NON QUALIFIÉ")
        self.assertIn("niveau sous la valeur attendue", report.oil_state_warning)
        self.assertIn("pas invalidée", report.oil_state_warning)

    def test_temperature_extremes_cannot_rescue_mixed_operating_modes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as directory:
            csv_path, manifest_path = self._write_tiny_dataset(directory, comparable=False)
            report = build_operational_report(csv_path, manifest_path)
        self.assertEqual(report.temporal_windows_at_plus_minus_10s, 1)
        self.assertEqual(report.digitally_comparable_windows, 0)
        self.assertEqual(report.operationally_comparable_windows, 0)
        self.assertIsNone(report.selected_window)

    def test_first_comparable_window_is_selected_in_time_order_only(self):
        first_target = 2_000_000_000
        second_target = first_target + 20 * CADENCE_SECONDS
        first = schedule(first_target)
        second = schedule(second_target)
        times = first + second
        states = [1] * 11
        states[4] = 3  # first window is mixed; second is consistently off/offloaded
        states.extend([3] * 11)
        currents = [2] * 11
        currents[4] = 0
        currents.extend([0] * 11)
        result = assess_windows(times, states, currents)
        self.assertEqual(result.temporal_windows, 2)
        self.assertEqual(result.comparable_windows, 1)
        self.assertEqual(result.first_comparable_selection.target_index, 21)

    def test_rule_is_versioned_and_has_no_temperature_input(self):
        self.assertEqual(OPERATIONAL_RULE_VERSION, "metropt3-digital-current-oil-comparator-v2")
        self.assertEqual(assess_windows.__code__.co_argcount, 3)


if __name__ == "__main__":
    unittest.main()
