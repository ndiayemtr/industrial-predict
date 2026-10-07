import pandas as pd


class StatisticalAnomalyDetector:

    def detect(
        self,
        dataframe: pd.DataFrame,
        *,
        threshold_std: float = 3.0,
    ) -> pd.DataFrame:

        if threshold_std <= 0:
            raise ValueError(
                "threshold_std must be greater than 0"
            )

        if dataframe.empty:
            return dataframe.copy()

        required_columns = {
            "value",
            "rolling_mean",
            "rolling_std",
        }

        missing_columns = (
            required_columns
            - set(dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Missing required columns: "
                + ", ".join(sorted(missing_columns))
            )

        result = dataframe.copy()

        result["statistical_deviation"] = (
            result["value"]
            - result["rolling_mean"]
        ).abs()

        result["statistical_threshold"] = (
            result["rolling_std"]
            * threshold_std
        )

        result["statistical_anomaly"] = (
            result["rolling_std"].notna()
            & (
                result["statistical_deviation"]
                > result["statistical_threshold"]
            )
        )

        return result