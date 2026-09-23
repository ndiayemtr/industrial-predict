from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.maintenance_record import MaintenanceRecord


class MaintenanceRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_paginated(
        self,
        *,
        offset: int,
        limit: int,
    ) -> list[MaintenanceRecord]:
        statement = (
            select(MaintenanceRecord)
            .order_by(MaintenanceRecord.created_at.desc(), MaintenanceRecord.id.desc())
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def count_all(self) -> int:
        statement = select(func.count(MaintenanceRecord.id))
        return self.db.execute(statement).scalar_one()

    def get_all(self) -> list[MaintenanceRecord]:
        statement = (
            select(MaintenanceRecord)
            .order_by(MaintenanceRecord.created_at.desc())
        )

        return list(self.db.scalars(statement).all())

    def get_by_id(
        self,
        maintenance_id: int,
    ) -> MaintenanceRecord | None:

        statement = select(MaintenanceRecord).where(
            MaintenanceRecord.id == maintenance_id
        )

        return self.db.scalar(statement)

    def get_by_equipment_id(
        self,
        equipment_id: int,
    ) -> list[MaintenanceRecord]:

        statement = (
            select(MaintenanceRecord)
            .where(
                MaintenanceRecord.equipment_id == equipment_id
            )
            .order_by(MaintenanceRecord.created_at.desc())
        )

        return list(self.db.scalars(statement).all())

    def create(
        self,
        maintenance: MaintenanceRecord,
    ) -> MaintenanceRecord:

        self.db.add(maintenance)
        self.db.flush()
        self.db.refresh(maintenance)

        return maintenance

    def update(
        self,
        maintenance: MaintenanceRecord,
    ) -> MaintenanceRecord:

        self.db.flush()
        self.db.refresh(maintenance)

        return maintenance

    def delete(
        self,
        maintenance: MaintenanceRecord,
    ) -> None:

        self.db.delete(maintenance)
        self.db.flush()
