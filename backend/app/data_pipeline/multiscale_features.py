import pandas as pd


class MultiScaleFeatureBuilder:

    def build(
        self,
        dataframe: pd.DataFrame,
        *,
        windows: tuple[int, ...] = (3, 5, 10),
    ) -> pd.DataFrame:

        if any(window < 1 for window in windows):
            raise ValueError(
                "windows must contain only positive integers"
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

        for window in windows:

            result[f"rolling_mean_{window}"] = (
                grouped["value"].transform(
                    lambda series: series.rolling(
                        window=window,
                        min_periods=1,
                    ).mean()
                )
            )

            result[f"rolling_std_{window}"] = (
                grouped["value"].transform(
                    lambda series: series.rolling(
                        window=window,
                        min_periods=min(2, window),
                    ).std()
                )
            )

        return result