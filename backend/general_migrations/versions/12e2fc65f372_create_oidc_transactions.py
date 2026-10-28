"""Create private OIDC transaction storage; statically published, never auto-run."""

from alembic import op
import sqlalchemy as sa


revision = "12e2fc65f372"
down_revision = "09ac8101e9fe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oidc_transactions",
        sa.Column("transaction_id", sa.String(64), nullable=False),
        sa.Column("state_digest", sa.String(64), nullable=False),
        sa.Column("browser_binding_digest", sa.String(64), nullable=False),
        sa.Column("policy_digest", sa.String(64), nullable=False),
        sa.Column("nonce", sa.String(43), nullable=False),
        sa.Column("code_verifier", sa.String(43), nullable=False),
        sa.Column("issuer", sa.String(2048), nullable=False),
        sa.Column("client_id", sa.String(512), nullable=False),
        sa.Column("callback_url", sa.String(2048), nullable=False),
        sa.Column("return_target", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("contract_version", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("transaction_id", name="pk_oidc_transactions"),
        sa.UniqueConstraint("state_digest", name="uq_oidc_transactions_state_digest"),
        sa.CheckConstraint("transaction_id ~ '^[0-9a-f]{64}$'", name="ck_oidc_transactions_transaction_id_hex"),
        sa.CheckConstraint("state_digest ~ '^[0-9a-f]{64}$'", name="ck_oidc_transactions_state_digest_hex"),
        sa.CheckConstraint("browser_binding_digest ~ '^[0-9a-f]{64}$'", name="ck_oidc_transactions_browser_binding_digest_hex"),
        sa.CheckConstraint("policy_digest ~ '^[0-9a-f]{64}$'", name="ck_oidc_transactions_policy_digest_hex"),
        sa.CheckConstraint("expires_at > created_at", name="ck_oidc_transactions_expiry"),
        sa.CheckConstraint("char_length(nonce) = 43", name="ck_oidc_transactions_nonce_length"),
        sa.CheckConstraint("char_length(code_verifier) = 43", name="ck_oidc_transactions_code_verifier_length"),
        schema="public",
    )
    op.create_index("ix_oidc_transactions_expires_at", "oidc_transactions", ["expires_at"], unique=False, schema="public")


def downgrade() -> None:
    op.drop_index("ix_oidc_transactions_expires_at", table_name="oidc_transactions", schema="public")
    op.drop_table("oidc_transactions", schema="public")
