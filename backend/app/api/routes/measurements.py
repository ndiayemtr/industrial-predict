from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.measurement import (
    MeasurementCreate,
    MeasurementRead,
    MeasurementUpdate,
)
from app.services.measurement_service import MeasurementService


router = APIRouter(
    prefix="/measurements",
    tags=["Measurements"],
)


@router.get(
    "",
    response_model=list[MeasurementRead],
)
def get_measurements(
    db: Session = Depends(get_db),
):
    service = MeasurementService(db)

    return service.get_all()


@router.get(
    "/sensor/{sensor_id}",
    response_model=list[MeasurementRead],
)
def get_measurements_by_sensor(
    sensor_id: int,
    db: Session = Depends(get_db),
):
    service = MeasurementService(db)

    try:
        return service.get_by_sensor_id(sensor_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get(
    "/sensor/{sensor_id}/period",
    response_model=list[MeasurementRead],
)
def get_measurements_by_period(
    sensor_id: int,
    start_time: datetime = Query(...),
    end_time: datetime = Query(...),
    db: Session = Depends(get_db),
):
    service = MeasurementService(db)

    try:
        return service.get_by_sensor_and_period(
            sensor_id,
            start_time,
            end_time,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get(
    "/{measurement_id}",
    response_model=MeasurementRead,
)
def get_measurement(
    measurement_id: int,
    db: Session = Depends(get_db),
):
    service = MeasurementService(db)

    measurement = service.get_by_id(measurement_id)

    if not measurement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Measurement not found",
        )

    return measurement


@router.post(
    "",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
)
def create_measurement(
    data: MeasurementCreate,
    db: Session = Depends(get_db),
):
    service = MeasurementService(db)

    try:
        return service.create(data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.patch(
    "/{measurement_id}",
    response_model=MeasurementRead,
)
def update_measurement(
    measurement_id: int,
    data: MeasurementUpdate,
    db: Session = Depends(get_db),
):
    service = MeasurementService(db)

    measurement = service.get_by_id(measurement_id)

    if not measurement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Measurement not found",
        )

    try:
        return service.update(measurement, data)

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.delete(
    "/{measurement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_measurement(
    measurement_id: int,
    db: Session = Depends(get_db),
):
    service = MeasurementService(db)

    measurement = service.get_by_id(measurement_id)

    if not measurement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Measurement not found",
        )

    service.delete(measurement)