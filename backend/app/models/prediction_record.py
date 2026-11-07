from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class PredictionRecord(Base):
    __tablename__ = "prediction_records"
    __table_args__ = (
        UniqueConstraint("id", "p101_operation_id", name="uq_prediction_records_p101_pair"),
        ForeignKeyConstraint(
            ["p101_operation_id", "id"],
            ["p101_prediction_operations.id", "p101_prediction_operations.prediction_id"],
            name="fk_prediction_records_p101_operation", match="SIMPLE",
            ondelete="RESTRICT", onupdate="RESTRICT", deferrable=True, initially="DEFERRED",
            use_alter=True,
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement="ignore_fk",  # Preserve generated ids despite the composite circular FK.
        index=True,
    )

    # NULL preserves the historical, unjournaled prediction lifecycle.
    p101_operation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    equipment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "equipments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sensor_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "sensors.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    measurement_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "measurements.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    prediction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    level: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    is_alert: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
    )

    model_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    model_version: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    horizon_hours: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    predicted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
