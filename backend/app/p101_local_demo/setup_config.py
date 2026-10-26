"""Explicit private setup inputs; no environment/secret discovery or engine import."""

from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network
import json
from pathlib import Path

from app.anomaly_detection.p101_canonical import utc_instant
from app.p101_local_demo.contracts import DATABASE, LocalDestination


REVISION = "p101_local_0001"
CLUSTER = "industrial-predict-p101-local-demo"
ROLES = ("p101_local_admin", "p101_local_owner", "p101_local_writer", "p101_local_reader")
ROOT = Path(__file__).resolve().parents[3]
CORE_FILES = (
    "0468ed5be8f1_create_companies_table.py", "50e5051527dc_create_sites_table.py",
    "656260b06cdf_create_equipments_table.py", "572080d9e581_create_sensors_table.py",
    "570ce155aaf8_create_measurements_table.py", "783e16aa6ce3_create_maintenance_records_table.py",
    "675ebfea0bb5_add_equipment_criticality.py", "d6ec01cf13b6_add_prediction_records.py",
    "09ac8101e9fe_add_maintenance_recommendations.py",
)


class SetupError(ValueError):
    """Sanitized setup error, never carries driver SQL or credentials."""


@dataclass(frozen=True)
class SetupSettings:
    private_root: str
    host: str
    port: int
    database: str
    server_address: str
    server_port: int
    network_subnet: str
    instance_uuid: str
    bootstrap_at: str
    secret_files: tuple[tuple[str, str], ...]

    def validate(self):
        try:
            self.destination("p101_local_reader").validate()
            network = IPv4Network(self.network_subnet, strict=True)
            address = IPv4Address(self.server_address)
            excluded = (IPv4Network("172.17.0.0/16"), IPv4Network("172.18.0.0/16"), IPv4Network("172.19.0.0/16"))
            root = Path(self.private_root)
            if (not network.is_private or not 24 <= network.prefixlen <= 28
                    or address not in network or address in (network.network_address, network.broadcast_address, network.network_address + 1)
                    or any(network.overlaps(n) for n in excluded)
                    or not root.is_absolute() or root.resolve() != root or root == ROOT or ROOT in root.parents
                    or any(c in self.private_root for c in "\r\n$\"'")
                    or utc_instant(self.bootstrap_at) != self.bootstrap_at
                    or self.bootstrap_at < "2026-01-12T08:01:00.000000Z"
                    or self.secret_files != tuple(zip(ROLES, ("admin.password", "owner.password", "writer.password", "reader.password")))):
                raise SetupError("Explicit independent local setup required")
        except (ValueError, TypeError, AttributeError, OSError):
            raise SetupError("Invalid local setup configuration") from None

    def destination(self, role):
        return LocalDestination(self.host, self.port, self.database, role, self.server_address,
                                self.server_port, self.instance_uuid, REVISION)

    @property
    def gateway(self):
        return str(IPv4Network(self.network_subnet).network_address + 1)

    def secret_path(self, role):
        if role not in ROLES:
            raise SetupError("Unknown local role")
        return Path(self.private_root) / dict(self.secret_files)[role]


def parse_settings(data):
    fields = {"format", "private_root", "host", "port", "database", "server_address", "server_port",
              "network_subnet", "instance_uuid", "bootstrap_at", "secret_files"}
    try:
        if type(data) is not dict or set(data) != fields or data["format"] != "p101-local-settings-v1":
            raise SetupError("Explicit local settings format required")
        values = dict(data)
        values.pop("format")
        files = values["secret_files"]
        if type(files) is not dict or set(files) != set(ROLES):
            raise SetupError("Four independent secret references required")
        values["secret_files"] = tuple((r, files[r]) for r in ROLES)
        settings = SetupSettings(**values)
        settings.validate()
        return settings
    except (ValueError, TypeError, KeyError, AttributeError):
        raise SetupError("Invalid explicit local settings") from None


def load_settings(path):
    """One explicit JSON file, physically outside the checkout. No .env fallback."""
    try:
        source = Path(path)
        if (not source.is_absolute() or source.resolve() != source or not source.is_file()
                or ROOT in source.parents or source.suffix != ".json" or source.stat().st_size > 16384):
            raise SetupError("Private settings file rejected")
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result: raise SetupError("Duplicate setting")
                result[key] = value
            return result
        settings = parse_settings(json.loads(source.read_text(encoding="utf-8"), object_pairs_hook=pairs))
        if source.parent != Path(settings.private_root):
            raise SetupError("Settings must be inside the declared private root")
        return settings
    except (ValueError, TypeError, OSError):
        raise SetupError("Private settings unavailable or invalid") from None


def read_secret(settings, role):
    settings.validate()
    try:
        path = settings.secret_path(role)
        if path.resolve() != path or not path.is_file() or path.stat().st_size > 256:
            raise SetupError("Private role secret unavailable")
        value = path.read_text(encoding="utf-8").removesuffix("\n").removesuffix("\r")
        if not 20 <= len(value) <= 200 or any(c in value for c in "\r\n\x00") or not value.strip():
            raise SetupError("Private role secret invalid")
        return value
    except (ValueError, OSError):
        raise SetupError("Private role secret unavailable") from None


def compose_files(settings):
    """Pure contents for future private files. Contains paths, never passwords."""
    settings.validate()
    hba = ("local all p101_local_admin scram-sha-256\nlocal all all reject\n"
        f"host {DATABASE} {','.join(ROLES)} {settings.network_subnet} scram-sha-256\n"
        "host all all 0.0.0.0/0 reject\nhost all all ::/0 reject\n")
    values = dict(P101_LOCAL_HBA_FILE=str(Path(settings.private_root) / "pg_hba.conf"),
        P101_LOCAL_ADDRESS=settings.server_address, P101_LOCAL_SUBNET=settings.network_subnet,
        P101_LOCAL_GATEWAY=settings.gateway, P101_LOCAL_ADMIN_PASSWORD_FILE=str(settings.secret_path(ROLES[0])))
    # JSON quoting is for dotenv data only, never interpolation into shell code.
    env = "".join(k + "=" + json.dumps(v.replace("\\", "/")) + "\n" for k, v in values.items())
    return {"pg_hba.conf": hba, "compose.vars": env}
