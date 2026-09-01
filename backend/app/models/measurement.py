from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.sensor import Sensor


class Measurement(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    sensor_id: Mapped[int] = mapped_column(
        ForeignKey("sensors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    value: Mapped[float] = mapped_column(
        Float,
        nullable=False,
    )

    quality: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="good",
    )

    sensor: Mapped["Sensor"] = relationship(
        back_populates="measurements",
    )