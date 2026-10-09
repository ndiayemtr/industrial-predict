class DataQualityHealthCalculator:

    def calculate(
        self,
        *,
        valid_count: int,
        warning_count: int,
        invalid_count: int,
    ) -> float:

        counts = {
            "valid_count": valid_count,
            "warning_count": warning_count,
            "invalid_count": invalid_count,
        }

        for name, value in counts.items():
            if value < 0:
                raise ValueError(
                    f"{name} must be greater than or equal to 0"
                )

        total_count = (
            valid_count
            + warning_count
            + invalid_count
        )

        if total_count == 0:
            raise ValueError(
                "At least one quality observation is required"
            )

        score = (
            valid_count
            + 0.5 * warning_count
        ) / total_count * 100.0

        return round(score, 2)