"""Offline byte validation only. No shell, Docker, filesystem or signal executor."""

from dataclasses import dataclass
from functools import wraps
from hashlib import sha256
import json


BASE_IMAGE = "docker.io/library/postgres@sha256:7958605b474b3d264a969cb3a123d6aa00ad1e1fe9da8a69984dabb704d93317"
GUARDIAN_PATH = "/usr/local/libexec/oidc-test-guardian"
BOOTSTRAP_SHA256 = "d319573e82d26516aca327a1294dd44d6abad2e5883995a1b557969a9aa24665"
ARTIFACTS = (
    ("guardian.sh", "bbca41577ef41c12d6cb3f31615c2c0c4a18fda028c7d5c0c7d44d05fbc992c2"),
    ("Dockerfile.in", "aae8dad868a68f48085a1c6a59abf26a66ad41eb0643f0f18c0013c0033b6e95"),
    (".dockerignore", "181be2c9e6db070e048be5103914e0953e35f6042111f7b34b81549223dfe1b8"),
)


class GuardianPreparationRejected(ValueError):
    def __init__(self):
        super().__init__("OIDC idle guardian preparation rejected")


def _reject():
    try:
        raise GuardianPreparationRejected() from None
    except GuardianPreparationRejected as error:
        error.__context__ = error.__cause__ = None
        error.__suppress_context__ = True
        raise


def _guarded(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            pass
        _reject()
    return checked


@dataclass(frozen=True, slots=True, repr=False)
class PreparationValidation:
    base_image: str
    guardian_sha256: str
    bootstrap_sha256: str

    def __repr__(self):
        return "<PreparationValidation: offline-only>"

    def __bool__(self):
        _reject()

    @property
    def execution_authorized(self):
        return False

    @property
    def build_authorized(self):
        return False

    @property
    def authenticated(self):
        return False


def _require(condition):
    if not condition:
        raise GuardianPreparationRejected()


def _bytes(value):
    _require(type(value) is bytes and 0 < len(value) <= 65536)
    _require(value.endswith(b"\n") and all(byte == 10 or 32 <= byte <= 126 for byte in value))
    return value


def _unique(pairs):
    result = {}
    for name, value in pairs:
        _require(name not in result)
        result[name] = value
    return result


def _same(actual, expected):
    _require(type(actual) is type(expected))
    if type(expected) is dict:
        _require(all(type(key) is str for key in actual))
        _require(set(actual) == set(expected))
        for key in expected:
            _same(actual[key], expected[key])
    elif type(expected) is list:
        _require(len(actual) == len(expected))
        for item, wanted in zip(actual, expected):
            _same(item, wanted)
    else:
        _require(actual == expected)


def _manifest_contract():
    return {
        "schema_version": "3F-idle-only-v1",
        "base_image": BASE_IMAGE,
        "platform": "linux/amd64",
        "guardian_path": GUARDIAN_PATH,
        "owner_uid": 0,
        "owner_gid": 0,
        "mode": "0555",
        "entrypoint": [GUARDIAN_PATH],
        "command": [],
        "initial_user": "0:0",
        "stop_signal": "SIGTERM",
        "initial_behavior": "idle_only",
        "activation_interface": "absent",
        "derived_digest": "unavailable_until_authorized_build",
        "runtime_requirements": {
            "read_only_rootfs": True,
            "privileged": False,
            "cap_drop": ["ALL"],
            "cap_add": [],
            "guardian_writable_directories": [],
        },
        "bootstrap_reference_sha256": BOOTSTRAP_SHA256,
        "artifacts": dict(ARTIFACTS),
    }


@_guarded
def validate_preparation(*, guardian_bytes, recipe_bytes, ignore_bytes, manifest_bytes, bootstrap_bytes):
    """Validate supplied original bytes. The reviewed module is the hash anchor.

    Editing a supplied manifest cannot approve unknown artifact content.
    This is neither a signature nor an authority to build or start anything.
    """
    for data, (_, expected_hash) in zip((guardian_bytes, recipe_bytes, ignore_bytes), ARTIFACTS):
        _require(sha256(_bytes(data)).hexdigest() == expected_hash)
    manifest = json.loads(_bytes(manifest_bytes).decode("ascii"), object_pairs_hook=_unique)
    _same(manifest, _manifest_contract())
    _require(sha256(_bytes(bootstrap_bytes)).hexdigest() == BOOTSTRAP_SHA256)
    return PreparationValidation(BASE_IMAGE, ARTIFACTS[0][1], BOOTSTRAP_SHA256)
