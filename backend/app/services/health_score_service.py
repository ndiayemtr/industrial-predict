from sqlalchemy.orm import Session

from app.ml.health_score.calculator import HealthScoreCalculator
from app.repositories.equipment_repository import EquipmentRepository
from app.schemas.health_score import (
    HealthScoreComponentsRead,
    HealthScoreRead,
    HealthScoreRequest,
)


class HealthScoreService:

    def __init__(self, db: Session):
        self.equipment_repository = EquipmentRepository(db)
        self.calculator = HealthScoreCalculator()

    def calculate_for_equipment(
        self,
        equipment_id: int,
        data: HealthScoreRequest,
    ) -> HealthScoreRead:

        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        result = self.calculator.calculate(
            failure_probability=data.failure_probability,
            anomaly_score=data.anomaly_score,
            valid_count=data.valid_count,
            warning_count=data.warning_count,
            invalid_count=data.invalid_count,
            corrective_in_progress=data.corrective_in_progress,
            overdue_maintenance=data.overdue_maintenance,
            planned_soon=data.planned_soon,
        )

        return HealthScoreRead(
            equipment_id=equipment.id,
            health_score=result.health_score,
            health_level=result.health_level,
            components=HealthScoreComponentsRead(
                failure_health=result.components.failure_health,
                anomaly_health=result.components.anomaly_health,
                data_quality_health=(
                    result.components.data_quality_health
                ),
                maintenance_health=(
                    result.components.maintenance_health
                ),
            ),
        )