import pandas as pd

from sklearn.linear_model import LogisticRegression


class FailureRiskBaselineClassifier:

    def __init__(self):
        self.model = LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
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

        if y.nunique() < 2:
            raise ValueError(
                "y must contain at least two classes"
            )

        self.model.fit(
            X,
            y,
        )

    def predict(
        self,
        X: pd.DataFrame,
    ) -> pd.Series:

        predictions = self.model.predict(
            X
        )

        return pd.Series(
            predictions,
            index=X.index,
            name="failure_prediction",
        )

    def predict_proba(
        self,
        X: pd.DataFrame,
    ) -> pd.Series:

        probabilities = (
            self.model.predict_proba(X)[:, 1]
        )

        return pd.Series(
            probabilities,
            index=X.index,
            name="failure_probability",
        )
        