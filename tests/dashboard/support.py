import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import create_autospec, patch
from uuid import uuid4

# Never load the development database URL, even when app.main is imported.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema

from app.core.database import Base
from app.models import Company, Equipment, MaintenanceRecord, Measurement, Sensor, Site
from app.repositories.dashboard_repository import DashboardRepository
from app.services.dashboard_service import DashboardService

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(days=3)
NOW = END + timedelta(days=1)


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return NOW.astimezone(tz) if tz else NOW.replace(tzinfo=None)


class DatabaseCase(unittest.TestCase):
    """Fresh database per test; optional PostgreSQL schema rolled back afterwards."""

    def setUp(self):
        url = os.environ.get("DASHBOARD_TEST_DATABASE_URL", "sqlite:///:memory:")
        self.engine = create_engine(
            url, connect_args={"check_same_thread": False} if url.startswith("sqlite:") else {},
        )
        self.addCleanup(self.engine.dispose)
        if self.engine.dialect.name == "sqlite":
            @event.listens_for(self.engine, "connect")
            def enable_foreign_keys(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
        elif self.engine.dialect.name != "postgresql":
            raise ValueError("Tests support SQLite or PostgreSQL only")
        connection = self.engine.connect()
        self.addCleanup(connection.close)
        transaction = connection.begin()
        self.addCleanup(transaction.rollback)
        if self.engine.dialect.name == "postgresql":
            schema = "dashboard_test_" + uuid4().hex
            connection.execute(CreateSchema(schema))
            connection = connection.execution_options(schema_translate_map={None: schema})
        Base.metadata.create_all(connection)
        self.db = Session(connection)
        self.addCleanup(self.db.close)
        self.repo = DashboardRepository(self.db)
        self.seed_assets()

    def seed_assets(self):
        self.db.add_all([Company(id=i, name=str(i), code=str(i)) for i in (1, 2, 3)])
        self.db.flush()
        self.db.add_all([
            Site(id=i, name=str(i), code=str(i), company_id=c)
            for i, c in ((1, 1), (2, 1), (3, 2), (4, 1))
        ])
        self.db.flush()
        self.db.add_all([
            Equipment(id=i, name=str(i), code=str(i), site_id=s,
                      equipment_type="pump", status=status, criticality=criticality)
            for i, s, status, criticality in (
                (1, 1, "operational", "high"), (2, 1, "custom", "custom"),
                (3, 2, "maintenance", "critical"), (4, 3, "out_of_service", "high"),
            )
        ])
        self.db.flush()
        self.db.add_all([
            Sensor(id=i, name=str(i), code=str(i), equipment_id=e,
                   sensor_type="temperature", unit="C", status=status)
            for i, e, status in (
                (1, 1, "active"), (2, 1, "active"), (3, 1, "inactive"),
                (4, 3, "active"), (5, 4, "active"), (6, 1, "custom"),
            )
        ])
        self.db.flush()

    def measurement(self, sensor_id=1, timestamp=START, quality="good", **kwargs):
        row = Measurement(sensor_id=sensor_id, timestamp=timestamp,
                          quality=quality, value=kwargs.pop("value", 1.0), **kwargs)
        self.db.add(row)
        self.db.flush()
        return row

    def maintenance(self, equipment_id=1, **kwargs):
        values = dict(title="test", status="completed", completed_at=START,
                      maintenance_type="preventive")
        values.update(kwargs)
        row = MaintenanceRecord(equipment_id=equipment_id, **values)
        self.db.add(row)
        self.db.flush()
        return row

    @staticmethod
    def counts(rows):
        return {row["value"]: row["count"] for row in rows}


class ServiceCase(DatabaseCase):
    """Real scope repositories, deterministic aggregate inputs, fixed clock."""

    def setUp(self):
        super().setUp()
        self.clock = patch("app.services.dashboard_service.datetime", FixedDatetime)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.service = DashboardService(self.db)
        self.aggregates = create_autospec(DashboardRepository, instance=True)
        self.service.repository = self.aggregates
        for name in dir(DashboardRepository):
            if name.startswith("count_"):
                getattr(self.aggregates, name).return_value = 0
            elif name.startswith("get_"):
                getattr(self.aggregates, name).return_value = []
        for name in ("get_completed_downtime_aggregate", "get_completed_cost_aggregate"):
            getattr(self.aggregates, name).return_value = {
                "eligible_records": 0, "valid_values": 0, "valid_sum": None,
            }

    def dashboard(self, **kwargs):
        args = dict(company_id=1, start_time=START, end_time=END)
        args.update(kwargs)
        return self.service.get_dashboard(**args)
