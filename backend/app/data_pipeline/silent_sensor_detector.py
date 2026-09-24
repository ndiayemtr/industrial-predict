from datetime import datetime

import pandas as pd


class SilentSensorDetector:

    def detect(
        self,
        dataframe: pd.DataFrame,
        *,
        reference_time: datetime,
        silence_multiplier: float = 3.0,
    ) -> pd.DataFrame:

        if silence_multiplier <= 1:
            raise ValueError(
                "silence_multiplier must be greater than 1"
            )

        reference_timestamp = pd.Timestamp(
            reference_time
        )

        if reference_timestamp.tzinfo is None:
            raise ValueError(
                "reference_time must include timezone information"
            )

        reference_timestamp = (
            reference_timestamp.tz_convert("UTC")
        )

        if dataframe.empty:
            return pd.DataFrame(
                columns=[
                    "sensor_id",
                    "last_measurement_time",
                    "expected_interval_seconds",
                    "silence_seconds",
                    "silent",
                ]
            )

        result = dataframe.copy()

        result["timestamp"] = pd.to_datetime(
            result["timestamp"],
            utc=True,
        )

        result = result.sort_values(
            by=[
                "sensor_id",
                "timestamp",
                "measurement_id",
            ]
        )

        if "time_delta_seconds" not in result.columns:
            result["time_delta_seconds"] = (
                result
                .groupby("sensor_id")["timestamp"]
                .diff()
                .dt.total_seconds()
            )


        if reference_timestamp.tzinfo is None:
            raise ValueError(
                "reference_time must include timezone information"
            )

        reference_timestamp = (
            reference_timestamp.tz_convert("UTC")
        )

        rows = []

        for sensor_id, group in result.groupby("sensor_id"):

            intervals = (
                group["time_delta_seconds"]
                .dropna()
            )

            expected_interval = (
                float(intervals.median())
                if not intervals.empty
                else None
            )

            last_measurement_time = (
                group["timestamp"].max()
            )

            silence_seconds = float(
                (
                    reference_timestamp
                    - last_measurement_time
                ).total_seconds()
            )

            silent = (
                expected_interval is not None
                and silence_seconds
                > expected_interval * silence_multiplier
            )

            rows.append(
                {
                    "sensor_id": int(sensor_id),
                    "last_measurement_time": last_measurement_time,
                    "expected_interval_seconds": expected_interval,
                    "silence_seconds": silence_seconds,
                    "silent": silent,
                }
            )

        return pd.DataFrame(rows)

    def summarize(
        self,
        dataframe: pd.DataFrame,
        *,
        reference_time: datetime,
        silence_multiplier: float = 3.0,
    ) -> dict:

        detected = self.detect(
            dataframe,
            reference_time=reference_time,
            silence_multiplier=silence_multiplier,
        )

        if detected.empty:
            return {
                "sensor_count": 0,
                "silent_sensor_count": 0,
            }

        return {
            "sensor_count": len(detected),
            "silent_sensor_count": int(
                detected["silent"].sum()
            ),
        }