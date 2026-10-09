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
from app.core.enums import (
    EquipmentCriticality,
    EquipmentStatus,
    PredictionType,
)
from app.schemas.health_score import (
    HealthScoreRead,
    HealthScoreRequest,
)
from app.services.health_score_service import HealthScoreService
from app.schemas.prediction_record import PredictionRecordRead
from app.services.prediction_service import PredictionService
from datetime import datetime


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
    site_id: int | None = Query(
    default=None,
        ge=1,
    ),

    status: EquipmentStatus | None = Query(
        default=None,
    ),

    criticality: EquipmentCriticality | None = Query(
        default=None,
    ),

    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=100,
    ),
    db: Session = Depends(get_db),
):
    service = EquipmentService(db)

    return service.get_paginated(
        page=page,
        page_size=page_size,
        site_id=site_id,
        status=status,
        criticality=criticality,
        search=search,
    )

@router.post(
    "/{equipment_id}/health-score",
    response_model=HealthScoreRead,
)
def calculate_equipment_health_score(
    equipment_id: int,
    data: HealthScoreRequest,
    db: Session = Depends(get_db),
):
    service = HealthScoreService(db)

    try:
        return service.calculate_for_equipment(
            equipment_id,
            data,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

@router.get(
    "/{equipment_id}/predictions",
    response_model=Page[PredictionRecordRead],
)
def get_equipment_predictions(
    equipment_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    prediction_type: PredictionType | None = Query(
        default=None,
    ),
    level: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
    ),
    is_alert: bool | None = Query(
        default=None,
    ),
    start_time: datetime | None = Query(
        default=None,
    ),
    end_time: datetime | None = Query(
        default=None,
    ),
    db: Session = Depends(get_db),
):
    service = PredictionService(db)

    try:
        return service.get_paginated(
            equipment_id=equipment_id,
            page=page,
            page_size=page_size,
            prediction_type=(
                prediction_type.value
                if prediction_type is not None
                else None
            ),
            level=level,
            is_alert=is_alert,
            start_time=start_time,
            end_time=end_time,
        )

    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
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
