from datetime import timedelta

import pandas as pd


class FailureLabeler:

    def build(
        self,
        measurements: pd.DataFrame,
        maintenance_records: pd.DataFrame,
        *,
        horizon_hours: float = 24.0,
    ) -> pd.DataFrame:

        if horizon_hours <= 0:
            raise ValueError(
                "horizon_hours must be greater than 0"
            )

        result = measurements.copy()

        result["failure_within_horizon"] = 0

        result["next_failure_at"] = pd.Series(
            pd.NaT,
            index=result.index,
            dtype="datetime64[ns, UTC]",
        )

        result["time_to_failure_hours"] = pd.Series(
            pd.NA,
            index=result.index,
            dtype="Float64",
        )

        if result.empty:
            return result

        required_measurement_columns = {
            "equipment_id",
            "timestamp",
        }

        missing_measurement_columns = (
            required_measurement_columns
            - set(result.columns)
        )

        if missing_measurement_columns:
            raise ValueError(
                "Missing measurement columns: "
                + ", ".join(
                    sorted(missing_measurement_columns)
                )
            )

        required_maintenance_columns = {
            "equipment_id",
            "maintenance_type",
            "started_at",
        }

        missing_maintenance_columns = (
            required_maintenance_columns
            - set(maintenance_records.columns)
        )

        if missing_maintenance_columns:
            raise ValueError(
                "Missing maintenance columns: "
                + ", ".join(
                    sorted(missing_maintenance_columns)
                )
            )

        result["timestamp"] = pd.to_datetime(
            result["timestamp"],
            utc=True,
        )

        maintenance = maintenance_records.copy()

        maintenance["started_at"] = pd.to_datetime(
            maintenance["started_at"],
            utc=True,
            errors="coerce",
        )

        failures = maintenance[
            (
                maintenance["maintenance_type"]
                .astype(str)
                .str.lower()
                == "corrective"
            )
            & maintenance["started_at"].notna()
        ].copy()

        if failures.empty:
            return result

        horizon = timedelta(
            hours=horizon_hours
        )

        # DataFrame indices may repeat after concatenating equipment series.
        for position, (_, row) in enumerate(result.iterrows()):

            equipment_failures = failures[
                failures["equipment_id"]
                == row["equipment_id"]
            ]

            future_failures = equipment_failures[
                equipment_failures["started_at"]
                > row["timestamp"]
            ].sort_values("started_at")

            if future_failures.empty:
                continue

            next_failure = (
                future_failures.iloc[0]["started_at"]
            )

            time_to_failure = (
                next_failure
                - row["timestamp"]
            )

            if time_to_failure <= horizon:
                result.iat[
                    position,
                    result.columns.get_loc("failure_within_horizon"),
                ] = 1

                result.iat[
                    position,
                    result.columns.get_loc("next_failure_at"),
                ] = next_failure

                result.iat[
                    position,
                    result.columns.get_loc("time_to_failure_hours"),
                ] = (
                    time_to_failure.total_seconds()
                    / 3600
                )

        return result
