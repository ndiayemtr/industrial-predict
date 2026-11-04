"""Closed permission ceiling, inspected as AST only; no migration execution."""

from sqlalchemy import CheckConstraint
from app import general_migrations as guards
from app.models.professional_account import MembershipPermissionRecord
from core.test_application_session_migration import operations
from core.test_general_migrations import no_database_or_migration_commands


def test_only_check_replacement_and_no_automatic_grant():
    ops = operations(guards.GENERAL_DIRECTORY / "versions/b2b_0002_analyze.py")
    assert [op[0] for op in ops] == ["drop_constraint", "create_check_constraint"]
    assert ops[0] == ("drop_constraint", ("ck_membership_permissions_role_cap", "membership_permissions"), {"type_": "check", "schema": "public"})
    check = next(c for c in MembershipPermissionRecord.__table__.constraints if isinstance(c, CheckConstraint))
    assert ops[1] == ("create_check_constraint", (check.name, "membership_permissions", str(check.sqltext)), {"schema": "public"})
    historical = operations(guards.GENERAL_DIRECTORY / "versions/4b7e2a91c6d0_create_professional_accounts.py")
    permission_table = next(args for kind, args, kw in historical if kind == "create_table" and args[0] == "membership_permissions")
    historical_check = next(args[0] for kind, args, kw in permission_table[1:] if kind == "CheckConstraint")
    assert str(check.sqltext) == historical_check.replace("permission = 'memberships:manage'", "permission IN ('memberships:manage', 'predictions:analyze')")
