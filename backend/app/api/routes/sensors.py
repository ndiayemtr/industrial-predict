from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.pagination import Page
from app.schemas.sensor import (
    SensorCreate,
    SensorRead,
    SensorUpdate,
)
from app.services.sensor_service import SensorService


router = APIRouter(
    prefix="/sensors",
    tags=["Sensors"],
)


@router.get(
    "",
    response_model=Page[SensorRead],
)
def get_sensors(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = SensorService(db)

    return service.get_paginated(
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{sensor_id}",
    response_model=SensorRead,
)
def get_sensor(
    sensor_id: int,
    db: Session = Depends(get_db),
):
    service = SensorService(db)

    sensor = service.get_by_id(sensor_id)

    if sensor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found",
        )

    return sensor


@router.get(
    "/equipment/{equipment_id}",
    response_model=list[SensorRead],
)
def get_sensors_by_equipment(
    equipment_id: int,
    db: Session = Depends(get_db),
):
    service = SensorService(db)

    return service.get_by_equipment_id(equipment_id)


@router.post(
    "",
    response_model=SensorRead,
    status_code=status.HTTP_201_CREATED,
)
def create_sensor(
    data: SensorCreate,
    db: Session = Depends(get_db),
):
    service = SensorService(db)

    try:
        return service.create(data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.patch(
    "/{sensor_id}",
    response_model=SensorRead,
)
def update_sensor(
    sensor_id: int,
    data: SensorUpdate,
    db: Session = Depends(get_db),
):
    service = SensorService(db)

    sensor = service.get_by_id(sensor_id)

    if sensor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found",
        )

    try:
        return service.update(sensor, data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.delete(
    "/{sensor_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_sensor(
    sensor_id: int,
    db: Session = Depends(get_db),
):
    service = SensorService(db)

    sensor = service.get_by_id(sensor_id)

    if sensor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensor not found",
        )

    service.delete(sensor)

    return None
