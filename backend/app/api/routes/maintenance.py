from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.pagination import Page
from app.schemas.maintenance import (
    MaintenanceCreate,
    MaintenanceRead,
    MaintenanceUpdate,
)
from app.services.maintenance_service import MaintenanceService
from app.core.enums import MaintenancePriority, MaintenanceStatus, MaintenanceType


router = APIRouter(
    prefix="/maintenance",
    tags=["Maintenance"],
)


@router.get(
    "",
    response_model=Page[MaintenanceRead],
)
def get_maintenance_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    equipment_id: int | None = Query(default=None, ge=1),
    maintenance_type: MaintenanceType | None = Query(default=None),
    maintenance_status: MaintenanceStatus | None = Query(
        default=None,
        alias="status",
    ),
    priority: MaintenancePriority | None = Query(default=None),
    start_time: datetime | None = Query(default=None),
    end_time: datetime | None = Query(default=None),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    db: Session = Depends(get_db),
):
    service = MaintenanceService(db)

    try:
        return service.get_paginated(
            page=page,
            page_size=page_size,
            equipment_id=equipment_id,
            maintenance_type=maintenance_type,
            status=maintenance_status,
            priority=priority,
            start_time=start_time,
            end_time=end_time,
            search=search,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


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
