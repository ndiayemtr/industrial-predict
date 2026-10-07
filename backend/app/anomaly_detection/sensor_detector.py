import pandas as pd

from app.anomaly_detection.isolation_forest_detector import (
    IsolationForestAnomalyDetector,
)
from app.anomaly_detection.statistical_detector import (
    StatisticalAnomalyDetector,
)
from app.anomaly_detection.unified_score import (
    UnifiedAnomalyScorer,
)
from app.anomaly_detection.zscore_detector import (
    ZScoreAnomalyDetector,
)


class SensorAnomalyDetector:

    def __init__(self):
        self.statistical_detector = StatisticalAnomalyDetector()
        self.zscore_detector = ZScoreAnomalyDetector()
        self.isolation_forest_detector = (
            IsolationForestAnomalyDetector()
        )
        self.unified_scorer = UnifiedAnomalyScorer()

    def detect(
        self,
        dataframe: pd.DataFrame,
        *,
        threshold_std: float = 3.0,
        z_threshold: float = 3.0,
        robust_threshold: float = 3.5,
        contamination: float = 0.05,
        anomaly_threshold: float = 0.6,
        isolation_features: list[str] | None = None,
    ) -> pd.DataFrame:

        if dataframe.empty:
            return dataframe.copy()

        result = self.statistical_detector.detect(
            dataframe,
            threshold_std=threshold_std,
        )

        result = self.zscore_detector.detect(
            result,
            z_threshold=z_threshold,
            robust_threshold=robust_threshold,
        )

        result = self.isolation_forest_detector.detect(
            result,
            contamination=contamination,
            features=isolation_features,
        )

        result = self.unified_scorer.build(
            result,
            anomaly_threshold=anomaly_threshold,
        )

        return result