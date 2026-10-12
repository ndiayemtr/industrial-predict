import pandas as pd

from sqlalchemy.orm import Session

from app.core.config import settings
from app.ml.rul_model_store import RULModelStore
from app.repositories.equipment_repository import EquipmentRepository
from app.schemas.rul import (
    RULPredictionRead,
    RULPredictionRequest,
)
from app.services.rul_service import RULService


class RULPredictionService:

    def __init__(self, db: Session):
        self.equipment_repository = EquipmentRepository(db)
        self.model_store = RULModelStore()

    def predict_for_equipment(
        self,
        equipment_id: int,
        data: RULPredictionRequest,
    ) -> RULPredictionRead:

        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        model = self.model_store.load(
            settings.rul_model_path
        )

        expected_features = list(
            model.model.feature_names_in_
        )

        provided_features = list(
            data.features.keys()
        )

        missing_features = [
            feature
            for feature in expected_features
            if feature not in data.features
        ]

        unexpected_features = [
            feature
            for feature in provided_features
            if feature not in expected_features
        ]

        if missing_features:
            raise ValueError(
                "Missing RUL features: "
                + ", ".join(missing_features)
            )

        if unexpected_features:
            raise ValueError(
                "Unexpected RUL features: "
                + ", ".join(unexpected_features)
            )

        features = pd.DataFrame(
            [data.features],
            columns=expected_features,
        )

        service = RULService(
            model
        )

        results = service.predict(
            features
        )

        if not results:
            raise ValueError(
                "No RUL prediction produced"
            )

        result = results[0]

        return RULPredictionRead(
            equipment_id=equipment.id,
            rul_hours=result.rul_hours,
            rul_level=result.rul_level,
        )