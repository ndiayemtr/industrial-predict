"""Local-only destination, SQL snapshot and immutable calculation contracts."""

from dataclasses import dataclass
from enum import StrEnum
from ipaddress import ip_address
from typing import Mapping
from uuid import UUID

from app.anomaly_detection.p101_contracts import Computed


DATABASE = "industrial_predict_p101_local_demo"
PURPOSE = "local-p101-functional-demo"
TARGETS = ("DEMO-M-011", "DEMO-M-012")
CUTOFFS = ("2026-01-11T08:01:00.000000Z", "2026-01-12T08:01:00.000000Z")


class ErrorCode(StrEnum):
    DESTINATION = "DESTINATION_REJECTED"
    SNAPSHOT = "SQL_SNAPSHOT_REJECTED"
    FIXTURE = "FIXTURE_MISMATCH"
    CONTEXT = "CALCULATION_CONTEXT_REJECTED"
    CALCULATION = "COMPUTED_PAIR_REQUIRED"


class LocalDemoError(ValueError):
    """Only a stable code, never SQL parameters, DSNs or raw driver exceptions."""
    def __init__(self, code: ErrorCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True)
class LocalDestination:
    host: str
    port: int
    database: str
    role: str
    server_address: str
    server_port: int
    instance_uuid: str
    schema_revision: str

    def validate(self):
        try:
            valid = (self.host == "127.0.0.1" and type(self.port) is int and self.port == 55432
                and self.database == DATABASE and self.role in ("p101_local_writer", "p101_local_reader")
                and type(self.server_port) is int and self.server_port == 5432
                and str(ip_address(self.server_address)) == self.server_address
                and not ip_address(self.server_address).is_unspecified
                and str(UUID(self.instance_uuid)) == self.instance_uuid and UUID(self.instance_uuid).int != 0
                and type(self.schema_revision) is str and self.schema_revision.startswith("p101_local_")
                and 12 <= len(self.schema_revision) <= 32
                and all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in self.schema_revision))
            if not valid:
                raise LocalDemoError(ErrorCode.DESTINATION)
        except (ValueError, TypeError, AttributeError):
            raise LocalDemoError(ErrorCode.DESTINATION) from None


@dataclass(frozen=True)
class SqlRows:
    """Raw driver mappings; validation always copies before constructing the manifest."""
    companies: tuple[Mapping[str, object], ...]
    sites: tuple[Mapping[str, object], ...]
    equipments: tuple[Mapping[str, object], ...]
    sensors: tuple[Mapping[str, object], ...]
    measurements: tuple[Mapping[str, object], ...]


@dataclass(frozen=True)
class SqlIdentityMap:
    company_id: int
    site_id: int
    equipment_id: int
    sensor_id: int
    measurements: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class AdaptedMeasurements:
    manifest_json: str
    identities: SqlIdentityMap


@dataclass(frozen=True)
class CalculationContext:
    run_id: str
    prepared_at: str
    code_revision: str
    cutoffs: tuple[str, str]


@dataclass(frozen=True)
class ComputedPair:
    results: tuple[Computed, Computed]
    identities: SqlIdentityMap
