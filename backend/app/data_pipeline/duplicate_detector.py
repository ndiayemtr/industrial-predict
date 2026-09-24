import pandas as pd


class DuplicateMeasurementDetector:

    def detect(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        result = dataframe.copy()

        if result.empty:
            result["duplicate_measurement_id"] = pd.Series(
                dtype="bool"
            )
            result["duplicate_sensor_timestamp"] = pd.Series(
                dtype="bool"
            )
            return result

        result["duplicate_measurement_id"] = (
            result.duplicated(
                subset=["measurement_id"],
                keep=False,
            )
        )

        result["duplicate_sensor_timestamp"] = (
            result.duplicated(
                subset=[
                    "sensor_id",
                    "timestamp",
                ],
                keep=False,
            )
        )

        return result

    def summarize(
        self,
        dataframe: pd.DataFrame,
    ) -> dict:

        detected = self.detect(dataframe)

        if detected.empty:
            return {
                "duplicate_measurement_id_count": 0,
                "duplicate_sensor_timestamp_count": 0,
            }

        return {
            "duplicate_measurement_id_count": int(
                detected["duplicate_measurement_id"].sum()
            ),
            "duplicate_sensor_timestamp_count": int(
                detected["duplicate_sensor_timestamp"].sum()
            ),
        }