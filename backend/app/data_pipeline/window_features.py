import pandas as pd


class WindowFeatureBuilder:

    def build(
        self,
        dataframe: pd.DataFrame,
        *,
        window_size: int = 3,
    ) -> pd.DataFrame:

        if window_size < 1:
            raise ValueError(
                "window_size must be greater than or equal to 1"
            )
            
        
        if dataframe.empty:
            return dataframe.copy()

        result = dataframe.copy()

        result = result.sort_values(
            by=[
                "sensor_id",
                "timestamp",
                "measurement_id",
            ]
        ).reset_index(drop=True)

        grouped = result.groupby(
            "sensor_id",
            group_keys=False,
        )

        result["rolling_mean"] = grouped["value"].transform(
            lambda series: series.rolling(
                window=window_size,
                min_periods=1,
            ).mean()
        )

        result["rolling_min"] = grouped["value"].transform(
            lambda series: series.rolling(
                window=window_size,
                min_periods=1,
            ).min()
        )

        result["rolling_max"] = grouped["value"].transform(
            lambda series: series.rolling(
                window=window_size,
                min_periods=1,
            ).max()
        )

        result["rolling_std"] = grouped["value"].transform(
            lambda series: series.rolling(
                window=window_size,
                min_periods=min(2, window_size),
            ).std()
        )

        result["rolling_count"] = grouped["value"].transform(
            lambda series: series.rolling(
                window=window_size,
                min_periods=1,
            ).count()
        )

        result["value_delta"] = grouped["value"].diff()

        return result