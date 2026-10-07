import pandas as pd


class RateFeatureBuilder:

    def build(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return dataframe.copy()

        required_columns = {
            "value_delta",
            "time_delta_seconds",
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

        result["rate_of_change"] = (
            result["value_delta"]
            / result["time_delta_seconds"]
        )

        result.loc[
            result["time_delta_seconds"] <= 0,
            "rate_of_change",
        ] = pd.NA

        return result