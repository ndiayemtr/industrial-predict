"""B-SEN-01 regression tests using only a fresh in-memory SQLite database."""

import os
import unittest

# Configure the application before importing its engine, never the development DB.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.api.routes.sensors import router
from app.models import Company, Equipment, Sensor, Site
from app.repositories.sensor_repository import SensorRepository


class SensorCrudTests(unittest.TestCase):
    def setUp(self):
        # Hardcoded URL: do not consult optional PostgreSQL test environment URLs.
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.addCleanup(self.engine.dispose)

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        with Session(self.engine) as db:
            db.add_all([
                Company(id=1, name="Company A", code="COMP-A"),
                Company(id=2, name="Company B", code="COMP-B"),
            ])
            db.flush()
            db.add_all([
                Site(id=1, name="Site A", code="SITE-A", company_id=1),
                Site(id=2, name="Site B", code="SITE-B", company_id=2),
            ])
            db.flush()
            db.add_all([
                Equipment(id=i, name=f"Equipment {i}", code=f"EQ-{i}",
                          equipment_type="pump", site_id=1 if i < 3 else 2)
                for i in (1, 2, 3)
            ])
            db.flush()
            db.add(Sensor(id=1, **self.payload("SEN-USED")))
            db.commit()

        def isolated_db():
            with Session(self.engine) as db:
                yield db

        # Mount the production router without loading unrelated ML routes.
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1")
        self.app.dependency_overrides[get_db] = isolated_db
        self.addCleanup(self.app.dependency_overrides.clear)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    @staticmethod
    def payload(code, equipment_id=1):
        return dict(name="Temperature", code=code, sensor_type="temperature",
                    unit="C", description="Initial description", status="active",
                    equipment_id=equipment_id)

    def snapshot(self):
        # A separate session verifies committed state, not a cached ORM object.
        with Session(self.engine) as db:
            return [
                {column.name: getattr(sensor, column.name)
                 for column in Sensor.__table__.columns}
                for sensor in db.scalars(select(Sensor).order_by(Sensor.id)).all()
            ]

    def assert_conflict(self, response, code):
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json(), {
            "detail": f"Sensor with code '{code}' already exists."
        })

    def test_get_by_code_uses_exact_global_equality(self):
        before = self.snapshot()
        with Session(self.engine) as db:
            repository = SensorRepository(db)
            sensor = repository.get_by_code("SEN-USED")
            self.assertIsNotNone(sensor)
            self.assertEqual((sensor.id, sensor.equipment_id), (1, 1))
            for code in ("MISSING", "sen-used", " SEN-USED ", "SEN-%", "SEN-USE_"):
                with self.subTest(code=code):
                    self.assertIsNone(repository.get_by_code(code))
        self.assertEqual(self.snapshot(), before)

    def test_post_available_code_returns_201_and_persists(self):
        payload = self.payload("SEN-NEW", equipment_id=2)
        response = self.client.post("/api/v1/sensors", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        body = response.json()
        self.assertNotEqual(body["id"], 1)
        for key, value in payload.items():
            self.assertEqual(body[key], value)
        persisted = self.snapshot()
        self.assertEqual(len(persisted), 2)
        self.assertEqual(persisted[1]["id"], body["id"])
        for key, value in payload.items():
            self.assertEqual(persisted[1][key], value)
        reread = self.client.get(f"/api/v1/sensors/{body['id']}")
        self.assertEqual(reread.status_code, 200, reread.text)
        self.assertEqual(reread.json(), body)

    def test_post_duplicate_code_is_rejected_globally(self):
        before = self.snapshot()
        # Same equipment, another equipment, then another company's equipment.
        for equipment_id in (1, 2, 3):
            with self.subTest(equipment_id=equipment_id):
                response = self.client.post(
                    "/api/v1/sensors",
                    json=self.payload("SEN-USED", equipment_id),
                )
                self.assert_conflict(response, "SEN-USED")
                self.assertEqual(self.snapshot(), before)

    def test_patch_current_code_returns_200_without_duplication(self):
        before = self.snapshot()
        response = self.client.patch("/api/v1/sensors/1", json={"code": "SEN-USED"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["code"], "SEN-USED")
        self.assertEqual(self.snapshot(), before)

    def test_patch_available_code_returns_200_and_persists(self):
        before = self.snapshot()[0]
        response = self.client.patch("/api/v1/sensors/1", json={"code": "SEN-FREE"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual((body["id"], body["code"], body["equipment_id"]),
                         (1, "SEN-FREE", 1))
        persisted = self.snapshot()
        self.assertEqual(len(persisted), 1)
        for key, value in before.items():
            if key not in ("code", "updated_at"):
                self.assertEqual(persisted[0][key], value)
        self.assertEqual(persisted[0]["code"], "SEN-FREE")
        with Session(self.engine) as db:
            repository = SensorRepository(db)
            self.assertIsNone(repository.get_by_code("SEN-USED"))
            self.assertEqual(repository.get_by_code("SEN-FREE").id, 1)
        reread = self.client.get("/api/v1/sensors/1")
        self.assertEqual(reread.status_code, 200, reread.text)
        self.assertEqual(reread.json(), body)

    def test_patch_another_sensors_code_is_rejected_globally(self):
        with Session(self.engine) as db:
            db.add_all([
                Sensor(id=i + 1, **self.payload(f"SEN-OTHER-{i}", equipment_id=i))
                for i in (1, 2, 3)
            ])
            db.commit()
        before = self.snapshot()
        for equipment_id in (1, 2, 3):
            with self.subTest(equipment_id=equipment_id):
                code = f"SEN-OTHER-{equipment_id}"
                response = self.client.patch("/api/v1/sensors/1", json={"code": code})
                self.assert_conflict(response, code)
                self.assertEqual(self.snapshot(), before)

    def test_patch_without_code_keeps_code_and_parent(self):
        response = self.client.patch("/api/v1/sensors/1", json={"description": "Updated"})
        self.assertEqual(response.status_code, 200, response.text)
        persisted = self.snapshot()
        self.assertEqual(len(persisted), 1)
        self.assertEqual((persisted[0]["code"], persisted[0]["equipment_id"],
                          persisted[0]["description"]), ("SEN-USED", 1, "Updated"))

    def test_post_missing_equipment_keeps_existing_data(self):
        before = self.snapshot()
        response = self.client.post("/api/v1/sensors", json=self.payload("SEN-NEW", 999))
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json(), {
            "detail": "Equipment with id '999' does not exist."
        })
        self.assertEqual(self.snapshot(), before)
