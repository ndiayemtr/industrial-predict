from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.orm import Base


class MaintenanceRecommendation(Base):
    __tablename__ = "maintenance_recommendations"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    equipment_id: Mapped[int] = mapped_column(
        ForeignKey(
            "equipments.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    priority: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    recommendation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    recommended_action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    signals: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )

    equipment = relationship(
        "Equipment",
        back_populates="maintenance_recommendations",
    )