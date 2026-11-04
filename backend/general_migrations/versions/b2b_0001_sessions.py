"""B2B session metadata publication only; execution remains disabled."""

from alembic import op
import sqlalchemy as sa

revision = "b2b_0001_sessions"
down_revision = "4b7e2a91c6d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint("uq_external_identities_id_user", "external_identities", ["id", "user_id"], schema="public")
    op.create_table(
        "application_sessions",
        sa.Column("secret_digest", sa.String(64), nullable=False),
        sa.Column("csrf_digest", sa.String(64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("external_identity_id", sa.Integer(), nullable=False),
        sa.Column("authenticated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("absolute_timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by", sa.String(64), nullable=True),
        sa.Column("contract_version", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("secret_digest", name="pk_application_sessions"),
        sa.ForeignKeyConstraint(["user_id"], ["public.local_users.id"], name="fk_application_sessions_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["external_identity_id", "user_id"], ["public.external_identities.id", "public.external_identities.user_id"], name="fk_application_sessions_external_identity_user", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["replaced_by"], ["public.application_sessions.secret_digest"], name="fk_application_sessions_replacement", ondelete="RESTRICT"),
        sa.CheckConstraint("secret_digest ~ '^[0-9a-f]{64}$'", name="ck_application_sessions_secret_digest_hex"),
        sa.CheckConstraint("csrf_digest ~ '^[0-9a-f]{64}$'", name="ck_application_sessions_csrf_digest_hex"),
        sa.CheckConstraint("user_id > 0 AND external_identity_id > 0", name="ck_application_sessions_positive_ids"),
        sa.CheckConstraint("idle_timeout_seconds > 0 AND absolute_timeout_seconds >= idle_timeout_seconds", name="ck_application_sessions_policy"),
        sa.CheckConstraint("authenticated_at <= created_at AND created_at <= last_activity_at AND last_activity_at < absolute_expires_at", name="ck_application_sessions_times"),
        sa.CheckConstraint("absolute_expires_at = authenticated_at + absolute_timeout_seconds * interval '1 second'", name="ck_application_sessions_absolute_expiry"),
        sa.CheckConstraint("revoked_at IS NULL OR revoked_at >= last_activity_at", name="ck_application_sessions_revocation"),
        sa.CheckConstraint("replaced_by IS NULL OR (revoked_at IS NOT NULL AND replaced_by <> secret_digest)", name="ck_application_sessions_rotation"),
        sa.CheckConstraint("contract_version = 'b2b-session-v1'", name="ck_application_sessions_contract"),
        schema="public",
    )
    op.create_index("ix_application_sessions_user", "application_sessions", ["user_id", "secret_digest"], unique=False, schema="public")
    op.create_index("ix_application_sessions_expiry", "application_sessions", ["absolute_expires_at"], unique=False, schema="public")


def downgrade() -> None:
    raise RuntimeError("B2B_SESSION_DOWNGRADE_REQUIRES_SEPARATE_APPROVAL")
