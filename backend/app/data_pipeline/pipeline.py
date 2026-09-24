from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.data_pipeline.data_quality import DataQualityReport
from app.data_pipeline.dataset_builder import MeasurementDatasetBuilder
from app.data_pipeline.extractor import MeasurementDataExtractor
from app.data_pipeline.time_series import TimeSeriesPreparer
from app.data_pipeline.window_features import WindowFeatureBuilder


class MeasurementDataPipeline:

    def __init__(self, db: Session):
        self.extractor = MeasurementDataExtractor(db)
        self.dataset_builder = MeasurementDatasetBuilder()
        self.quality_report = DataQualityReport()
        self.time_series_preparer = TimeSeriesPreparer()
        self.window_feature_builder = WindowFeatureBuilder()

    def build(
        self,
        *,
        company_id: int | None = None,
        site_id: int | None = None,
        equipment_id: int | None = None,
        sensor_id: int | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        window_size: int = 3,
    ) -> pd.DataFrame:

        rows = self.extractor.extract(
            company_id=company_id,
            site_id=site_id,
            equipment_id=equipment_id,
            sensor_id=sensor_id,
            start_time=start_time,
            end_time=end_time,
        )

        dataframe = self.dataset_builder.build(rows)

        dataframe = self.time_series_preparer.prepare(
            dataframe
        )

        dataframe = self.window_feature_builder.build(
            dataframe,
            window_size=window_size,
        )

        return dataframe

    def analyze_quality(
        self,
        dataframe: pd.DataFrame,
    ) -> dict:

        return self.quality_report.analyze(
            dataframe
        )

    def profile_time_series(
        self,
        dataframe: pd.DataFrame,
    ) -> dict:

        return self.time_series_preparer.profile(
            dataframe
        )