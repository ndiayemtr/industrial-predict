"""Professional account metadata only; no registration by email or runtime I/O.

As with business models, the ORM uses unqualified names; deployments must fix
search_path to public. The guarded revision explicitly creates public objects.
"""

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.orm import Base


class LocalUserRecord(Base):
    __tablename__ = "local_users"
    __table_args__ = (
        CheckConstraint("id > 0", name="ck_local_users_positive_id"),
        CheckConstraint("state IN ('active', 'suspended')", name="ck_local_users_state"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)


class ExternalIdentityRecord(Base):
    __tablename__ = "external_identities"
    __table_args__ = (
        CheckConstraint("id > 0", name="ck_external_identities_positive_id"),
        CheckConstraint("issuer <> '' AND issuer = trim(issuer)", name="ck_external_identities_issuer"),
        CheckConstraint("subject <> '' AND subject = trim(subject)", name="ck_external_identities_subject"),
        # Bound a UTF-8 composite btree key, rather than assuming String lengths
        # alone fit a PostgreSQL index. No truncation/normalization is permitted.
        CheckConstraint("octet_length(issuer) + octet_length(subject) <= 2048", name="ck_external_identities_key_bytes"),
        UniqueConstraint("issuer", "subject", name="uq_external_identities_key"),
        ForeignKeyConstraint(["user_id"], ["local_users.id"], name="fk_external_identities_user", ondelete="RESTRICT"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    issuer: Mapped[str] = mapped_column(String(2048), nullable=False)
    subject: Mapped[str] = mapped_column(String(2048), nullable=False)


class MembershipRecord(Base):
    __tablename__ = "company_memberships"
    __table_args__ = (
        CheckConstraint("id > 0", name="ck_company_memberships_positive_id"),
        CheckConstraint("company_id > 0", name="ck_company_memberships_positive_company_id"),
        CheckConstraint("state IN ('active', 'inactive')", name="ck_company_memberships_state"),
        CheckConstraint("role IN ('reader', 'technician', 'company_admin')", name="ck_company_memberships_role"),
        UniqueConstraint("user_id", "company_id", name="uq_company_memberships_user_company"),
        UniqueConstraint("id", "role", name="uq_company_memberships_id_role"),
        ForeignKeyConstraint(["user_id"], ["local_users.id"], name="fk_company_memberships_user", ondelete="RESTRICT"),
        ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_company_memberships_company", ondelete="RESTRICT"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)


class MembershipPermissionRecord(Base):
    __tablename__ = "membership_permissions"
    __table_args__ = (
        ForeignKeyConstraint(["membership_id", "role"], ["company_memberships.id", "company_memberships.role"],
                             name="fk_membership_permissions_membership_role", ondelete="RESTRICT"),
        CheckConstraint(
            "(role IN ('reader', 'technician', 'company_admin') AND permission IN "
            "('companies:read', 'assets:read', 'measurements:read', 'predictions:read')) OR "
            "(role IN ('technician', 'company_admin') AND permission = 'maintenance:write') OR "
            "(role = 'company_admin' AND permission = 'memberships:manage')",
            name="ck_membership_permissions_role_cap"),
    )
    membership_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    permission: Mapped[str] = mapped_column(String(32), primary_key=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
