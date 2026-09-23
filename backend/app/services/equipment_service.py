from sqlalchemy.orm import Session

from app.core.pagination import build_page

from app.models.equipment import Equipment
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.equipment import EquipmentCreate, EquipmentUpdate


class EquipmentService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = EquipmentRepository(db)
        self.site_repository = SiteRepository(db)

    def get_paginated(
        self,
        *,
        page: int,
        page_size: int,
    ):
        offset = (page - 1) * page_size

        items = self.repository.get_paginated(
            offset=offset,
            limit=page_size,
        )

        total = self.repository.count_all()

        return build_page(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_all(self) -> list[Equipment]:
        return self.repository.get_all()

    def get_by_id(self, equipment_id: int) -> Equipment | None:
        return self.repository.get_by_id(equipment_id)

    def get_by_site_id(self, site_id: int) -> list[Equipment]:
        return self.repository.get_by_site_id(site_id)

    def create(self, data: EquipmentCreate) -> Equipment:
        # Vérifier que le Site existe
        site = self.site_repository.get_by_id(data.site_id)

        if site is None:
            raise ValueError(
                f"Site with id '{data.site_id}' does not exist."
            )

        # Vérifier que le code de l'Equipment est unique
        existing_equipment = self.repository.get_by_code(data.code)

        if existing_equipment:
            raise ValueError(
                f"Equipment with code '{data.code}' already exists."
            )

        equipment = Equipment(
            name=data.name,
            code=data.code,
            equipment_type=data.equipment_type,
            description=data.description,
            status=data.status,
            criticality=data.criticality,
            site_id=data.site_id,
        )

        self.repository.create(equipment)

        self.db.commit()
        self.db.refresh(equipment)

        return equipment

    def update(
        self,
        equipment: Equipment,
        data: EquipmentUpdate,
    ) -> Equipment:

        update_data = data.model_dump(exclude_unset=True)

        # Vérifier le nouveau Site s'il est modifié
        if "site_id" in update_data:
            site = self.site_repository.get_by_id(
                update_data["site_id"]
            )

            if site is None:
                raise ValueError(
                    f"Site with id '{update_data['site_id']}' does not exist."
                )

        # Vérifier l'unicité du code
        if "code" in update_data:
            existing_equipment = self.repository.get_by_code(
                update_data["code"]
            )

            if (
                existing_equipment
                and existing_equipment.id != equipment.id
            ):
                raise ValueError(
                    f"Equipment with code '{update_data['code']}' already exists."
                )

        # Appliquer les modifications
        for field, value in update_data.items():
            setattr(equipment, field, value)

        self.repository.update(equipment)

        self.db.commit()
        self.db.refresh(equipment)

        return equipment

    def delete(self, equipment: Equipment) -> None:
        self.repository.delete(equipment)

        self.db.commit()
