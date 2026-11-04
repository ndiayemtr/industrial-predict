"""Extend the role ceiling only; no permission is automatically granted."""

from alembic import op

revision = "b2b_0002_analyze"
down_revision = "b2b_0001_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_membership_permissions_role_cap", "membership_permissions", type_="check", schema="public")
    op.create_check_constraint(
        "ck_membership_permissions_role_cap",
        "membership_permissions",
        "(role IN ('reader', 'technician', 'company_admin') AND permission IN ('companies:read', 'assets:read', 'measurements:read', 'predictions:read')) OR (role IN ('technician', 'company_admin') AND permission = 'maintenance:write') OR (role = 'company_admin' AND permission IN ('memberships:manage', 'predictions:analyze'))",
        schema="public",
    )


def downgrade() -> None:
    raise RuntimeError("B2B_ANALYSIS_DOWNGRADE_REQUIRES_SEPARATE_APPROVAL")
