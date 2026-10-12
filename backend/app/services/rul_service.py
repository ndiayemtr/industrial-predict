import pandas as pd

from app.ml.rul_classifier import RULLevelClassifier
from app.ml.rul_random_forest_regressor import (
    RULRandomForestRegressor,
)
from app.ml.rul_schemas import RULPredictionResult


class RULService:

    def __init__(
        self,
        model: RULRandomForestRegressor,
        classifier: RULLevelClassifier | None = None,
    ):
        self.model = model
        self.classifier = (
            classifier
            if classifier is not None
            else RULLevelClassifier()
        )

    def predict(
        self,
        features: pd.DataFrame,
    ) -> list[RULPredictionResult]:

        if features.empty:
            return []

        predictions = self.model.predict(
            features
        )

        return [
            RULPredictionResult(
                rul_hours=float(rul_hours),
                rul_level=self.classifier.classify(
                    float(rul_hours)
                ),
            )
            for rul_hours in predictions
        ]