import unittest

from evaluation import evaluate_window
from operational import iter_comparable_windows
from prototype import CADENCE_SECONDS, Selection


def sample_selection():
    target = 2_000_000_000
    refs = tuple(range(10))
    return Selection(target_index=10, reference_indices=refs,
                     deadline_seconds=tuple(target - day * CADENCE_SECONDS for day in range(10, 0, -1)),
                     offsets_seconds=(0,) * 10)


def raw_rows(values, timestamps=None):
    if timestamps is None:
        timestamps = [f"2025-01-{index + 1:02d} 12:00:00" for index in range(11)]
    result = {}
    for index, value in enumerate(values):
        line = index + 2
        result[line] = {"": str(index + 1), "timestamp": timestamps[index],
                        "Oil_temperature": str(value)}
    return result


class EvaluationTests(unittest.TestCase):
    def test_operational_selection_is_independent_of_temperature_values(self):
        target = 2_000_000_000
        times = [target - day * CADENCE_SECONDS for day in range(10, 0, -1)] + [target]
        selected_a = tuple(iter_comparable_windows(times, [3] * 11, [0] * 11))
        selected_b = tuple(iter_comparable_windows(times, [3] * 11, [0] * 11))
        self.assertEqual(selected_a, selected_b)
        self.assertEqual(len(selected_a), 1)

    def test_mean_sample_stddev_and_strict_three_sigma_comparison(self):
        result = evaluate_window(sample_selection(), raw_rows([0] * 9 + [1, 20]))
        self.assertEqual(result.status, "EVALUABLE")
        self.assertAlmostEqual(result.reference_mean_c, 0.1)
        self.assertAlmostEqual(result.reference_sample_stddev_c, 0.1 ** 0.5)
        self.assertAlmostEqual(result.target_absolute_deviation_c, 19.9)
        self.assertTrue(result.thermal_deviation_flag)
        below_threshold = evaluate_window(sample_selection(), raw_rows([0] * 9 + [1, 1]))
        self.assertFalse(below_threshold.thermal_deviation_flag)

    def test_zero_reference_sample_deviation_abstains(self):
        result = evaluate_window(sample_selection(), raw_rows([4.5] * 10 + [30]))
        self.assertEqual(result.status, "ABSTAINED")
        self.assertEqual(result.abstention_reason, "zero_reference_sample_stddev")
        self.assertIsNone(result.thermal_deviation_flag)

    def test_invalid_or_nonfinite_selected_temperature_abstains(self):
        values = [1.0] * 10 + [2.0]
        rows = raw_rows(values)
        rows[7]["Oil_temperature"] = "NaN"
        result = evaluate_window(sample_selection(), rows)
        self.assertEqual(result.status, "ABSTAINED")
        self.assertEqual(result.abstention_reason, "invalid_or_nonfinite_temperature")

    def test_source_row_ids_timestamps_values_and_nonqualified_status_are_preserved(self):
        values = [f"{50 + index}.1200" for index in range(10)] + ["75.5000"]
        timestamps = [f"2020-02-{index + 1:02d} 08:27:25" for index in range(11)]
        result = evaluate_window(sample_selection(), raw_rows(values, timestamps))
        self.assertEqual(result.target.temperature_original, "75.5000")
        self.assertEqual(result.target.timestamp_original, timestamps[-1])
        self.assertEqual(result.target.source_row_id, "11")
        self.assertEqual(result.references[0].temperature_original, "50.1200")
        self.assertEqual(result.references[0].offset_seconds, 0)
        self.assertEqual(result.quality_status, "NON QUALIFIÉ")
        self.assertTrue(all(row.quality_status == "NON QUALIFIÉ" for row in result.references))


if __name__ == "__main__":
    unittest.main()
