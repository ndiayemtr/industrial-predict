import pandas as pd


class TrendFeatureBuilder:

    def build(
        self,
        dataframe: pd.DataFrame,
        *,
        window_size: int = 3,
    ) -> pd.DataFrame:

        if window_size < 2:
            raise ValueError(
                "window_size must be greater than or equal to 2"
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

        result["trend_slope"] = grouped["value"].transform(
            lambda series: series.rolling(
                window=window_size,
                min_periods=2,
            ).apply(
                lambda values: (
                    (values.iloc[-1] - values.iloc[0])
                    / (len(values) - 1)
                ),
                raw=False,
            )
        )

        return result