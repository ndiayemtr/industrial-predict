from datetime import datetime

from sqlalchemy import ColumnElement, Date, RowMapping, Select, case, distinct, func, select
from sqlalchemy.orm import Session

from app.models.equipment import Equipment
from app.models.maintenance_record import MaintenanceRecord
from app.models.measurement import Measurement
from app.models.sensor import Sensor
from app.models.site import Site


class DashboardRepository:
    """Read-only SQL aggregates; scope/time validation belongs to the service.

    Category rows contain ``value`` and ``count`` without category normalization.
    Dates and cutoffs are supplied by the caller; this class never reads the clock.
    """

    def __init__(self, db: Session):
        self.db = db

    def _equipment_ids(
        self, company_id: int, site_id: int | None, equipment_id: int | None,
    ) -> Select[tuple[int]]:
        statement = (
            select(Equipment.id)
            .join(Site, Equipment.site_id == Site.id)
            .where(Site.company_id == company_id)
        )
        if site_id is not None:
            statement = statement.where(Site.id == site_id)
        if equipment_id is not None:
            statement = statement.where(Equipment.id == equipment_id)
        return statement

    def _sensor_ids(
        self, company_id: int, site_id: int | None, equipment_id: int | None,
    ) -> Select[tuple[int]]:
        return select(Sensor.id).where(
            Sensor.equipment_id.in_(
                self._equipment_ids(company_id, site_id, equipment_id)
            )
        )

    def _measurement_filters(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None, equipment_id: int | None,
    ) -> tuple[ColumnElement[bool], ...]:
        return (
            Measurement.sensor_id.in_(
                self._sensor_ids(company_id, site_id, equipment_id)
            ),
            Measurement.timestamp >= start_time,
            Measurement.timestamp < end_time,
        )

    def _maintenance_scope(
        self, company_id: int, site_id: int | None, equipment_id: int | None,
    ) -> ColumnElement[bool]:
        return MaintenanceRecord.equipment_id.in_(
            self._equipment_ids(company_id, site_id, equipment_id)
        )

    def _completed_filters(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None, equipment_id: int | None,
    ) -> tuple[ColumnElement[bool], ...]:
        return (
            self._maintenance_scope(company_id, site_id, equipment_id),
            MaintenanceRecord.status == "completed",
            MaintenanceRecord.completed_at >= start_time,
            MaintenanceRecord.completed_at < end_time,
        )

    def count_sites(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int:
        # Do not join children: empty sites must still count.
        statement = select(func.count(Site.id)).where(Site.company_id == company_id)
        if site_id is not None:
            statement = statement.where(Site.id == site_id)
        if equipment_id is not None:
            statement = statement.where(
                select(Equipment.id).where(
                    Equipment.site_id == Site.id,
                    Equipment.id == equipment_id,
                ).exists()
            )
        return self.db.execute(statement).scalar_one()

    def count_equipments(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(Equipment.id)).where(
            Equipment.id.in_(self._equipment_ids(company_id, site_id, equipment_id))
        )
        return self.db.execute(statement).scalar_one()

    def count_sensors(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(Sensor.id)).where(
            Sensor.id.in_(self._sensor_ids(company_id, site_id, equipment_id))
        )
        return self.db.execute(statement).scalar_one()

    def get_equipment_status_counts(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> list[RowMapping]:
        statement = (
            select(Equipment.status.label("value"), func.count().label("count"))
            .where(Equipment.id.in_(
                self._equipment_ids(company_id, site_id, equipment_id)
            ))
            .group_by(Equipment.status)
            .order_by(Equipment.status)
        )
        return list(self.db.execute(statement).mappings().all())

    def get_equipment_criticality_counts(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> list[RowMapping]:
        statement = (
            select(Equipment.criticality.label("value"), func.count().label("count"))
            .where(Equipment.id.in_(
                self._equipment_ids(company_id, site_id, equipment_id)
            ))
            .group_by(Equipment.criticality)
            .order_by(Equipment.criticality)
        )
        return list(self.db.execute(statement).mappings().all())

    def count_high_critical_unavailable(
    self,
        company_id: int,
        site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(Equipment.id)).where(
            Equipment.id.in_(
                self._equipment_ids(
                    company_id,
                    site_id,
                    equipment_id,
                )
            ),
            Equipment.criticality.in_(("high", "critical")),
            Equipment.status.in_(("maintenance", "out_of_service")),
        )
        return self.db.execute(statement).scalar_one()

    def count_equipments_with_active_sensor(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(distinct(Sensor.equipment_id))).where(
            Sensor.equipment_id.in_(
                self._equipment_ids(company_id, site_id, equipment_id)
            ),
            Sensor.status == "active",
        )
        return self.db.execute(statement).scalar_one()

    def get_sensor_status_counts(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> list[RowMapping]:
        statement = (
            select(Sensor.status.label("value"), func.count().label("count"))
            .where(Sensor.id.in_(self._sensor_ids(company_id, site_id, equipment_id)))
            .group_by(Sensor.status)
            .order_by(Sensor.status)
        )
        return list(self.db.execute(statement).mappings().all())

    def count_measurements(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(Measurement.id)).where(
            *self._measurement_filters(
                company_id, start_time, end_time, site_id, equipment_id
            )
        )
        return self.db.execute(statement).scalar_one()

    def get_measurement_quality_counts(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> list[RowMapping]:
        statement = (
            select(Measurement.quality.label("value"), func.count().label("count"))
            .where(*self._measurement_filters(
                company_id, start_time, end_time, site_id, equipment_id
            ))
            .group_by(Measurement.quality)
            .order_by(Measurement.quality)
        )
        return list(self.db.execute(statement).mappings().all())

    def count_active_sensors_with_measurement(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(Sensor.id)).where(
            Sensor.id.in_(self._sensor_ids(company_id, site_id, equipment_id)),
            Sensor.status == "active",
            select(Measurement.id).where(
                Measurement.sensor_id == Sensor.id,
                Measurement.timestamp >= start_time,
                Measurement.timestamp < end_time,
            ).exists(),
        )
        return self.db.execute(statement).scalar_one()

    def get_daily_measurement_counts(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> list[RowMapping]:
        """Return observed UTC dates (date, count); zero filling is left to service."""
        # PostgreSQL timezone() makes buckets independent of the session timezone.
        day = func.timezone("UTC", Measurement.timestamp).cast(Date)
        statement = (
            select(day.label("date"), func.count().label("count"))
            .where(*self._measurement_filters(
                company_id, start_time, end_time, site_id, equipment_id
            ))
            .group_by(day)
            .order_by(day)
        )
        return list(self.db.execute(statement).mappings().all())

    def get_last_measurements(
        self, company_id: int, calculated_at: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> list[RowMapping]:
        """One row per sensor, including sensors with no reading by the cutoff.

        Return sensor_id/name/code, equipment_id, unit, measurement_id, timestamp,
        value and quality. No period filter or age calculation is applied.
        """
        sensor_ids = self._sensor_ids(company_id, site_id, equipment_id)
        ranked = (
            select(
                Measurement.id.label("measurement_id"),
                Measurement.sensor_id,
                Measurement.timestamp,
                Measurement.value,
                Measurement.quality,
                func.row_number().over(
                    partition_by=Measurement.sensor_id,
                    order_by=(Measurement.timestamp.desc(), Measurement.id.desc()),
                ).label("position"),
            )
            .where(
                Measurement.sensor_id.in_(sensor_ids),
                Measurement.timestamp <= calculated_at,
            )
            .subquery()
        )
        statement = (
            select(
                Sensor.id.label("sensor_id"),
                Sensor.name.label("sensor_name"),
                Sensor.code.label("sensor_code"),
                Sensor.equipment_id,
                Sensor.unit,
                ranked.c.measurement_id,
                ranked.c.timestamp,
                ranked.c.value,
                ranked.c.quality,
            )
            .outerjoin(ranked, (ranked.c.sensor_id == Sensor.id) & (ranked.c.position == 1))
            .where(Sensor.id.in_(sensor_ids))
            .order_by(Sensor.id)
        )
        return list(self.db.execute(statement).mappings().all())

    def get_open_maintenance_status_counts(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> list[RowMapping]:
        """The sum of returned counts is the total number of open interventions."""
        statement = (
            select(MaintenanceRecord.status.label("value"), func.count().label("count"))
            .where(
                self._maintenance_scope(company_id, site_id, equipment_id),
                MaintenanceRecord.status.in_(("planned", "in_progress")),
            )
            .group_by(MaintenanceRecord.status)
            .order_by(MaintenanceRecord.status)
        )
        return list(self.db.execute(statement).mappings().all())

    def get_open_maintenance_priority_counts(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> list[RowMapping]:
        statement = (
            select(MaintenanceRecord.priority.label("value"), func.count().label("count"))
            .where(
                self._maintenance_scope(company_id, site_id, equipment_id),
                MaintenanceRecord.status.in_(("planned", "in_progress")),
            )
            .group_by(MaintenanceRecord.priority)
            .order_by(MaintenanceRecord.priority)
        )
        return list(self.db.execute(statement).mappings().all())

    def count_overdue_maintenance(
        self, company_id: int, calculated_at: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(MaintenanceRecord.id)).where(
            self._maintenance_scope(company_id, site_id, equipment_id),
            MaintenanceRecord.status == "planned",
            MaintenanceRecord.planned_at < calculated_at,
            MaintenanceRecord.started_at.is_(None),
        )
        return self.db.execute(statement).scalar_one()

    def count_planned_maintenance_without_planned_at(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(MaintenanceRecord.id)).where(
            self._maintenance_scope(company_id, site_id, equipment_id),
            MaintenanceRecord.status == "planned",
            MaintenanceRecord.planned_at.is_(None),
        )
        return self.db.execute(statement).scalar_one()

    def get_completed_maintenance_type_counts(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> list[RowMapping]:
        """The sum of returned counts is the completed total on the period."""
        statement = (
            select(
                MaintenanceRecord.maintenance_type.label("value"),
                func.count().label("count"),
            )
            .where(*self._completed_filters(
                company_id, start_time, end_time, site_id, equipment_id
            ))
            .group_by(MaintenanceRecord.maintenance_type)
            .order_by(MaintenanceRecord.maintenance_type)
        )
        return list(self.db.execute(statement).mappings().all())

    def count_completed_maintenance_without_completed_at(
        self, company_id: int, site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> int:
        statement = select(func.count(MaintenanceRecord.id)).where(
            self._maintenance_scope(company_id, site_id, equipment_id),
            MaintenanceRecord.status == "completed",
            MaintenanceRecord.completed_at.is_(None),
        )
        return self.db.execute(statement).scalar_one()

    def get_completed_downtime_aggregate(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> RowMapping:
        """Return eligible_records, valid_values, valid_sum (minutes).

        SUM stays NULL when no valid value exists, including an empty scope.
        The service can distinguish empty scope from missing values via counts.
        """
        valid_value = case((
            MaintenanceRecord.downtime_minutes.is_not(None)
            & (MaintenanceRecord.downtime_minutes >= 0),
            MaintenanceRecord.downtime_minutes,
        ))
        statement = select(
            func.count(MaintenanceRecord.id).label("eligible_records"),
            func.count(valid_value).label("valid_values"),
            func.sum(valid_value).label("valid_sum"),
        ).where(*self._completed_filters(
            company_id, start_time, end_time, site_id, equipment_id
        ))
        return self.db.execute(statement).mappings().one()

    def get_completed_cost_aggregate(
        self, company_id: int, start_time: datetime, end_time: datetime,
        site_id: int | None = None, equipment_id: int | None = None,
    ) -> RowMapping:
        """Return eligible_records, valid_values, valid_sum without currency/rounding.

        As with downtime, no valid values means a NULL sum. PostgreSQL orders
        NaN above infinity; the upper bound excludes both non-finite values.
        """
        valid_value = case((
            MaintenanceRecord.cost.is_not(None)
            & (MaintenanceRecord.cost >= 0)
            & (MaintenanceRecord.cost < float("inf")),
            MaintenanceRecord.cost,
        ))
        statement = select(
            func.count(MaintenanceRecord.id).label("eligible_records"),
            func.count(valid_value).label("valid_values"),
            func.sum(valid_value).label("valid_sum"),
        ).where(*self._completed_filters(
            company_id, start_time, end_time, site_id, equipment_id
        ))
        return self.db.execute(statement).mappings().one()
