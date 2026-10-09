import unittest
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import create_autospec

from sqlalchemy.orm import Session

from predictions.support import PredictionCase, START, as_utc, create_data
from app.models.prediction_record import PredictionRecord
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.prediction_repository import PredictionRepository
from app.services.prediction_service import PredictionService


class PredictionServiceUnitTests(unittest.TestCase):
    def setUp(self):
        self.db = create_autospec(Session, instance=True)
        self.service = PredictionService(self.db)
        self.equipment = create_autospec(EquipmentRepository, instance=True)
        self.repository = create_autospec(PredictionRepository, instance=True)
        self.service.equipment_repository = self.equipment
        self.service.repository = self.repository
        self.equipment.get_by_id.return_value = SimpleNamespace(id=1)

    def test_create_mapping_commit_and_refresh(self):
        data = create_data(sensor_id=1, measurement_id=2, level="high", is_alert=True,
            model_name="test", model_version="v1", horizon_hours=12, details={"reason": "test"})
        result = self.service.create(data)
        self.assertIsInstance(result, PredictionRecord)
        self.equipment.get_by_id.assert_called_once_with(1)
        self.repository.create.assert_called_once_with(result)
        self.db.commit.assert_called_once_with()
        self.db.refresh.assert_called_once_with(result)
        for field, expected in data.model_dump().items():
            self.assertEqual(getattr(result, field), expected.value if field == "prediction_type" else expected)

    def test_create_missing_equipment_does_not_write(self):
        self.equipment.get_by_id.return_value = None
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            self.service.create(create_data(equipment_id=999))
        self.repository.create.assert_not_called()
        self.db.commit.assert_not_called()

    def test_pagination_passes_all_filters_to_items_and_count(self):
        filters = dict(equipment_id=1, prediction_type="anomaly", level="high", is_alert=False,
                       start_time=START, end_time=START + timedelta(hours=2))
        item = PredictionRecord(id=1, **create_data().model_dump())
        self.repository.get_paginated.return_value = [item]
        self.repository.count_all.return_value = 7
        result = self.service.get_paginated(page=2, page_size=3, **filters)
        self.equipment.get_by_id.assert_called_once_with(1)
        self.repository.get_paginated.assert_called_once_with(offset=3, limit=3, **filters)
        self.repository.count_all.assert_called_once_with(**filters)
        self.assertEqual({key: getattr(result, key) for key in ("total", "page", "page_size", "pages")},
                         dict(total=7, page=2, page_size=3, pages=3))
        self.assertIs(result.items[0], item)

    def test_pagination_missing_equipment_does_not_query_predictions(self):
        self.equipment.get_by_id.return_value = None
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            self.service.get_paginated(equipment_id=999, page=1, page_size=20)
        self.repository.get_paginated.assert_not_called()
        self.repository.count_all.assert_not_called()


class PredictionServiceIntegrationTests(PredictionCase):
    def test_create_with_real_repository(self):
        result = PredictionService(self.db).create(create_data(details={"test": True}))
        self.assertIsNotNone(result.id)
        record_id = result.id
        self.db.expunge_all()
        loaded = self.predictions.get_by_id(record_id)
        self.assertEqual(loaded.details, {"test": True})
        self.assertEqual(as_utc(loaded.predicted_at), START)

    def test_create_missing_equipment(self):
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            PredictionService(self.db).create(create_data(equipment_id=999))
        self.assertEqual(self.predictions.count_all(equipment_id=999), 0)

    def test_paginated_real_repository_and_filters(self):
        self.seed_predictions()
        service = PredictionService(self.db)
        result = service.get_paginated(equipment_id=1, page=2, page_size=2)
        self.assertEqual(self.ids(result.items), self.ids([self.tie_first, self.early]))
        self.assertEqual(result.total, 4)
        self.assertEqual(result.pages, 2)
        for filters, expected in self.filter_cases():
            with self.subTest(filters=filters):
                page = service.get_paginated(equipment_id=1, page=1, page_size=20, **filters)
                self.assertEqual(self.ids(page.items), self.ids(expected))
                self.assertEqual(page.total, len(expected))

    def test_paginated_missing_equipment(self):
        with self.assertRaisesRegex(LookupError, "Equipment not found"):
            PredictionService(self.db).get_paginated(equipment_id=999, page=1, page_size=20)
