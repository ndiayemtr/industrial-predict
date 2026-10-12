from dataclasses import FrozenInstanceError

import pytest
from pydantic import ValidationError

from app.ml.rul_schemas import RULPredictionResult
from app.schemas.rul import RULPredictionRead, RULPredictionRequest


def test_prediction_result_is_immutable():
    result = RULPredictionResult(24., "critical")
    with pytest.raises(FrozenInstanceError):
        result.rul_hours = 72.


def test_request_numeric_features():
    assert RULPredictionRequest(features={"value": 2, "active": True}).features == {
        "value": 2., "active": 1.}


@pytest.mark.parametrize("overrides", [{"equipment_id": 0}, {"equipment_id": -1}, {"rul_hours": -1.}])
def test_response_constraints(overrides):
    values = dict(equipment_id=1, rul_hours=0., rul_level="critical")
    values.update(overrides)
    with pytest.raises(ValidationError):
        RULPredictionRead(**values)
