from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.pagination import Page
from app.schemas.equipment import (
    EquipmentCreate,
    EquipmentRead,
    EquipmentUpdate,
)
from app.services.equipment_service import EquipmentService


router = APIRouter(
    prefix="/equipments",
    tags=["Equipments"],
)


@router.get(
    "",
    response_model=Page[EquipmentRead],
)
def get_equipments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = EquipmentService(db)

    return service.get_paginated(
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{equipment_id}",
    response_model=EquipmentRead,
)
def get_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
):
    service = EquipmentService(db)

    equipment = service.get_by_id(equipment_id)

    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    return equipment


@router.get(
    "/site/{site_id}",
    response_model=list[EquipmentRead],
)
def get_equipments_by_site(
    site_id: int,
    db: Session = Depends(get_db),
):
    service = EquipmentService(db)

    return service.get_by_site_id(site_id)


@router.post(
    "",
    response_model=EquipmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_equipment(
    data: EquipmentCreate,
    db: Session = Depends(get_db),
):
    service = EquipmentService(db)

    try:
        return service.create(data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.patch(
    "/{equipment_id}",
    response_model=EquipmentRead,
)
def update_equipment(
    equipment_id: int,
    data: EquipmentUpdate,
    db: Session = Depends(get_db),
):
    service = EquipmentService(db)

    equipment = service.get_by_id(equipment_id)

    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    try:
        return service.update(equipment, data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.delete(
    "/{equipment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
):
    service = EquipmentService(db)

    equipment = service.get_by_id(equipment_id)

    if equipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Equipment not found",
        )

    service.delete(equipment)

    return None
