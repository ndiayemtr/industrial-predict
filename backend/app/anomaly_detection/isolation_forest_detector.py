import pandas as pd

from sklearn.ensemble import IsolationForest


class IsolationForestAnomalyDetector:

    DEFAULT_FEATURES = [
        "value",
        "rolling_mean",
        "rolling_std",
        "value_delta",
        "rate_of_change",
        "trend_slope",
        "rolling_range",
        "rolling_cv",
    ]

    def detect(
        self,
        dataframe: pd.DataFrame,
        *,
        contamination: float = 0.05,
        random_state: int = 42,
        features: list[str] | None = None,
    ) -> pd.DataFrame:

        if not 0 < contamination <= 0.5:
            raise ValueError(
                "contamination must be greater than 0 "
                "and less than or equal to 0.5"
            )

        if dataframe.empty:
            return dataframe.copy()

        selected_features = (
            features
            if features is not None
            else self.DEFAULT_FEATURES
        )

        missing_columns = (
            set(selected_features)
            - set(dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        result = dataframe.copy()

        feature_frame = (
            result[selected_features]
            .apply(
                pd.to_numeric,
                errors="coerce",
            )
        )

        valid_mask = feature_frame.notna().all(axis=1)

        result["isolation_forest_score"] = pd.NA
        result["isolation_forest_anomaly"] = False

        valid_features = feature_frame.loc[
            valid_mask
        ]

        if len(valid_features) < 2:
            return result

        model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
        )

        predictions = model.fit_predict(
            valid_features
        )

        raw_scores = (
            -model.score_samples(
                valid_features
            )
        )

        result.loc[
            valid_mask,
            "isolation_forest_score",
        ] = raw_scores

        result.loc[
            valid_mask,
            "isolation_forest_anomaly",
        ] = predictions == -1

        return result