import pandas as pd


class UnifiedAnomalyScorer:

    def build(
        self,
        dataframe: pd.DataFrame,
        *,
        statistical_weight: float = 0.25,
        robust_zscore_weight: float = 0.35,
        isolation_forest_weight: float = 0.40,
        anomaly_threshold: float = 0.6,
    ) -> pd.DataFrame:

        weights = (
            statistical_weight
            + robust_zscore_weight
            + isolation_forest_weight
        )

        if weights <= 0:
            raise ValueError(
                "sum of weights must be greater than 0"
            )

        if any(weight < 0 for weight in (
            statistical_weight,
            robust_zscore_weight,
            isolation_forest_weight,
        )):
            raise ValueError(
                "individual weights must be greater than or equal to 0"
            )

        if not 0 <= anomaly_threshold <= 1:
            raise ValueError(
                "anomaly_threshold must be between 0 and 1"
            )

        if dataframe.empty:
            return dataframe.copy()

        result = dataframe.copy()

        statistical_signal = (
            result["statistical_anomaly"]
            .fillna(False)
            .astype(float)
            if "statistical_anomaly" in result.columns
            else 0.0
        )

        robust_signal = (
            result["robust_zscore_anomaly"]
            .fillna(False)
            .astype(float)
            if "robust_zscore_anomaly" in result.columns
            else 0.0
        )

        isolation_signal = (
            result["isolation_forest_anomaly"]
            .fillna(False)
            .astype(float)
            if "isolation_forest_anomaly" in result.columns
            else 0.0
        )

        result["anomaly_score"] = (
            statistical_signal * statistical_weight
            + robust_signal * robust_zscore_weight
            + isolation_signal * isolation_forest_weight
        ) / weights

        result["is_anomaly"] = (
            result["anomaly_score"]
            >= anomaly_threshold
        )

        return result
