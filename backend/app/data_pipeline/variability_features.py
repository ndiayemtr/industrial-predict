import pandas as pd


class VariabilityFeatureBuilder:

    def build(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return dataframe.copy()

        required_columns = {
            "rolling_mean",
            "rolling_min",
            "rolling_max",
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

        result["rolling_range"] = (
            result["rolling_max"]
            - result["rolling_min"]
        )

        result["rolling_cv"] = (
            result["rolling_std"]
            / result["rolling_mean"]
        )

        result.loc[
            result["rolling_mean"] == 0,
            "rolling_cv",
        ] = pd.NA

        return result