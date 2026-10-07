import pandas as pd


class FailureRiskPreparer:

    TARGET_COLUMN = "failure_within_horizon"

    EXCLUDED_COLUMNS = {
        "failure_within_horizon",
        "next_failure_at",
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
                pd.Series(dtype="int8", name=self.TARGET_COLUMN),
            )

        if self.TARGET_COLUMN not in dataframe.columns:
            raise ValueError(
                f"Missing target column: {self.TARGET_COLUMN}"
            )

        y = (
            dataframe[self.TARGET_COLUMN]
            .astype("int8")
            .copy()
        )

        candidate_columns = [
            column
            for column in dataframe.columns
            if column not in self.EXCLUDED_COLUMNS
        ]

        X = dataframe[candidate_columns].copy()

        # V1: on ne garde que les features numériques / booléennes.
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