import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.data_pipeline.rul_dataset import RULDatasetBuilder
from app.data_pipeline.rul_labeler import RULLabeler


@pytest.fixture
def measurements():
    return pd.DataFrame({"equipment_id": [1, 1, 2, 3],
                         "timestamp": ["2026-01-01T00:00:00Z"] * 4,
                         "value": [10., 20., 30., 40.]}, index=[7, 7, 9, 12])


@pytest.fixture
def maintenance():
    return pd.DataFrame([
        (1, "corrective", "2026-01-03T00:00:00Z"),
        (1, "preventive", "2026-01-01T01:00:00Z"),
        (1, "CORRECTIVE", "2026-01-02T06:30:00Z"),
        (1, "corrective", None),
        (1, "corrective", "invalid"),
        (1, "corrective", "2025-12-31T00:00:00Z"),
        (2, "corrective", "2026-01-01T03:00:00Z"),
    ], columns=["equipment_id", "maintenance_type", "started_at"])


def test_next_corrective_failure_is_chronological_and_equipment_scoped(measurements, maintenance):
    before_x, before_m = measurements.copy(deep=True), maintenance.copy(deep=True)
    result = RULLabeler().build(measurements, maintenance)
    assert result.rul_hours.iloc[:3].tolist() == [30.5, 30.5, 3.]
    assert pd.isna(result.rul_hours.iloc[3])
    assert pd.isna(result.next_failure_at.iloc[3])
    assert result.next_failure_at.iloc[0] == pd.Timestamp("2026-01-02T06:30:00Z")
    assert result.index.tolist() == measurements.index.tolist()
    assert str(result.rul_hours.dtype) == "Float64"
    assert str(result.next_failure_at.dtype) == "datetime64[ns, UTC]"
    assert_frame_equal(measurements, before_x)
    assert_frame_equal(maintenance, before_m)


@pytest.mark.parametrize("kind,started", [
    ("preventive", "2026-01-02T00:00:00Z"),
    ("inspection", "2026-01-02T00:00:00Z"),
    ("corrective", None), ("corrective", "invalid"),
    ("corrective", "2026-01-01T00:00:00Z"),
    ("corrective", "2025-12-31T00:00:00Z"),
])
def test_noncorrective_missing_start_or_nonfuture_failure_is_censored(measurements, kind, started):
    records = pd.DataFrame({"equipment_id": [1], "maintenance_type": [kind], "started_at": [started]})
    assert RULLabeler().build(measurements, records).rul_hours.isna().all()


def test_no_maintenance_is_censored(measurements, maintenance):
    assert RULLabeler().build(measurements, maintenance.iloc[:0]).rul_hours.isna().all()


def test_timestamp_offsets_use_the_same_instant():
    measurements = pd.DataFrame({"equipment_id": [1], "timestamp": ["2026-01-01T02:00:00+02:00"]})
    records = pd.DataFrame({"equipment_id": [1], "maintenance_type": ["corrective"],
                            "started_at": ["2026-01-01T04:00:00+01:00"]})
    assert RULLabeler().build(measurements, records).rul_hours.iloc[0] == 3.


@pytest.mark.parametrize("column", ["equipment_id", "timestamp"])
def test_labeler_missing_measurement_column(measurements, maintenance, column):
    with pytest.raises(ValueError, match=column):
        RULLabeler().build(measurements.drop(columns=column), maintenance)


@pytest.mark.parametrize("column", ["equipment_id", "maintenance_type", "started_at"])
def test_labeler_missing_maintenance_column(measurements, maintenance, column):
    with pytest.raises(ValueError, match=column):
        RULLabeler().build(measurements, maintenance.drop(columns=column))


def test_labeler_empty_measurements():
    result = RULLabeler().build(pd.DataFrame(), pd.DataFrame())
    assert result.empty
    assert result.columns.tolist() == ["next_failure_at", "rul_hours"]


def test_builder_labels_features_and_summarizes(measurements, maintenance):
    builder = RULDatasetBuilder()
    result = builder.build(measurements, maintenance)
    assert_frame_equal(result, RULLabeler().build(measurements, maintenance))
    assert result.value.tolist() == [10., 20., 30., 40.]
    assert builder.summarize(result) == dict(row_count=4, labeled_count=3,
                                           unlabeled_count=1, labeled_ratio=0.75)


@pytest.mark.parametrize("values,expected", [([1., 2.], (2, 0, 1.)), ([None, None], (0, 2, 0.))])
def test_summary_all_labeled_or_censored(values, expected):
    labeled, unlabeled, ratio = expected
    assert RULDatasetBuilder().summarize(pd.DataFrame({"rul_hours": values})) == dict(
        row_count=2, labeled_count=labeled, unlabeled_count=unlabeled, labeled_ratio=ratio)


def test_builder_empty_dataset():
    source = pd.DataFrame(columns=["value"])
    result = RULDatasetBuilder().build(source, pd.DataFrame())
    assert result is not source
    assert_frame_equal(result, source)
    assert RULDatasetBuilder().summarize(result) == dict(row_count=0, labeled_count=0,
                                                       unlabeled_count=0, labeled_ratio=0.)


@pytest.mark.parametrize("column", ["equipment_id", "timestamp"])
def test_builder_missing_feature_column(measurements, maintenance, column):
    with pytest.raises(ValueError, match=column):
        RULDatasetBuilder().build(measurements.drop(columns=column), maintenance)


def test_summary_requires_target():
    with pytest.raises(ValueError, match="rul_hours"):
        RULDatasetBuilder().summarize(pd.DataFrame({"value": [1]}))
