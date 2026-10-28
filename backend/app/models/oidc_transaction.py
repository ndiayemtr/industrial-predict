"""Private, short-lived OIDC material; importing metadata performs no SQL.

Imported explicitly by the adapter. No registration through historical model
exports, migration, relationships, public schema or business identity is added.
"""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, PrimaryKeyConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class OidcTransactionRecord(Base):
    __tablename__ = "oidc_transactions"
    __table_args__ = (
        PrimaryKeyConstraint("transaction_id", name="pk_oidc_transactions"),
        UniqueConstraint("state_digest", name="uq_oidc_transactions_state_digest"),
        *(CheckConstraint(f"{column} ~ '^[0-9a-f]{{64}}$'",
                          name=f"ck_oidc_transactions_{column}_hex")
          for column in ("transaction_id", "state_digest", "browser_binding_digest", "policy_digest")),
        CheckConstraint("expires_at > created_at", name="ck_oidc_transactions_expiry"),
        Index("ix_oidc_transactions_expires_at", "expires_at"),
        {"schema": "public"},
    )

    transaction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    state_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    browser_binding_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    nonce: Mapped[str] = mapped_column(String(43), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(43), nullable=False)
    issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    client_id: Mapped[str] = mapped_column(String(512), nullable=False)
    callback_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    return_target: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    contract_version: Mapped[str] = mapped_column(Text, nullable=False)
