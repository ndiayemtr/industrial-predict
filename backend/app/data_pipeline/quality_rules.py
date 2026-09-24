from enum import StrEnum
from math import isfinite


class DataQualityStatus(StrEnum):
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"


class MeasurementQualityPolicy:

    VALID_QUALITIES = {
        "good",
    }

    WARNING_QUALITIES = {
        "suspect",
        "estimated",
    }

    INVALID_QUALITIES = {
        "bad",
        "missing",
    }

    @classmethod
    def classify_quality(
        cls,
        quality: str,
    ) -> DataQualityStatus:

        normalized = quality.strip().lower()

        if normalized in cls.VALID_QUALITIES:
            return DataQualityStatus.VALID

        if normalized in cls.WARNING_QUALITIES:
            return DataQualityStatus.WARNING

        if normalized in cls.INVALID_QUALITIES:
            return DataQualityStatus.INVALID

        return DataQualityStatus.INVALID
    
    @staticmethod
    def is_valid_numeric_value(
        value: float,
    ) -> bool:

        return isfinite(value)