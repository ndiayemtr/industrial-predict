import pandas as pd

from sklearn.dummy import DummyRegressor


class RULBaselineRegressor:

    def __init__(self):
        self.model = DummyRegressor(
            strategy="median",
        )

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
    ) -> None:

        if X.empty:
            raise ValueError(
                "X must not be empty"
            )

        if y.empty:
            raise ValueError(
                "y must not be empty"
            )

        if len(X) != len(y):
            raise ValueError(
                "X and y must have the same number of rows"
            )

        self.model.fit(
            X,
            y,
        )

    def predict(
        self,
        X: pd.DataFrame,
    ) -> pd.Series:

        if X.empty:
            return pd.Series(
                dtype="float64",
                name="rul_prediction_hours",
            )

        predictions = self.model.predict(
            X
        )

        return pd.Series(
            predictions,
            index=X.index,
            name="rul_prediction_hours",
            dtype="float64",
        )