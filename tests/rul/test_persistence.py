from unittest.mock import create_autospec

import pytest

from predictions.support import PredictionCase, START, as_utc
from app.core.enums import PredictionType
from app.ml.rul_schemas import RULPredictionResult
from app.services.prediction_service import PredictionService


@pytest.mark.parametrize("hours,level", [(24., "critical"), (72., "warning"),
                                         (168., "watch"), (240., "healthy")])
def test_persist_rul_mapping_delegates_to_create(hours, level):
    service = PredictionService(None)
    service.create = create_autospec(service.create)
    returned = service.persist_rul(equipment_id=42, result=RULPredictionResult(hours, level),
        predicted_at=START, model_name="custom_rf", model_version="v2")
    service.create.assert_called_once()
    data = service.create.call_args.args[0]
    assert data.equipment_id == 42
    assert data.prediction_type == PredictionType.RUL
    assert data.prediction_type.value == "rul"
    assert data.score == hours
    assert data.level == level
    assert data.model_name == "custom_rf"
    assert data.model_version == "v2"
    assert data.details == {"rul_hours": hours}
    assert data.predicted_at == START
    assert returned is service.create.return_value


class RULPersistenceIntegrationTests(PredictionCase):
    def test_real_repository_roundtrip(self):
        service = PredictionService(self.db)
        record = service.persist_rul(equipment_id=1, result=RULPredictionResult(240.5, "healthy"),
                                    predicted_at=START, model_name="custom_rf", model_version="v2")
        record_id = record.id
        self.db.expunge_all()
        loaded = self.predictions.get_by_id(record_id)
        assert loaded.equipment_id == 1
        assert loaded.prediction_type == "rul"
        assert loaded.score == 240.5
        assert loaded.level == "healthy"
        assert loaded.model_name == "custom_rf"
        assert loaded.model_version == "v2"
        assert loaded.details == {"rul_hours": 240.5}
        assert as_utc(loaded.predicted_at) == START

    def test_defaults_and_zero_rul(self):
        record = PredictionService(self.db).persist_rul(
            equipment_id=1, result=RULPredictionResult(0., "critical"), predicted_at=START)
        assert record.model_name == "rul_random_forest"
        assert record.model_version is None
        assert record.score == 0.
        assert record.level == "critical"
        assert record.details == {"rul_hours": 0.}

    def test_missing_equipment_does_not_write(self):
        with pytest.raises(LookupError, match="Equipment not found"):
            PredictionService(self.db).persist_rul(
                equipment_id=999, result=RULPredictionResult(48., "warning"), predicted_at=START)
        assert self.predictions.count_all(equipment_id=1) == 0
        assert self.predictions.count_all(equipment_id=999) == 0
