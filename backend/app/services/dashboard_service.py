from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.repositories.company_repository import CompanyRepository
from app.repositories.dashboard_repository import DashboardRepository
from app.repositories.equipment_repository import EquipmentRepository
from app.repositories.site_repository import SiteRepository
from app.schemas.dashboard import (
    AssetOverview,
    CategoryCount,
    CompletedMaintenanceSummary,
    CorrectiveMaintenanceSummary,
    CoverageSummary,
    DailyMeasurementCount,
    DashboardPeriod,
    DashboardRead,
    DashboardScope,
    DowntimeSummary,
    EquipmentCriticalitySummary,
    EquipmentStatusSummary,
    LastMeasurement,
    MaintenanceCostSummary,
    MaintenancePrioritySummary,
    MaintenanceSummary,
    MaintenanceTypeSummary,
    MeasurementActivitySummary,
    MeasurementQualitySummary,
    MeasurementSummary,
    OpenMaintenanceSummary,
    OverdueMaintenanceSummary,
    RatioKPI,
    SensorCoverageSummary,
    SensorStatusSummary,
)


class DashboardService:

    EQUIPMENT_STATUSES = {
        "operational",
        "maintenance",
        "out_of_service",
    }

    EQUIPMENT_CRITICALITIES = {
        "low",
        "medium",
        "high",
        "critical",
    }

    SENSOR_STATUSES = {
        "active",
        "inactive",
    }

    MEASUREMENT_QUALITIES = {
        "good",
        "suspect",
        "bad",
        "missing",
        "estimated",
    }

    MAINTENANCE_PRIORITIES = {
        "low",
        "medium",
        "high",
        "critical",
    }

    MAINTENANCE_TYPES = {
        "preventive",
        "corrective",
        "predictive",
    }

    def __init__(self, db: Session):
        self.repository = DashboardRepository(db)

        self.company_repository = CompanyRepository(db)
        self.site_repository = SiteRepository(db)
        self.equipment_repository = EquipmentRepository(db)

        self.db = db

    def get_dashboard(
        self,
        company_id: int,
        start_time: datetime,
        end_time: datetime,
        site_id: int | None = None,
        equipment_id: int | None = None,
    ) -> DashboardRead:

        calculated_at = datetime.now(timezone.utc)

        start_time = self._normalize_datetime(
            start_time,
            "start_time",
        )

        end_time = self._normalize_datetime(
            end_time,
            "end_time",
        )

        self._validate_period(
            start_time=start_time,
            end_time=end_time,
            calculated_at=calculated_at,
        )

        self._validate_scope(
            company_id=company_id,
            site_id=site_id,
            equipment_id=equipment_id,
        )

        assets = self._build_assets(
            company_id,
            site_id,
            equipment_id,
        )

        equipment_status = self._build_equipment_status(
            company_id,
            site_id,
            equipment_id,
        )

        equipment_criticality = self._build_equipment_criticality(
            company_id,
            site_id,
            equipment_id,
        )

        sensor_status = self._build_sensor_status(
            company_id,
            site_id,
            equipment_id,
        )

        sensor_coverage = self._build_sensor_coverage(
            company_id,
            site_id,
            equipment_id,
            assets.equipments,
        )

        measurements = self._build_measurements(
            company_id=company_id,
            site_id=site_id,
            equipment_id=equipment_id,
            start_time=start_time,
            end_time=end_time,
            calculated_at=calculated_at,
            sensor_status=sensor_status,
        )

        maintenance = self._build_maintenance(
            company_id=company_id,
            site_id=site_id,
            equipment_id=equipment_id,
            start_time=start_time,
            end_time=end_time,
            calculated_at=calculated_at,
        )

        return DashboardRead(
            scope=DashboardScope(
                company_id=company_id,
                site_id=site_id,
                equipment_id=equipment_id,
            ),
            period=DashboardPeriod(
                start_time=start_time,
                end_time=end_time,
                calculated_at=calculated_at,
            ),
            assets=assets,
            equipment_status=equipment_status,
            equipment_criticality=equipment_criticality,
            sensor_coverage=sensor_coverage,
            sensor_status=sensor_status,
            measurements=measurements,
            maintenance=maintenance,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_scope(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
    ) -> None:
        company = self.company_repository.get_by_id(company_id)

        if not company:
            raise ValueError("Company not found")

        if site_id is not None:
            self._validate_site_scope(
                company_id=company_id,
                site_id=site_id,
            )

        if equipment_id is not None:
            self._validate_equipment_scope(
                company_id=company_id,
                site_id=site_id,
                equipment_id=equipment_id,
            )


    def _validate_site_scope(
        self,
        company_id: int,
        site_id: int,
    ) -> None:
        site = self.site_repository.get_by_id(site_id)

        if not site:
            raise ValueError("Site not found")

        if site.company_id != company_id:
            raise ValueError(
                "Site does not belong to company"
            )


    def _validate_equipment_scope(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int,
    ) -> None:
        equipment = self.equipment_repository.get_by_id(
            equipment_id
        )

        if not equipment:
            raise ValueError("Equipment not found")

        equipment_site = self.site_repository.get_by_id(
            equipment.site_id
        )

        if not equipment_site:
            raise ValueError(
                "Equipment site not found"
            )

        if equipment_site.company_id != company_id:
            raise ValueError(
                "Equipment does not belong to company"
            )

        if (
            site_id is not None
            and equipment.site_id != site_id
        ):
            raise ValueError(
                "Equipment does not belong to site"
            )


    def _validate_period(
        self,
        start_time: datetime,
        end_time: datetime,
        calculated_at: datetime,
    ) -> None:

        if start_time >= end_time:
            raise ValueError(
                "start_time must be before end_time"
            )

        if end_time > calculated_at:
            raise ValueError(
                "end_time cannot be in the future"
            )

    @staticmethod
    def _normalize_datetime(
        value: datetime,
        field_name: str,
    ) -> datetime:

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                f"{field_name} must include timezone information"
            )

        return value.astimezone(timezone.utc)

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ratio(
        numerator: int,
        denominator: int,
    ) -> RatioKPI:

        percentage = None

        if denominator > 0:
            percentage = round(
                (numerator / denominator) * 100,
                2,
            )

        return RatioKPI(
            numerator=numerator,
            denominator=denominator,
            percentage=percentage,
        )

    @staticmethod
    def _rows_to_counts(
        rows,
    ) -> dict[str, int]:

        result: dict[str, int] = {}

        for row in rows:
            value = row["value"]

            key = (
                str(value)
                if value is not None
                else "null"
            )

            result[key] = int(
                row["count"]
            )

        return result

    @staticmethod
    def _distribution(
        counts: dict[str, int],
    ) -> list[CategoryCount]:

        return [
            CategoryCount(
                value=value,
                count=count,
            )
            for value, count in counts.items()
        ]

    @staticmethod
    def _other_count(
        counts: dict[str, int],
        known_values: set[str],
    ) -> int:

        return sum(
            count
            for value, count in counts.items()
            if value not in known_values
        )

    # ------------------------------------------------------------------
    # Assets
    # ------------------------------------------------------------------

    def _build_assets(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
    ) -> AssetOverview:

        return AssetOverview(
            sites=self.repository.count_sites(
                company_id,
                site_id,
                equipment_id,
            ),
            equipments=self.repository.count_equipments(
                company_id,
                site_id,
                equipment_id,
            ),
            sensors=self.repository.count_sensors(
                company_id,
                site_id,
                equipment_id,
            ),
        )

    # ------------------------------------------------------------------
    # Equipment
    # ------------------------------------------------------------------

    def _build_equipment_status(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
    ) -> EquipmentStatusSummary:

        rows = self.repository.get_equipment_status_counts(
            company_id,
            site_id,
            equipment_id,
        )

        counts = self._rows_to_counts(rows)

        total = sum(counts.values())

        operational = counts.get(
            "operational",
            0,
        )

        return EquipmentStatusSummary(
            total=total,
            operational=operational,
            maintenance=counts.get(
                "maintenance",
                0,
            ),
            out_of_service=counts.get(
                "out_of_service",
                0,
            ),
            other=self._other_count(
                counts,
                self.EQUIPMENT_STATUSES,
            ),
            distribution=self._distribution(
                counts
            ),
            operational_ratio=self._ratio(
                operational,
                total,
            ),
        )

    def _build_equipment_criticality(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
    ) -> EquipmentCriticalitySummary:

        rows = (
            self.repository
            .get_equipment_criticality_counts(
                company_id,
                site_id,
                equipment_id,
            )
        )

        counts = self._rows_to_counts(rows)

        total = sum(counts.values())

        high = counts.get("high", 0)
        critical = counts.get("critical", 0)

        return EquipmentCriticalitySummary(
            total=total,
            low=counts.get("low", 0),
            medium=counts.get("medium", 0),
            high=high,
            critical=critical,
            other=self._other_count(
                counts,
                self.EQUIPMENT_CRITICALITIES,
            ),
            distribution=self._distribution(
                counts
            ),
            high_or_critical=(
                high + critical
            ),
            high_or_critical_unavailable=(
                self.repository
                .count_high_critical_unavailable(
                    company_id,
                    site_id,
                    equipment_id,
                )
            ),
        )

    # ------------------------------------------------------------------
    # Sensors
    # ------------------------------------------------------------------

    def _build_sensor_coverage(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
        equipment_total: int,
    ) -> SensorCoverageSummary:

        covered = (
            self.repository
            .count_equipments_with_active_sensor(
                company_id,
                site_id,
                equipment_id,
            )
        )

        return SensorCoverageSummary(
            equipments_total=equipment_total,
            equipments_with_active_sensor=covered,
            coverage=self._ratio(
                covered,
                equipment_total,
            ),
        )

    def _build_sensor_status(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
    ) -> SensorStatusSummary:

        rows = self.repository.get_sensor_status_counts(
            company_id,
            site_id,
            equipment_id,
        )

        counts = self._rows_to_counts(rows)

        total = sum(counts.values())

        active = counts.get(
            "active",
            0,
        )

        return SensorStatusSummary(
            total=total,
            active=active,
            inactive=counts.get(
                "inactive",
                0,
            ),
            other=self._other_count(
                counts,
                self.SENSOR_STATUSES,
            ),
            distribution=self._distribution(
                counts
            ),
            active_ratio=self._ratio(
                active,
                total,
            ),
        )

    # ------------------------------------------------------------------
    # Measurements
    # ------------------------------------------------------------------

    def _build_measurements(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
        start_time: datetime,
        end_time: datetime,
        calculated_at: datetime,
        sensor_status: SensorStatusSummary,
    ) -> MeasurementSummary:

        measurements_total = (
            self.repository.count_measurements(
                company_id,
                start_time,
                end_time,
                site_id,
                equipment_id,
            )
        )

        quality_rows = (
            self.repository
            .get_measurement_quality_counts(
                company_id,
                start_time,
                end_time,
                site_id,
                equipment_id,
            )
        )

        quality_counts = self._rows_to_counts(
            quality_rows
        )

        good = quality_counts.get(
            "good",
            0,
        )

        quality = MeasurementQualitySummary(
            total=measurements_total,
            good=good,
            suspect=quality_counts.get(
                "suspect",
                0,
            ),
            bad=quality_counts.get(
                "bad",
                0,
            ),
            missing=quality_counts.get(
                "missing",
                0,
            ),
            estimated=quality_counts.get(
                "estimated",
                0,
            ),
            other=self._other_count(
                quality_counts,
                self.MEASUREMENT_QUALITIES,
            ),
            distribution=self._distribution(
                quality_counts
            ),
            good_ratio=self._ratio(
                good,
                measurements_total,
            ),
        )

        active_reporting = (
            self.repository
            .count_active_sensors_with_measurement(
                company_id,
                start_time,
                end_time,
                site_id,
                equipment_id,
            )
        )

        activity = MeasurementActivitySummary(
            measurements_total=measurements_total,
            active_sensors_total=sensor_status.active,
            active_sensors_with_measurement=active_reporting,
            active_sensors_reporting_ratio=self._ratio(
                active_reporting,
                sensor_status.active,
            ),
        )

        daily_rows = (
            self.repository
            .get_daily_measurement_counts(
                company_id,
                start_time,
                end_time,
                site_id,
                equipment_id,
            )
        )

        daily_volume = self._fill_daily_measurements(
            start_time,
            end_time,
            daily_rows,
        )

        last_rows = (
            self.repository.get_last_measurements(
                company_id,
                calculated_at,
                site_id,
                equipment_id,
            )
        )

        last_measurements = (
            self._build_last_measurements(
                last_rows,
                calculated_at,
            )
        )

        return MeasurementSummary(
            activity=activity,
            quality=quality,
            daily_volume=daily_volume,
            last_measurements=last_measurements,
        )

    @staticmethod
    def _fill_daily_measurements(
        start_time: datetime,
        end_time: datetime,
        rows,
    ) -> list[DailyMeasurementCount]:

        observed: dict[date, int] = {
            row["date"]: int(row["count"])
            for row in rows
        }

        current_date = start_time.date()

        last_date = (
            end_time - timedelta(
                microseconds=1
            )
        ).date()

        result: list[
            DailyMeasurementCount
        ] = []

        while current_date <= last_date:
            result.append(
                DailyMeasurementCount(
                    date=current_date.isoformat(),
                    count=observed.get(
                        current_date,
                        0,
                    ),
                )
            )

            current_date += timedelta(days=1)

        return result

    @staticmethod
    def _build_last_measurements(
        rows,
        calculated_at: datetime,
    ) -> list[LastMeasurement]:

        result: list[LastMeasurement] = []

        for row in rows:
            timestamp = row["timestamp"]

            age_seconds = None

            if timestamp is not None:
                age_seconds = max(
                    (
                        calculated_at
                        - timestamp
                    ).total_seconds(),
                    0.0,
                )

            result.append(
                LastMeasurement(
                    sensor_id=row["sensor_id"],
                    sensor_name=row["sensor_name"],
                    sensor_code=row["sensor_code"],
                    equipment_id=row["equipment_id"],
                    timestamp=timestamp,
                    value=row["value"],
                    unit=row["unit"],
                    quality=row["quality"],
                    age_seconds=age_seconds,
                )
            )

        return result

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def _build_maintenance(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
        start_time: datetime,
        end_time: datetime,
        calculated_at: datetime,
    ) -> MaintenanceSummary:

        open_summary = self._build_open_maintenance(
            company_id,
            site_id,
            equipment_id,
        )

        overdue = OverdueMaintenanceSummary(
            overdue=(
                self.repository
                .count_overdue_maintenance(
                    company_id,
                    calculated_at,
                    site_id,
                    equipment_id,
                )
            ),
            planned_without_planned_at=(
                self.repository
                .count_planned_maintenance_without_planned_at(
                    company_id,
                    site_id,
                    equipment_id,
                )
            ),
        )

        completed = (
            self._build_completed_maintenance(
                company_id,
                start_time,
                end_time,
                site_id,
                equipment_id,
            )
        )

        corrective_completed = (
            completed.types.corrective
        )

        corrective = CorrectiveMaintenanceSummary(
            corrective_completed=corrective_completed,
            completed_total=completed.total,
            ratio=self._ratio(
                corrective_completed,
                completed.total,
            ),
        )

        downtime = self._build_downtime(
            company_id,
            start_time,
            end_time,
            site_id,
            equipment_id,
        )

        cost = self._build_cost(
            company_id,
            start_time,
            end_time,
            site_id,
            equipment_id,
        )

        return MaintenanceSummary(
            open=open_summary,
            overdue=overdue,
            completed=completed,
            corrective=corrective,
            downtime=downtime,
            cost=cost,
        )

    def _build_open_maintenance(
        self,
        company_id: int,
        site_id: int | None,
        equipment_id: int | None,
    ) -> OpenMaintenanceSummary:

        status_rows = (
            self.repository
            .get_open_maintenance_status_counts(
                company_id,
                site_id,
                equipment_id,
            )
        )

        status_counts = self._rows_to_counts(
            status_rows
        )

        total = sum(
            status_counts.values()
        )

        priority_rows = (
            self.repository
            .get_open_maintenance_priority_counts(
                company_id,
                site_id,
                equipment_id,
            )
        )

        priority_counts = self._rows_to_counts(
            priority_rows
        )

        return OpenMaintenanceSummary(
            total=total,
            planned=status_counts.get(
                "planned",
                0,
            ),
            in_progress=status_counts.get(
                "in_progress",
                0,
            ),
            other=self._other_count(
                status_counts,
                {
                    "planned",
                    "in_progress",
                },
            ),
            priorities=MaintenancePrioritySummary(
                total=sum(
                    priority_counts.values()
                ),
                low=priority_counts.get(
                    "low",
                    0,
                ),
                medium=priority_counts.get(
                    "medium",
                    0,
                ),
                high=priority_counts.get(
                    "high",
                    0,
                ),
                critical=priority_counts.get(
                    "critical",
                    0,
                ),
                other=self._other_count(
                    priority_counts,
                    self.MAINTENANCE_PRIORITIES,
                ),
                distribution=self._distribution(
                    priority_counts
                ),
            ),
        )

    def _build_completed_maintenance(
        self,
        company_id: int,
        start_time: datetime,
        end_time: datetime,
        site_id: int | None,
        equipment_id: int | None,
    ) -> CompletedMaintenanceSummary:

        rows = (
            self.repository
            .get_completed_maintenance_type_counts(
                company_id,
                start_time,
                end_time,
                site_id,
                equipment_id,
            )
        )

        counts = self._rows_to_counts(rows)

        total = sum(counts.values())

        type_summary = MaintenanceTypeSummary(
            total=total,
            preventive=counts.get(
                "preventive",
                0,
            ),
            corrective=counts.get(
                "corrective",
                0,
            ),
            predictive=counts.get(
                "predictive",
                0,
            ),
            other=self._other_count(
                counts,
                self.MAINTENANCE_TYPES,
            ),
            distribution=self._distribution(
                counts
            ),
        )

        return CompletedMaintenanceSummary(
            total=total,
            completed_without_completed_at=(
                self.repository
                .count_completed_maintenance_without_completed_at(
                    company_id,
                    site_id,
                    equipment_id,
                )
            ),
            types=type_summary,
        )

    def _build_downtime(
        self,
        company_id: int,
        start_time: datetime,
        end_time: datetime,
        site_id: int | None,
        equipment_id: int | None,
    ) -> DowntimeSummary:

        row = (
            self.repository
            .get_completed_downtime_aggregate(
                company_id,
                start_time,
                end_time,
                site_id,
                equipment_id,
            )
        )

        eligible = int(
            row["eligible_records"]
        )

        valid = int(
            row["valid_values"]
        )

        raw_sum = row["valid_sum"]

        total_minutes: float | None

        if eligible == 0:
            total_minutes = 0.0

        elif valid == 0:
            total_minutes = None

        else:
            total_minutes = float(
                raw_sum
            )

        total_hours = (
            round(
                total_minutes / 60,
                2,
            )
            if total_minutes is not None
            else None
        )

        return DowntimeSummary(
            total_minutes=total_minutes,
            total_hours=total_hours,
            coverage=CoverageSummary(
                valid_values=valid,
                eligible_records=eligible,
                ratio=self._ratio(
                    valid,
                    eligible,
                ),
            ),
        )

    def _build_cost(
        self,
        company_id: int,
        start_time: datetime,
        end_time: datetime,
        site_id: int | None,
        equipment_id: int | None,
    ) -> MaintenanceCostSummary:

        row = (
            self.repository
            .get_completed_cost_aggregate(
                company_id,
                start_time,
                end_time,
                site_id,
                equipment_id,
            )
        )

        eligible = int(
            row["eligible_records"]
        )

        valid = int(
            row["valid_values"]
        )

        raw_sum = row["valid_sum"]

        total_cost: float | None

        if eligible == 0:
            total_cost = 0.0

        elif valid == 0:
            total_cost = None

        else:
            total_cost = float(
                raw_sum
            )

        return MaintenanceCostSummary(
            total_cost=total_cost,
            currency=None,
            coverage=CoverageSummary(
                valid_values=valid,
                eligible_records=eligible,
                ratio=self._ratio(
                    valid,
                    eligible,
                ),
            ),
        )