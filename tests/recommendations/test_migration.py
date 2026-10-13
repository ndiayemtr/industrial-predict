"""Read the migration AST only: never execute upgrade or downgrade."""

import ast
from pathlib import Path

import pytest


@pytest.fixture
def migration():
    project = Path(__file__).resolve().parents[2]
    path = project / "backend" / "migrations" / "versions" / "09ac8101e9fe_add_maintenance_recommendations.py"
    assert path.is_file()
    return ast.parse(path.read_text(encoding="utf-8"))


def calls(function, name):
    return [node for node in ast.walk(function) if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute) and node.func.attr == name]


def test_revision_and_parent_are_declared(migration):
    assignments = {node.target.id: ast.literal_eval(node.value) for node in migration.body
                   if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}
    assert assignments["revision"] == "09ac8101e9fe"
    assert assignments["down_revision"] == "d6ec01cf13b6"


def test_upgrade_targets_expected_table_columns_and_fk(migration):
    upgrade = next(node for node in migration.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    tables = calls(upgrade, "create_table")
    assert len(tables) == 1
    assert ast.literal_eval(tables[0].args[0]) == "maintenance_recommendations"
    columns = calls(tables[0], "Column")
    assert {ast.literal_eval(column.args[0]) for column in columns} == {
        "id", "equipment_id", "priority", "recommendation_type", "title", "reason",
        "recommended_action", "signals", "generated_at", "created_at"}
    for column in columns:
        assert next(ast.literal_eval(kw.value) for kw in column.keywords if kw.arg == "nullable") is False
    foreign_keys = calls(tables[0], "ForeignKeyConstraint")
    assert len(foreign_keys) == 1
    assert ast.literal_eval(foreign_keys[0].args[0]) == ["equipment_id"]
    assert ast.literal_eval(foreign_keys[0].args[1]) == ["equipments.id"]
    assert next(ast.literal_eval(kw.value) for kw in foreign_keys[0].keywords if kw.arg == "ondelete") == "CASCADE"
    primary_key = calls(tables[0], "PrimaryKeyConstraint")
    assert [ast.literal_eval(arg) for arg in primary_key[0].args] == ["id"]
    assert not calls(upgrade, "drop_table")


def test_indexes_and_downgrade_are_scoped_to_recommendations(migration):
    functions = {node.name: node for node in migration.body if isinstance(node, ast.FunctionDef)}
    indexes = calls(functions["upgrade"], "create_index")
    assert len(indexes) == 4
    assert {tuple(ast.literal_eval(call.args[2])) for call in indexes} == {
        ("id",), ("equipment_id",), ("priority",), ("recommendation_type",)}
    assert all(ast.literal_eval(call.args[1]) == "maintenance_recommendations" for call in indexes)
    drops = calls(functions["downgrade"], "drop_table")
    assert len(drops) == 1
    assert ast.literal_eval(drops[0].args[0]) == "maintenance_recommendations"
