class MaintenanceHealthCalculator:

    CORRECTIVE_IN_PROGRESS_PENALTY = 40.0
    OVERDUE_MAINTENANCE_PENALTY = 30.0
    PLANNED_SOON_PENALTY = 10.0

    def calculate(
        self,
        *,
        corrective_in_progress: bool = False,
        overdue_maintenance: bool = False,
        planned_soon: bool = False,
    ) -> float:

        score = 100.0

        if corrective_in_progress:
            score -= self.CORRECTIVE_IN_PROGRESS_PENALTY

        if overdue_maintenance:
            score -= self.OVERDUE_MAINTENANCE_PENALTY

        if planned_soon:
            score -= self.PLANNED_SOON_PENALTY

        return max(
            0.0,
            round(score, 2),
        )