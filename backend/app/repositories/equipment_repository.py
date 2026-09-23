from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.equipment import Equipment


class EquipmentRepository:

    def __init__(self, db: Session):
        self.db = db

    def get_paginated(
        self,
        *,
        offset: int,
        limit: int,
        site_id: int | None = None,
        status: str | None = None,
        criticality: str | None = None,
        search: str | None = None,
    ) -> list[Equipment]:
        statement = select(Equipment)

        if site_id is not None:
            statement = statement.where(
                Equipment.site_id == site_id
            )

        if status is not None:
            statement = statement.where(
                Equipment.status == status
            )

        if criticality is not None:
            statement = statement.where(
                Equipment.criticality == criticality
            )

        if search:
            pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    Equipment.name.ilike(pattern),
                    Equipment.code.ilike(pattern),
                    Equipment.equipment_type.ilike(pattern),
                )
            )

        statement = (
            statement
            .order_by(Equipment.id.asc())
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
        site_id: int | None = None,
        status: str | None = None,
        criticality: str | None = None,
        search: str | None = None,
    ) -> int:
        statement = select(func.count(Equipment.id))

        if site_id is not None:
            statement = statement.where(
                Equipment.site_id == site_id
            )

        if status is not None:
            statement = statement.where(
                Equipment.status == status
            )

        if criticality is not None:
            statement = statement.where(
                Equipment.criticality == criticality
            )

        if search:
            pattern = f"%{search.strip()}%"

            statement = statement.where(
                or_(
                    Equipment.name.ilike(pattern),
                    Equipment.code.ilike(pattern),
                    Equipment.equipment_type.ilike(pattern),
                )
            )

        return self.db.execute(
            statement
        ).scalar_one()

    def get_all(self) -> list[Equipment]:
        statement = select(Equipment).order_by(Equipment.id)
        return list(self.db.scalars(statement).all())

    def get_by_id(self, equipment_id: int) -> Equipment | None:
        statement = select(Equipment).where(
            Equipment.id == equipment_id
        )
        return self.db.scalar(statement)

    def get_by_code(self, code: str) -> Equipment | None:
        statement = select(Equipment).where(
            Equipment.code == code
        )
        return self.db.scalar(statement)

    def get_by_site_id(self, site_id: int) -> list[Equipment]:
        statement = (
            select(Equipment)
            .where(Equipment.site_id == site_id)
            .order_by(Equipment.id)
        )
        return list(self.db.scalars(statement).all())

    def create(self, equipment: Equipment) -> Equipment:
        self.db.add(equipment)
        self.db.flush()
        self.db.refresh(equipment)
        return equipment

    def update(self, equipment: Equipment) -> Equipment:
        self.db.flush()
        self.db.refresh(equipment)
        return equipment

    def delete(self, equipment: Equipment) -> None:
        self.db.delete(equipment)
        self.db.flush()
