import pandas as pd


class LagFeatureBuilder:

    def build(
        self,
        dataframe: pd.DataFrame,
        *,
        lags: tuple[int, ...] = (1, 2, 3),
    ) -> pd.DataFrame:

        if any(lag < 1 for lag in lags):
            raise ValueError(
                "lags must contain only positive integers"
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

        for lag in lags:
            result[f"value_lag_{lag}"] = (
                grouped["value"].shift(lag)
            )

        return result