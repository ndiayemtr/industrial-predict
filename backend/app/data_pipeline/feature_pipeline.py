import pandas as pd

from app.data_pipeline.lag_features import LagFeatureBuilder
from app.data_pipeline.multiscale_features import MultiScaleFeatureBuilder
from app.data_pipeline.quality_features import QualityFeatureBuilder
from app.data_pipeline.rate_features import RateFeatureBuilder
from app.data_pipeline.time_series import TimeSeriesPreparer
from app.data_pipeline.trend_features import TrendFeatureBuilder
from app.data_pipeline.variability_features import VariabilityFeatureBuilder
from app.data_pipeline.window_features import WindowFeatureBuilder


class MeasurementFeaturePipeline:

    def __init__(self):
        self.time_series = TimeSeriesPreparer()
        self.window_features = WindowFeatureBuilder()
        self.lag_features = LagFeatureBuilder()
        self.trend_features = TrendFeatureBuilder()
        self.variability_features = VariabilityFeatureBuilder()
        self.rate_features = RateFeatureBuilder()
        self.multiscale_features = MultiScaleFeatureBuilder()
        self.quality_features = QualityFeatureBuilder()

    def build(
        self,
        dataframe: pd.DataFrame,
        *,
        window_size: int = 3,
        lags: tuple[int, ...] = (1, 2, 3),
        multiscale_windows: tuple[int, ...] = (3, 5, 10),
    ) -> pd.DataFrame:

        result = self.time_series.prepare(
            dataframe
        )

        result = self.window_features.build(
            result,
            window_size=window_size,
        )

        result = self.lag_features.build(
            result,
            lags=lags,
        )

        result = self.trend_features.build(
            result,
            window_size=window_size,
        )

        result = self.variability_features.build(
            result
        )

        result = self.rate_features.build(
            result
        )

        result = self.multiscale_features.build(
            result,
            windows=multiscale_windows,
        )

        result = self.quality_features.build(
            result
        )

        return result