import pandas as pd


class MeasurementGapDetector:

    def detect(
        self,
        dataframe: pd.DataFrame,
        *,
        gap_multiplier: float = 1.5,
    ) -> pd.DataFrame:

        if gap_multiplier <= 1:
            raise ValueError(
                "gap_multiplier must be greater than 1"
            )

        result = dataframe.copy()

        if result.empty:
            result["expected_interval_seconds"] = pd.Series(
                dtype="float64"
            )
            result["gap_detected"] = pd.Series(
                dtype="bool"
            )
            return result

        result = result.sort_values(
            by=[
                "sensor_id",
                "timestamp",
                "measurement_id",
            ]
        ).reset_index(drop=True)

        if "time_delta_seconds" not in result.columns:
            result["time_delta_seconds"] = (
                result
                .groupby("sensor_id")["timestamp"]
                .diff()
                .dt.total_seconds()
            )

        expected_intervals = (
            result
            .groupby("sensor_id")["time_delta_seconds"]
            .transform(
                lambda series: series.dropna().median()
            )
        )

        result["expected_interval_seconds"] = (
            expected_intervals
        )

        result["gap_detected"] = (
            result["time_delta_seconds"].notna()
            & result["expected_interval_seconds"].notna()
            & (
                result["time_delta_seconds"]
                >
                result["expected_interval_seconds"]
                * gap_multiplier
            )
        )

        return result

    def summarize(
        self,
        dataframe: pd.DataFrame,
        *,
        gap_multiplier: float = 1.5,
    ) -> dict:

        detected = self.detect(
            dataframe,
            gap_multiplier=gap_multiplier,
        )

        if detected.empty:
            return {
                "gap_count": 0,
                "sensors_with_gaps": 0,
            }

        gap_rows = detected[
            detected["gap_detected"]
        ]

        return {
            "gap_count": int(
                gap_rows.shape[0]
            ),
            "sensors_with_gaps": int(
                gap_rows["sensor_id"].nunique()
            ),
        }