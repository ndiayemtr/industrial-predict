class FailureHealthCalculator:

    def calculate(
        self,
        failure_probability: float,
    ) -> float:

        if not 0.0 <= failure_probability <= 1.0:
            raise ValueError(
                "failure_probability must be between 0 and 1"
            )

        return round(
            (1.0 - failure_probability) * 100.0,
            2,
        )