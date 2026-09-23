from sqlalchemy.orm import Session

from app.core.pagination import build_page

from app.models.sensor import Sensor
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.sensor_repository import SensorRepository
from app.schemas.sensor import SensorCreate, SensorUpdate


class SensorService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = SensorRepository(db)
        self.equipment_repository = EquipmentRepository(db)

    def get_paginated(
        self,
        *,
        page: int,
        page_size: int,
        equipment_id: int | None = None,
        status: str | None = None,
        search: str | None = None,
    ):
        offset = (page - 1) * page_size
        
        if search is not None:
            search = search.strip()

            if not search:
                search = None

        items = self.repository.get_paginated(
            offset=offset,
            limit=page_size,
            equipment_id=equipment_id,
            status=status,
            search=search,
        )

        total = self.repository.count_all(
            equipment_id=equipment_id,
            status=status,
            search=search,
        )

        return build_page(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    def get_all(self) -> list[Sensor]:
        return self.repository.get_all()

    def get_by_id(self, sensor_id: int) -> Sensor | None:
        return self.repository.get_by_id(sensor_id)

    def get_by_equipment_id(
        self,
        equipment_id: int,
    ) -> list[Sensor]:
        return self.repository.get_by_equipment_id(equipment_id)

    def create(self, data: SensorCreate) -> Sensor:
        # Vérifier que l'Equipment existe
        equipment = self.equipment_repository.get_by_id(
            data.equipment_id
        )

        if equipment is None:
            raise ValueError(
                f"Equipment with id '{data.equipment_id}' does not exist."
            )

        # Vérifier l'unicité du code
        existing_sensor = self.repository.get_by_code(data.code)

        if existing_sensor:
            raise ValueError(
                f"Sensor with code '{data.code}' already exists."
            )

        sensor = Sensor(
            name=data.name,
            code=data.code,
            sensor_type=data.sensor_type,
            unit=data.unit,
            description=data.description,
            status=data.status,
            equipment_id=data.equipment_id,
        )

        self.repository.create(sensor)

        self.db.commit()
        self.db.refresh(sensor)

        return sensor

    def update(
        self,
        sensor: Sensor,
        data: SensorUpdate,
    ) -> Sensor:

        update_data = data.model_dump(exclude_unset=True)

        # Vérifier le nouvel Equipment
        if "equipment_id" in update_data:
            equipment = self.equipment_repository.get_by_id(
                update_data["equipment_id"]
            )

            if equipment is None:
                raise ValueError(
                    f"Equipment with id "
                    f"'{update_data['equipment_id']}' "
                    f"does not exist."
                )

        # Vérifier l'unicité du code
        if "code" in update_data:
            existing_sensor = self.repository.get_by_code(
                update_data["code"]
            )

            if (
                existing_sensor
                and existing_sensor.id != sensor.id
            ):
                raise ValueError(
                    f"Sensor with code "
                    f"'{update_data['code']}' already exists."
                )

        # Appliquer les modifications
        for field, value in update_data.items():
            setattr(sensor, field, value)

        self.repository.update(sensor)

        self.db.commit()
        self.db.refresh(sensor)

        return sensor

    def delete(self, sensor: Sensor) -> None:
        self.repository.delete(sensor)

        self.db.commit()
