import pandas as pd


class TimeSeriesPreparer:

    def prepare(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return dataframe.copy()

        prepared = dataframe.copy()

        prepared["timestamp"] = pd.to_datetime(
            prepared["timestamp"],
            utc=True,
        )

        prepared = prepared.sort_values(
            by=[
                "sensor_id",
                "timestamp",
                "measurement_id",
            ],
            ascending=True,
        ).reset_index(drop=True)

        prepared["time_delta_seconds"] = (
            prepared
            .groupby("sensor_id")["timestamp"]
            .diff()
            .dt.total_seconds()
        )

        return prepared

    def profile(
        self,
        dataframe: pd.DataFrame,
    ) -> dict:

        if dataframe.empty:
            return {
                "sensor_count": 0,
                "measurement_count": 0,
                "sensors": {},
            }

        sensors = {}

        for sensor_id, group in dataframe.groupby("sensor_id"):
            intervals = (
                group["time_delta_seconds"]
                .dropna()
            )

            sensors[int(sensor_id)] = {
                "measurement_count": len(group),
                "start_time": group["timestamp"].min(),
                "end_time": group["timestamp"].max(),
                "min_interval_seconds": (
                    float(intervals.min())
                    if not intervals.empty
                    else None
                ),
                "max_interval_seconds": (
                    float(intervals.max())
                    if not intervals.empty
                    else None
                ),
                "median_interval_seconds": (
                    float(intervals.median())
                    if not intervals.empty
                    else None
                ),
            }

        return {
            "sensor_count": dataframe["sensor_id"].nunique(),
            "measurement_count": len(dataframe),
            "sensors": sensors,
        }