from sqlalchemy.orm import Session

from app.models.prediction_record import PredictionRecord
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.prediction_repository import PredictionRepository
from app.schemas.prediction_record import PredictionRecordCreate
from app.core.enums import PredictionType
from app.anomaly_detection.schemas import AnomalyResult
from datetime import datetime
from app.ml.health_score.schemas import HealthScoreResult
from datetime import datetime

from app.core.pagination import build_page


class PredictionService:

    def __init__(self, db: Session):
        self.db = db
        self.repository = PredictionRepository(db)
        self.equipment_repository = EquipmentRepository(db)

    def create(
        self,
        data: PredictionRecordCreate,
    ) -> PredictionRecord:

        equipment = self.equipment_repository.get_by_id(
            data.equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        prediction = PredictionRecord(
            equipment_id=data.equipment_id,
            sensor_id=data.sensor_id,
            measurement_id=data.measurement_id,
            prediction_type=data.prediction_type.value,
            score=data.score,
            level=data.level,
            is_alert=data.is_alert,
            model_name=data.model_name,
            model_version=data.model_version,
            horizon_hours=data.horizon_hours,
            details=data.details,
            predicted_at=data.predicted_at,
        )

        self.repository.create(prediction)

        self.db.commit()
        self.db.refresh(prediction)

        return prediction

    def get_by_id(
        self,
        prediction_id: int,
    ) -> PredictionRecord | None:

        return self.repository.get_by_id(
            prediction_id
        )

    def get_by_equipment_id(
        self,
        equipment_id: int,
    ) -> list[PredictionRecord]:

        return self.repository.get_by_equipment_id(
            equipment_id
        )

    def get_latest_by_equipment_and_type(
        self,
        equipment_id: int,
        prediction_type: str,
    ) -> PredictionRecord | None:

        return self.repository.get_latest_by_equipment_and_type(
            equipment_id,
            prediction_type,
        )

    def persist_anomaly(
        self,
        anomaly: AnomalyResult,
    ) -> PredictionRecord:

        if anomaly.equipment_id is None:
            raise ValueError(
                "Anomaly result must contain equipment_id"
            )

        data = PredictionRecordCreate(
            equipment_id=anomaly.equipment_id,
            sensor_id=anomaly.sensor_id,
            measurement_id=anomaly.measurement_id,
            prediction_type=PredictionType.ANOMALY,
            score=anomaly.anomaly_score,
            is_alert=anomaly.is_anomaly,
            model_name=anomaly.method,
            details=(
                {
                    "reason": anomaly.reason,
                }
                if anomaly.reason is not None
                else None
            ),
            predicted_at=anomaly.timestamp,
        )

        return self.create(data)


    def persist_failure_risk(
        self,
        *,
        equipment_id: int,
        failure_probability: float,
        risk_score: float,
        risk_level: str,
        predicted_at: datetime,
        sensor_id: int | None = None,
        measurement_id: int | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
        horizon_hours: float | None = None,
    ) -> PredictionRecord:

        if not 0.0 <= failure_probability <= 1.0:
            raise ValueError(
                "failure_probability must be between 0 and 1"
            )

        data = PredictionRecordCreate(
            equipment_id=equipment_id,
            sensor_id=sensor_id,
            measurement_id=measurement_id,
            prediction_type=PredictionType.FAILURE_RISK,
            score=risk_score,
            level=risk_level,
            model_name=model_name,
            model_version=model_version,
            horizon_hours=horizon_hours,
            details={
                "failure_probability": failure_probability,
            },
            predicted_at=predicted_at,
        )

        return self.create(data)

    def persist_health_score(
        self,
        *,
        equipment_id: int,
        result: HealthScoreResult,
        predicted_at: datetime,
        model_name: str | None = "health_score",
        model_version: str | None = None,
    ) -> PredictionRecord:

        data = PredictionRecordCreate(
            equipment_id=equipment_id,
            prediction_type=PredictionType.HEALTH_SCORE,
            score=result.health_score,
            level=result.health_level,
            model_name=model_name,
            model_version=model_version,
            details={
                "components": {
                    "failure_health": (
                        result.components.failure_health
                    ),
                    "anomaly_health": (
                        result.components.anomaly_health
                    ),
                    "data_quality_health": (
                        result.components.data_quality_health
                    ),
                    "maintenance_health": (
                        result.components.maintenance_health
                    ),
                }
            },
            predicted_at=predicted_at,
        )

        return self.create(data)

    def get_history_for_equipment(
        self,
        equipment_id: int,
    ) -> list[PredictionRecord]:

        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        return self.repository.get_by_equipment_id(
            equipment_id
        )

    def get_paginated(
        self,
        *,
        equipment_id: int,
        page: int,
        page_size: int,
        prediction_type: str | None = None,
        level: str | None = None,
        is_alert: bool | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ):
        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if equipment is None:
            raise LookupError(
                "Equipment not found"
            )

        offset = (page - 1) * page_size

        items = self.repository.get_paginated(
            equipment_id=equipment_id,
            offset=offset,
            limit=page_size,
            prediction_type=prediction_type,
            level=level,
            is_alert=is_alert,
            start_time=start_time,
            end_time=end_time,
        )

        total = self.repository.count_all(
            equipment_id=equipment_id,
            prediction_type=prediction_type,
            level=level,
            is_alert=is_alert,
            start_time=start_time,
            end_time=end_time,
        )

        return build_page(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )