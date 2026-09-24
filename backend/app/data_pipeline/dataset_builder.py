import pandas as pd

from app.data_pipeline.schemas import MeasurementDataRow


class MeasurementDatasetBuilder:

    def build(
        self,
        rows: list[MeasurementDataRow],
    ) -> pd.DataFrame:

        if not rows:
            return pd.DataFrame()

        data = [
            row.model_dump()
            for row in rows
        ]

        dataframe = pd.DataFrame(data)

        dataframe["timestamp"] = pd.to_datetime(
            dataframe["timestamp"],
            utc=True,
        )

        dataframe = dataframe.sort_values(
            by=[
                "sensor_id",
                "timestamp",
                "measurement_id",
            ],
            ascending=True,
        )

        dataframe = dataframe.reset_index(
            drop=True,
        )

        return dataframe