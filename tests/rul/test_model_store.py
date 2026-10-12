import joblib
import pytest
from pandas.testing import assert_series_equal

from app.ml.rul_model_store import RULModelStore
from app.ml.rul_random_forest_regressor import RULRandomForestRegressor


@pytest.mark.parametrize("as_string", [False, True])
def test_save_load_fitted_model_roundtrip(tmp_path, fitted_model, training_data, as_string):
    path = tmp_path / "nested" / "rul_model.joblib"
    argument = str(path) if as_string else path
    store = RULModelStore()
    store.save(fitted_model, argument)
    assert path.is_file()
    loaded = store.load(argument)
    assert isinstance(loaded, RULRandomForestRegressor)
    assert loaded.model.feature_names_in_.tolist() == training_data[0].columns.tolist()
    assert_series_equal(loaded.predict(training_data[0]), fitted_model.predict(training_data[0]))


def test_missing_artifact(tmp_path):
    with pytest.raises(FileNotFoundError, match="RUL model artifact not found"):
        RULModelStore().load(tmp_path / "absent.joblib")


@pytest.mark.parametrize("value", [{"model": "wrong"}, "not a regressor", None])
def test_wrong_artifact_type(tmp_path, value):
    path = tmp_path / "wrong.joblib"
    joblib.dump(value, path)
    with pytest.raises(TypeError, match="Invalid RUL model artifact"):
        RULModelStore().load(path)
