from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment import Equipment


class EquipmentRepository:

    def __init__(self, db: Session):
        self.db = db

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