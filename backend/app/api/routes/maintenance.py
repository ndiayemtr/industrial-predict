from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.maintenance import (
    MaintenanceCreate,
    MaintenanceRead,
    MaintenanceUpdate,
)
from app.services.maintenance_service import MaintenanceService


router = APIRouter(
    prefix="/maintenance",
    tags=["Maintenance"],
)


@router.get(
    "",
    response_model=list[MaintenanceRead],
)
def get_maintenance_records(
    db: Session = Depends(get_db),
):
    service = MaintenanceService(db)

    return service.get_all()


@router.get(
    "/equipment/{equipment_id}",
    response_model=list[MaintenanceRead],
)
def get_maintenance_by_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
):
    service = MaintenanceService(db)

    try:
        return service.get_by_equipment_id(
            equipment_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get(
    "/{maintenance_id}",
    response_model=MaintenanceRead,
)
def get_maintenance(
    maintenance_id: int,
    db: Session = Depends(get_db),
):
    service = MaintenanceService(db)

    maintenance = service.get_by_id(
        maintenance_id
    )

    if not maintenance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance record not found",
        )

    return maintenance


@router.post(
    "",
    response_model=MaintenanceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_maintenance(
    data: MaintenanceCreate,
    db: Session = Depends(get_db),
):
    service = MaintenanceService(db)

    try:
        return service.create(data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.patch(
    "/{maintenance_id}",
    response_model=MaintenanceRead,
)
def update_maintenance(
    maintenance_id: int,
    data: MaintenanceUpdate,
    db: Session = Depends(get_db),
):
    service = MaintenanceService(db)

    maintenance = service.get_by_id(
        maintenance_id
    )

    if not maintenance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance record not found",
        )

    try:
        return service.update(
            maintenance,
            data,
        )

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.delete(
    "/{maintenance_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_maintenance(
    maintenance_id: int,
    db: Session = Depends(get_db),
):
    service = MaintenanceService(db)

    maintenance = service.get_by_id(
        maintenance_id
    )

    if not maintenance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Maintenance record not found",
        )

    service.delete(maintenance)