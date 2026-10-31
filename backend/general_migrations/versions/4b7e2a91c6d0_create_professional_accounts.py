"""Create explicit B2B accounts and grants; execution remains disabled."""

from alembic import op
import sqlalchemy as sa


revision = "4b7e2a91c6d0"
down_revision = "12e2fc65f372"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "local_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id > 0", name="ck_local_users_positive_id"),
        sa.CheckConstraint("state IN ('active', 'suspended')", name="ck_local_users_state"),
        schema="public",
    )
    op.create_table(
        "external_identities",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("issuer", sa.String(2048), nullable=False),
        sa.Column("subject", sa.String(2048), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id > 0", name="ck_external_identities_positive_id"),
        sa.CheckConstraint("issuer <> '' AND issuer = trim(issuer)", name="ck_external_identities_issuer"),
        sa.CheckConstraint("subject <> '' AND subject = trim(subject)", name="ck_external_identities_subject"),
        sa.CheckConstraint("octet_length(issuer) + octet_length(subject) <= 2048", name="ck_external_identities_key_bytes"),
        sa.UniqueConstraint("issuer", "subject", name="uq_external_identities_key"),
        sa.ForeignKeyConstraint(["user_id"], ["public.local_users.id"], name="fk_external_identities_user", ondelete="RESTRICT"),
        schema="public",
    )
    op.create_index("ix_external_identities_user_id", "external_identities", ["user_id"], unique=False, schema="public")
    op.create_table(
        "company_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id > 0", name="ck_company_memberships_positive_id"),
        sa.CheckConstraint("company_id > 0", name="ck_company_memberships_positive_company_id"),
        sa.CheckConstraint("state IN ('active', 'inactive')", name="ck_company_memberships_state"),
        sa.CheckConstraint("role IN ('reader', 'technician', 'company_admin')", name="ck_company_memberships_role"),
        sa.UniqueConstraint("user_id", "company_id", name="uq_company_memberships_user_company"),
        sa.UniqueConstraint("id", "role", name="uq_company_memberships_id_role"),
        sa.ForeignKeyConstraint(["user_id"], ["public.local_users.id"], name="fk_company_memberships_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["company_id"], ["public.companies.id"], name="fk_company_memberships_company", ondelete="RESTRICT"),
        schema="public",
    )
    op.create_index("ix_company_memberships_company_id", "company_memberships", ["company_id"], unique=False, schema="public")
    op.create_table(
        "membership_permissions",
        sa.Column("membership_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(32), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("membership_id", "permission"),
        sa.ForeignKeyConstraint(["membership_id", "role"], ["public.company_memberships.id", "public.company_memberships.role"], name="fk_membership_permissions_membership_role", ondelete="RESTRICT"),
        sa.CheckConstraint("(role IN ('reader', 'technician', 'company_admin') AND permission IN ('companies:read', 'assets:read', 'measurements:read', 'predictions:read')) OR (role IN ('technician', 'company_admin') AND permission = 'maintenance:write') OR (role = 'company_admin' AND permission = 'memberships:manage')", name="ck_membership_permissions_role_cap"),
        schema="public",
    )


def downgrade() -> None:
    op.drop_table("membership_permissions", schema="public")
    op.drop_index("ix_company_memberships_company_id", table_name="company_memberships", schema="public")
    op.drop_table("company_memberships", schema="public")
    op.drop_index("ix_external_identities_user_id", table_name="external_identities", schema="public")
    op.drop_table("external_identities", schema="public")
    op.drop_table("local_users", schema="public")
