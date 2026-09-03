from sqlalchemy.orm import Session

from app.models.maintenance_record import MaintenanceRecord
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.maintenance_repository import MaintenanceRepository
from app.schemas.maintenance import (
    MaintenanceCreate,
    MaintenanceUpdate,
)


class MaintenanceService:

    def __init__(self, db: Session):
        self.repository = MaintenanceRepository(db)
        self.equipment_repository = EquipmentRepository(db)
        self.db = db

    def get_all(self) -> list[MaintenanceRecord]:
        return self.repository.get_all()

    def get_by_id(
        self,
        maintenance_id: int,
    ) -> MaintenanceRecord | None:

        return self.repository.get_by_id(maintenance_id)

    def get_by_equipment_id(
        self,
        equipment_id: int,
    ) -> list[MaintenanceRecord]:

        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if not equipment:
            raise ValueError("Equipment not found")

        return self.repository.get_by_equipment_id(
            equipment_id
        )

    def create(
        self,
        data: MaintenanceCreate,
    ) -> MaintenanceRecord:

        equipment = self.equipment_repository.get_by_id(
            data.equipment_id
        )

        if not equipment:
            raise ValueError("Equipment not found")

        maintenance = MaintenanceRecord(
            equipment_id=data.equipment_id,
            maintenance_type=data.maintenance_type,
            status=data.status,
            priority=data.priority,
            title=data.title,
            description=data.description,
            failure_code=data.failure_code,
            root_cause=data.root_cause,
            action_taken=data.action_taken,
            technician=data.technician,
            planned_at=data.planned_at,
            started_at=data.started_at,
            completed_at=data.completed_at,
            downtime_minutes=data.downtime_minutes,
            cost=data.cost,
        )

        maintenance = self.repository.create(
            maintenance
        )

        self.db.commit()
        self.db.refresh(maintenance)

        return maintenance

    def update(
        self,
        maintenance: MaintenanceRecord,
        data: MaintenanceUpdate,
    ) -> MaintenanceRecord:

        update_data = data.model_dump(
            exclude_unset=True
        )

        for field, value in update_data.items():
            setattr(maintenance, field, value)

        maintenance = self.repository.update(
            maintenance
        )

        self.db.commit()
        self.db.refresh(maintenance)

        return maintenance

    def delete(
        self,
        maintenance: MaintenanceRecord,
    ) -> None:

        self.repository.delete(maintenance)

        self.db.commit()