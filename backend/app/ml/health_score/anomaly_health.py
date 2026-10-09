class AnomalyHealthCalculator:

    def calculate(
        self,
        anomaly_score: float,
    ) -> float:

        if not 0.0 <= anomaly_score <= 1.0:
            raise ValueError(
                "anomaly_score must be between 0 and 1"
            )

        return round(
            (1.0 - anomaly_score) * 100.0,
            2,
        )