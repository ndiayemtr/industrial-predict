import pandas as pd
import pytest
from pandas.testing import assert_frame_equal, assert_series_equal

from app.ml.rul_preparer import RULPreparer


def test_censored_rows_metadata_and_nonnumeric_features_are_removed():
    # Explicit list makes leakage protection independent of the implementation constant.
    forbidden = ["next_failure_at", "failure_within_horizon", "time_to_failure_hours",
                 "measurement_id", "sensor_id", "equipment_id", "site_id", "company_id",
                 "timestamp", "sensor_code", "equipment_code", "site_code", "company_code",
                 "root_cause", "action_taken", "failure_code", "completed_at", "downtime_minutes", "cost"]
    frame = pd.DataFrame({column: [1, 2, 3] for column in forbidden}, index=[9, 4, 8])
    frame["rul_hours"] = pd.array([24., None, 72.], dtype="Float64")
    frame["value"] = [2., 3., 4.]
    frame["count"] = [1, 2, 3]
    frame["active"] = [True, False, False]
    frame["nullable_bool"] = pd.array([True, None, False], dtype="boolean")
    frame["description"] = ["a", "b", "c"]
    frame["numeric_text"] = ["1", "2", "3"]
    frame["category"] = pd.Categorical(["a", "b", "a"])
    frame["date"] = pd.to_datetime(["2026-01-01"] * 3)
    before = frame.copy(deep=True)
    X, y = RULPreparer().prepare(frame)
    assert_frame_equal(X, frame.loc[[9, 8], ["value", "count", "active", "nullable_bool"]])
    assert_series_equal(y, pd.Series([24., 72.], index=[9, 8], name="rul_hours"))
    assert_frame_equal(frame, before)


@pytest.mark.parametrize("frame", [pd.DataFrame(), pd.DataFrame({"rul_hours": [None], "value": [1]})])
def test_empty_or_all_censored_dataset(frame):
    X, y = RULPreparer().prepare(frame)
    assert X.empty and y.empty
    assert y.name == "rul_hours"
    assert y.dtype == "float64"


def test_target_is_required():
    with pytest.raises(ValueError, match="Missing target column: rul_hours"):
        RULPreparer().prepare(pd.DataFrame({"value": [1]}))
