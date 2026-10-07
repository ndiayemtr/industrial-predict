import pandas as pd

from sklearn.ensemble import RandomForestClassifier


class FailureRiskRandomForestClassifier:

    def __init__(
        self,
        *,
        n_estimators: int = 200,
        max_depth: int | None = None,
        min_samples_leaf: int = 1,
        max_features: str | float | int | None = "sqrt",
        random_state: int = 42,
    ):
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_leaf=min_samples_leaf,
            max_features=max_features,
            class_weight="balanced",
            random_state=random_state,
            n_jobs=-1,
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

    def feature_importances(
        self,
        feature_names: list[str],
    ) -> pd.DataFrame:

        if len(feature_names) != len(
            self.model.feature_importances_
        ):
            raise ValueError(
                "feature_names length does not match model features"
            )

        return (
            pd.DataFrame(
                {
                    "feature": feature_names,
                    "importance": self.model.feature_importances_,
                }
            )
            .sort_values(
                by="importance",
                ascending=False,
            )
            .reset_index(drop=True)
        )