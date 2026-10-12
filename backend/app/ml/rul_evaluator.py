import pandas as pd

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)


class RULEvaluator:

    def evaluate(
        self,
        y_true: pd.Series,
        y_pred: pd.Series,
    ) -> dict:

        if y_true.empty:
            raise ValueError(
                "y_true must not be empty"
            )

        if y_pred.empty:
            raise ValueError(
                "y_pred must not be empty"
            )

        if len(y_true) != len(y_pred):
            raise ValueError(
                "y_true and y_pred must have the same number of rows"
            )

        mae = mean_absolute_error(
            y_true,
            y_pred,
        )

        rmse = mean_squared_error(
            y_true,
            y_pred,
        ) ** 0.5

        r2 = r2_score(
            y_true,
            y_pred,
        )

        return {
            "mae": float(mae),
            "rmse": float(rmse),
            "r2": float(r2),
        }