"""Opt-in PostgreSQL session metadata only. No engine, registration or DDL."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


CONTRACT_VERSION = "b2b-session-v1"


class ApplicationSessionRecord(Base):
    __tablename__ = "application_sessions"
    __table_args__ = (
        PrimaryKeyConstraint("secret_digest", name="pk_application_sessions"),
        ForeignKeyConstraint(["user_id"], ["local_users.id"], name="fk_application_sessions_user", ondelete="RESTRICT"),
        ForeignKeyConstraint(["external_identity_id"], ["external_identities.id"],
                             name="fk_application_sessions_external_identity", ondelete="RESTRICT"),
        ForeignKeyConstraint(["replaced_by"], ["application_sessions.secret_digest"],
                             name="fk_application_sessions_replacement", ondelete="RESTRICT"),
        *(CheckConstraint(f"{column} ~ '^[0-9a-f]{{64}}$'", name=f"ck_application_sessions_{column}_hex")
          for column in ("secret_digest", "csrf_digest")),
        CheckConstraint("user_id > 0 AND external_identity_id > 0", name="ck_application_sessions_positive_ids"),
        CheckConstraint("idle_timeout_seconds > 0 AND absolute_timeout_seconds >= idle_timeout_seconds",
                        name="ck_application_sessions_policy"),
        CheckConstraint("authenticated_at <= created_at AND created_at <= last_activity_at "
                        "AND last_activity_at < absolute_expires_at", name="ck_application_sessions_times"),
        CheckConstraint("absolute_expires_at = authenticated_at + absolute_timeout_seconds * interval '1 second'",
                        name="ck_application_sessions_absolute_expiry"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= last_activity_at", name="ck_application_sessions_revocation"),
        CheckConstraint("replaced_by IS NULL OR (revoked_at IS NOT NULL AND replaced_by <> secret_digest)",
                        name="ck_application_sessions_rotation"),
        CheckConstraint("contract_version = 'b2b-session-v1'", name="ck_application_sessions_contract"),
        Index("ix_application_sessions_user", "user_id", "secret_digest"),
        Index("ix_application_sessions_expiry", "absolute_expires_at"),
    )

    secret_digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    external_identity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    absolute_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    idle_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    absolute_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by: Mapped[str | None] = mapped_column(String(64))
    contract_version: Mapped[str] = mapped_column(String(32), nullable=False)
