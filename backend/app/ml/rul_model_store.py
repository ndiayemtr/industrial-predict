from pathlib import Path

import joblib

from app.ml.rul_random_forest_regressor import (
    RULRandomForestRegressor,
)


class RULModelStore:

    def save(
        self,
        model: RULRandomForestRegressor,
        path: str | Path,
    ) -> None:

        destination = Path(path)
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        joblib.dump(
            model,
            destination,
        )

    def load(
        self,
        path: str | Path,
    ) -> RULRandomForestRegressor:

        source = Path(path)

        if not source.exists():
            raise FileNotFoundError(
                f"RUL model artifact not found: {source}"
            )

        model = joblib.load(
            source
        )

        if not isinstance(
            model,
            RULRandomForestRegressor,
        ):
            raise TypeError(
                "Invalid RUL model artifact"
            )

        return model