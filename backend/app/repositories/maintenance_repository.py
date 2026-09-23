from datetime import datetime

from sqlalchemy import func, or_, select
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
        equipment_id: int | None = None,
        maintenance_type: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        search: str | None = None,
    ) -> list[MaintenanceRecord]:
        statement = select(MaintenanceRecord)

        if equipment_id is not None:
            statement = statement.where(
                MaintenanceRecord.equipment_id == equipment_id
            )

        if maintenance_type is not None:
            statement = statement.where(
                MaintenanceRecord.maintenance_type == maintenance_type
            )

        if status is not None:
            statement = statement.where(
                MaintenanceRecord.status == status
            )

        if priority is not None:
            statement = statement.where(
                MaintenanceRecord.priority == priority
            )

        if start_time is not None:
            statement = statement.where(
                MaintenanceRecord.created_at >= start_time
            )

        if end_time is not None:
            statement = statement.where(
                MaintenanceRecord.created_at < end_time
            )

        if search:
            pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    MaintenanceRecord.title.ilike(pattern),
                    MaintenanceRecord.description.ilike(pattern),
                    MaintenanceRecord.failure_code.ilike(pattern),
                    MaintenanceRecord.root_cause.ilike(pattern),
                    MaintenanceRecord.action_taken.ilike(pattern),
                    MaintenanceRecord.technician.ilike(pattern),
                )
            )

        statement = (
            statement
            .order_by(
                MaintenanceRecord.created_at.desc(),
                MaintenanceRecord.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )

        return list(
            self.db.execute(statement)
            .scalars()
            .all()
        )

    def count_all(
        self,
        *,
        equipment_id: int | None = None,
        maintenance_type: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        search: str | None = None,
    ) -> int:
        statement = select(
            func.count(MaintenanceRecord.id)
        )

        if equipment_id is not None:
            statement = statement.where(
                MaintenanceRecord.equipment_id == equipment_id
            )

        if maintenance_type is not None:
            statement = statement.where(
                MaintenanceRecord.maintenance_type == maintenance_type
            )

        if status is not None:
            statement = statement.where(
                MaintenanceRecord.status == status
            )

        if priority is not None:
            statement = statement.where(
                MaintenanceRecord.priority == priority
            )

        if start_time is not None:
            statement = statement.where(
                MaintenanceRecord.created_at >= start_time
            )

        if end_time is not None:
            statement = statement.where(
                MaintenanceRecord.created_at < end_time
            )

        if search:
            pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    MaintenanceRecord.title.ilike(pattern),
                    MaintenanceRecord.description.ilike(pattern),
                    MaintenanceRecord.failure_code.ilike(pattern),
                    MaintenanceRecord.root_cause.ilike(pattern),
                    MaintenanceRecord.action_taken.ilike(pattern),
                    MaintenanceRecord.technician.ilike(pattern),
                )
            )

        return self.db.execute(
            statement
        ).scalar_one()

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
