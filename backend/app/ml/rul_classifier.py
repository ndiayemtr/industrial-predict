class RULLevelClassifier:

    def __init__(
        self,
        *,
        critical_hours: float = 24.0,
        warning_hours: float = 72.0,
        watch_hours: float = 168.0,
    ):
        if critical_hours <= 0:
            raise ValueError(
                "critical_hours must be greater than 0"
            )

        if warning_hours <= critical_hours:
            raise ValueError(
                "warning_hours must be greater than critical_hours"
            )

        if watch_hours <= warning_hours:
            raise ValueError(
                "watch_hours must be greater than warning_hours"
            )

        self.critical_hours = critical_hours
        self.warning_hours = warning_hours
        self.watch_hours = watch_hours

    def classify(
        self,
        rul_hours: float,
    ) -> str:

        if rul_hours < 0:
            raise ValueError(
                "rul_hours must be non-negative"
            )

        if rul_hours <= self.critical_hours:
            return "critical"

        if rul_hours <= self.warning_hours:
            return "warning"

        if rul_hours <= self.watch_hours:
            return "watch"

        return "healthy"