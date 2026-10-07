import numpy as np
import pandas as pd


class ZScoreAnomalyDetector:

    def detect(
        self,
        dataframe: pd.DataFrame,
        *,
        z_threshold: float = 3.0,
        robust_threshold: float = 3.5,
    ) -> pd.DataFrame:

        if z_threshold <= 0:
            raise ValueError(
                "z_threshold must be greater than 0"
            )

        if robust_threshold <= 0:
            raise ValueError(
                "robust_threshold must be greater than 0"
            )

        if dataframe.empty:
            return dataframe.copy()

        required_columns = {
            "sensor_id",
            "value",
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

        grouped = result.groupby(
            "sensor_id",
            group_keys=False,
        )

        mean = grouped["value"].transform("mean")
        std = grouped["value"].transform("std")

        result["z_score"] = (
            (result["value"] - mean)
            / std
        )

        result.loc[
            std.isna() | (std == 0),
            "z_score",
        ] = np.nan

        median = grouped["value"].transform("median")

        absolute_deviation = (
            result["value"] - median
        ).abs()

        mad = absolute_deviation.groupby(
            result["sensor_id"]
        ).transform("median")

        result["robust_z_score"] = (
            0.6745
            * (result["value"] - median)
            / mad
        )

        result.loc[
            mad.isna() | (mad == 0),
            "robust_z_score",
        ] = np.nan

        result["zscore_anomaly"] = (
            result["z_score"].abs()
            > z_threshold
        )

        result["robust_zscore_anomaly"] = (
            result["robust_z_score"].abs()
            > robust_threshold
        )

        return result