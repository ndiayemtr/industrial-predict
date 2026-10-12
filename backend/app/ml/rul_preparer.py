import pandas as pd


class RULPreparer:

    TARGET_COLUMN = "rul_hours"

    EXCLUDED_COLUMNS = {
        "rul_hours",
        "next_failure_at",

        "failure_within_horizon",
        "time_to_failure_hours",

        "measurement_id",
        "sensor_id",
        "equipment_id",
        "site_id",
        "company_id",

        "timestamp",

        "sensor_code",
        "equipment_code",
        "site_code",
        "company_code",

        "root_cause",
        "action_taken",
        "failure_code",
        "completed_at",
        "downtime_minutes",
        "cost",
    }

    def prepare(
        self,
        dataframe: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.Series]:

        if dataframe.empty:
            return (
                pd.DataFrame(),
                pd.Series(
                    dtype="float64",
                    name=self.TARGET_COLUMN,
                ),
            )

        if self.TARGET_COLUMN not in dataframe.columns:
            raise ValueError(
                f"Missing target column: {self.TARGET_COLUMN}"
            )

        labeled = dataframe[
            dataframe[self.TARGET_COLUMN].notna()
        ].copy()

        if labeled.empty:
            return (
                pd.DataFrame(),
                pd.Series(
                    dtype="float64",
                    name=self.TARGET_COLUMN,
                ),
            )

        y = (
            labeled[self.TARGET_COLUMN]
            .astype("float64")
            .copy()
        )

        candidate_columns = [
            column
            for column in labeled.columns
            if column not in self.EXCLUDED_COLUMNS
        ]

        X = labeled[candidate_columns].copy()

        allowed_columns = [
            column
            for column in X.columns
            if (
                pd.api.types.is_numeric_dtype(X[column])
                or pd.api.types.is_bool_dtype(X[column])
            )
        ]

        X = X[allowed_columns]

        return X, y