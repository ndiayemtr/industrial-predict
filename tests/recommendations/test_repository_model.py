from datetime import datetime, timezone

import pytest
from sqlalchemy import DateTime, JSON, inspect, select
from sqlalchemy.exc import IntegrityError

from app.models.equipment import Equipment
from app.models.maintenance_recommendation import MaintenanceRecommendation
from app.schemas.recommendation import RecommendationSignals
from predictions.support import as_utc
from recommendations.support import START, create_data, filter_cases


def test_create_roundtrips_all_fields_and_json(repository, db):
    signals = RecommendationSignals(anomaly_score=.6, failure_probability=.8, health_score=42., rul_hours=18.)
    data = create_data(signals=signals)
    before = datetime.now(timezone.utc)
    record = repository.create(data)
    after = datetime.now(timezone.utc)
    record_id = record.id
    assert record_id is not None
    db.expunge_all()
    loaded = repository.get_by_id(record_id)
    for name in ["equipment_id", "priority", "recommendation_type", "title", "reason", "recommended_action"]:
        assert getattr(loaded, name) == getattr(data, name)
    assert loaded.signals == signals.model_dump()
    assert as_utc(loaded.generated_at) == START
    assert before <= as_utc(loaded.created_at) <= after
    assert loaded.equipment.id == 1
    assert loaded in loaded.equipment.maintenance_recommendations


def test_model_column_mapping_and_foreign_key():
    table = MaintenanceRecommendation.__table__
    assert table.name == "maintenance_recommendations"
    assert set(table.columns.keys()) == {"id", "equipment_id", "priority", "recommendation_type",
        "title", "reason", "recommended_action", "signals", "generated_at", "created_at"}
    assert all(not column.nullable for column in table.columns)
    assert table.c.id.primary_key
    assert isinstance(table.c.signals.type, JSON)
    for field in ["generated_at", "created_at"]:
        assert isinstance(table.c[field].type, DateTime)
        assert table.c[field].type.timezone
    foreign_key = next(iter(table.c.equipment_id.foreign_keys))
    assert foreign_key.target_fullname == "equipments.id"
    assert foreign_key.ondelete == "CASCADE"
    assert inspect(MaintenanceRecommendation).relationships.equipment.back_populates == "maintenance_recommendations"


def test_missing_ids_return_none(repository):
    assert repository.get_by_id(999) is None
    assert repository.get_latest_by_equipment(999) is None


def test_latest_scoped_to_equipment_and_time_then_id(repository, history):
    # Remove latest via ORM, so tied generated_at must be resolved by id.
    assert repository.get_latest_by_equipment(1).id == history["latest"].id
    assert repository.get_latest_by_equipment(2).id == history["foreign"].id
    repository.db.delete(history["latest"])
    repository.db.flush()
    assert repository.get_latest_by_equipment(1).id == history["tie_last"].id


@pytest.mark.parametrize("filters,names", filter_cases())
def test_filters_order_and_total(repository, history, filters, names):
    rows, total = repository.list_by_equipment(equipment_id=1, **filters)
    assert [row.id for row in rows] == [history[name].id for name in names]
    assert total == len(names)
    paged, paged_total = repository.list_by_equipment(equipment_id=1, offset=1, limit=1, **filters)
    assert [row.id for row in paged] == [history[name].id for name in names[1:2]]
    assert paged_total == len(names)


@pytest.mark.parametrize("offset,limit,names", [
    (0, 2, ["latest", "tie_last"]), (1, 2, ["tie_last", "tie_first"]),
    (3, 10, ["early"]), (10, 2, []),
])
def test_offset_limit_do_not_change_total(repository, history, offset, limit, names):
    items, total = repository.list_by_equipment(equipment_id=1, offset=offset, limit=limit)
    assert [row.id for row in items] == [history[name].id for name in names]
    assert total == 4


def test_empty_equipment_list(repository, history):
    assert repository.list_by_equipment(equipment_id=999) == ([], 0)


def test_foreign_key_rejects_nonexistent_equipment(repository, db):
    with pytest.raises(IntegrityError):
        with db.begin_nested():
            repository.create(create_data(equipment_id=999))


def test_deleting_equipment_cascades_recommendations(repository, db):
    # Equipment 4 has no predictions or maintenance fixtures referencing it.
    record_id = repository.create(create_data(equipment_id=4)).id
    equipment = db.get(Equipment, 4)
    db.delete(equipment)
    db.flush()
    db.expunge_all()
    assert repository.get_by_id(record_id) is None
    assert db.scalar(select(MaintenanceRecommendation.id).where(
        MaintenanceRecommendation.equipment_id == 4)) is None
