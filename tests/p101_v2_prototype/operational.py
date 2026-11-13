"""Offline operational comparability gate for the MetroPT-3 v2 prototype.

The rule uses only source timestamps and operating-state fields. Temperature
values are read only after a temporally valid, operationally comparable window
has been selected.
"""

from __future__ import annotations

import array
import csv
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Sequence

from prototype import (
    QualificationInputError,
    QualificationReport,
    Selection,
    _expected_csv_hash,
    _report_for_selection,
    iter_temporal_windows,
    parse_naive_timestamp,
)


OPERATIONAL_RULE_VERSION = "metropt3-digital-current-oil-comparator-v2"
OPERATIONAL_RULE = (
    "Les 11 lignes doivent partager un mode COMP/DV_eletric reconnu et le même "
    "drapeau binaire Oil_level. COMP=0,DV_eletric=1 signifie en charge; "
    "COMP=1,DV_eletric=0 signifie arrêté/déchargé. Les autres combinaisons sont "
    "inconnues ou contradictoires. La comparabilité affinée exige aussi la même "
    "classe Motor_current la plus proche des valeurs nominales (0, 4, 7 ou 9 A); "
    "les égalités et contradictions sont rejetées. Les frontières au milieu des "
    "centres sont exploratoires, pas des limites validées par UCI."
)

# Encoded byte values allow a compact streaming index for the 1.5M-row CSV.
_UNKNOWN = 0
_LOADED_OIL_OK = 1
_LOADED_OIL_LOW = 2
_UNLOADED_OIL_OK = 3
_UNLOADED_OIL_LOW = 4
_SIGNATURES = {
    _LOADED_OIL_OK: ("LOADED", 0),
    _LOADED_OIL_LOW: ("LOADED", 1),
    _UNLOADED_OIL_OK: ("OFF_OR_OFFLOADED", 0),
    _UNLOADED_OIL_LOW: ("OFF_OR_OFFLOADED", 1),
}
_CURRENT_NOMINALS = (0.0, 4.0, 7.0, 9.0)
_CURRENT_OFF = 0
_CURRENT_OFFLOADED = 1
_CURRENT_LOADED = 2
_CURRENT_STARTING = 3
_CURRENT_UNKNOWN = 255


@dataclass(frozen=True)
class WindowAssessment:
    temporal_windows: int
    digitally_comparable_windows: int
    comparable_windows: int
    unknown_or_conflicting_state: int
    mixed_operating_mode: int
    mixed_oil_level_flag: int
    invalid_or_conflicting_current: int
    mixed_current_category: int
    first_temporal_selection: Selection | None
    first_digital_selection: Selection | None
    first_comparable_selection: Selection | None


@dataclass(frozen=True)
class OperationalQualificationReport:
    source_file: str
    source_sha256: str
    source_id: str
    timestamp_interpretation: str
    temporal_policy: str
    operational_rule_version: str
    operational_rule: str
    rows_in_source: int
    temporal_windows_at_plus_minus_10s: int
    digitally_comparable_windows: int
    operationally_comparable_windows: int
    rejected_unknown_or_conflicting_state: int
    rejected_mixed_operating_mode: int
    rejected_mixed_oil_level_flag: int
    rejected_invalid_or_conflicting_current: int
    rejected_mixed_current_category: int
    selected_window: QualificationReport | None
    oil_state_warning: str


def _binary_flag(value: str) -> int | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number == 0.0:
        return 0
    if number == 1.0:
        return 1
    return None


def encode_operational_signature(
    comp: str,
    dv_eletric: str,
    oil_level: str,
    motor_current: str,
) -> int:
    """Encode a validated mode/oil tuple; return 0 for unknown rows.

    Current is required to be finite but is not thresholded: the official source
    only describes representative values as "close to" nominal values.
    """
    comp_flag = _binary_flag(comp)
    dv_flag = _binary_flag(dv_eletric)
    oil_flag = _binary_flag(oil_level)
    try:
        current = float(motor_current)
    except (TypeError, ValueError):
        return _UNKNOWN
    if comp_flag is None or dv_flag is None or oil_flag is None or not math.isfinite(current):
        return _UNKNOWN
    if comp_flag == 0 and dv_flag == 1:
        return _LOADED_OIL_LOW if oil_flag else _LOADED_OIL_OK
    if comp_flag == 1 and dv_flag == 0:
        return _UNLOADED_OIL_LOW if oil_flag else _UNLOADED_OIL_OK
    return _UNKNOWN


def classify_motor_current(value: str) -> int:
    """Assign nearest documented nominal A value; return 255 on a tie/invalid."""
    try:
        current = float(value)
    except (TypeError, ValueError):
        return _CURRENT_UNKNOWN
    if not math.isfinite(current):
        return _CURRENT_UNKNOWN
    distances = [abs(current - nominal) for nominal in _CURRENT_NOMINALS]
    nearest = min(distances)
    winners = [index for index, distance in enumerate(distances) if distance == nearest]
    return winners[0] if len(winners) == 1 else _CURRENT_UNKNOWN


def _current_agrees_with_digital_mode(signature: int, current_class: int) -> bool:
    mode, _oil = _SIGNATURES[signature]
    if mode == "LOADED":
        return current_class == _CURRENT_LOADED
    if mode == "OFF_OR_OFFLOADED":
        return current_class in (_CURRENT_OFF, _CURRENT_OFFLOADED)
    return False


def assess_windows(
    timestamps_seconds: Sequence[int],
    operational_signatures: Sequence[int],
    motor_current_classes: Sequence[int],
) -> WindowAssessment:
    """Count temporal and comparable windows without accepting temperatures."""
    if len(timestamps_seconds) != len(operational_signatures) or len(timestamps_seconds) != len(motor_current_classes):
        raise QualificationInputError("timestamp and operating-state index lengths differ")
    temporal = digital_comparable = comparable = 0
    unknown = mixed_mode = mixed_oil = invalid_current = mixed_current = 0
    first_temporal = first_digital = first_comparable = None
    for selection in iter_temporal_windows(timestamps_seconds):
        temporal += 1
        if first_temporal is None:
            first_temporal = selection
        reason = _window_rejection_reason(selection, operational_signatures, motor_current_classes)
        if reason == "unknown":
            unknown += 1
            continue
        if reason == "mixed_mode":
            mixed_mode += 1
            continue
        if reason == "mixed_oil":
            mixed_oil += 1
            continue
        digital_comparable += 1
        if first_digital is None:
            first_digital = selection
        if reason == "invalid_current":
            invalid_current += 1
            continue
        if reason == "mixed_current":
            mixed_current += 1
            continue
        comparable += 1
        if first_comparable is None:
            first_comparable = selection
    return WindowAssessment(
        temporal_windows=temporal,
        digitally_comparable_windows=digital_comparable,
        comparable_windows=comparable,
        unknown_or_conflicting_state=unknown,
        mixed_operating_mode=mixed_mode,
        mixed_oil_level_flag=mixed_oil,
        invalid_or_conflicting_current=invalid_current,
        mixed_current_category=mixed_current,
        first_temporal_selection=first_temporal,
        first_digital_selection=first_digital,
        first_comparable_selection=first_comparable,
    )


def _window_rejection_reason(
    selection: Selection,
    operational_signatures: Sequence[int],
    motor_current_classes: Sequence[int],
) -> str | None:
    """Apply the established operational gate to one timestamp-only window."""
    indices = (selection.target_index, *selection.reference_indices)
    row_codes = [operational_signatures[index] for index in indices]
    if any(code not in _SIGNATURES for code in row_codes):
        return "unknown"
    decoded = [_SIGNATURES[code] for code in row_codes]
    if len({item[0] for item in decoded}) != 1:
        return "mixed_mode"
    if len({item[1] for item in decoded}) != 1:
        return "mixed_oil"
    current_rows = [motor_current_classes[index] for index in indices]
    if any(
        current == _CURRENT_UNKNOWN or not _current_agrees_with_digital_mode(code, current)
        for code, current in zip(row_codes, current_rows)
    ):
        return "invalid_current"
    if len(set(current_rows)) != 1:
        return "mixed_current"
    return None


def iter_comparable_windows(
    timestamps_seconds: Sequence[int],
    operational_signatures: Sequence[int],
    motor_current_classes: Sequence[int],
):
    """Yield strict exploratory windows using the same gate as assess_windows.

    No temperature values are accepted by this selector.
    """
    if len(timestamps_seconds) != len(operational_signatures) or len(timestamps_seconds) != len(motor_current_classes):
        raise QualificationInputError("timestamp and operating-state index lengths differ")
    for selection in iter_temporal_windows(timestamps_seconds):
        if _window_rejection_reason(selection, operational_signatures, motor_current_classes) is None:
            yield selection


def _read_operational_index(csv_path: Path) -> tuple[array.array, bytearray, bytearray, int]:
    timestamps = array.array("q")
    signatures = bytearray()
    current_classes = bytearray()
    row_count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"timestamp", "COMP", "DV_eletric", "Motor_current", "Oil_level"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise QualificationInputError("CSV lacks timestamp or required operational columns")
        for row in reader:
            row_count += 1
            timestamp = parse_naive_timestamp(row.get("timestamp", ""))
            if timestamps and timestamp <= timestamps[-1]:
                raise QualificationInputError("source timestamps are duplicated or not increasing")
            timestamps.append(timestamp)
            signatures.append(encode_operational_signature(
                row.get("COMP", ""), row.get("DV_eletric", ""),
                row.get("Oil_level", ""), row.get("Motor_current", ""),
            ))
            current_classes.append(classify_motor_current(row.get("Motor_current", "")))
    return timestamps, signatures, current_classes, row_count


def build_operational_report(csv_path: Path, manifest_path: Path) -> OperationalQualificationReport:
    expected_hash = _expected_csv_hash(manifest_path, csv_path)
    digest = hashlib.sha256()
    with csv_path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    actual_hash = digest.hexdigest().upper()
    if actual_hash != expected_hash:
        raise QualificationInputError("CSV SHA-256 does not match the source manifest")

    timestamps, signatures, current_classes, row_count = _read_operational_index(csv_path)
    assessment = assess_windows(timestamps, signatures, current_classes)
    selected_report = None
    warning = "Aucune fenêtre opérationnellement comparable sélectionnée."
    selection = assessment.first_comparable_selection
    if selection is not None:
        selected_report = _report_for_selection(csv_path, actual_hash, row_count, selection)
        oil_states = {
            _SIGNATURES[signatures[index]][1]
            for index in (selection.target_index, *selection.reference_indices)
        }
        if oil_states == {1}:
            warning = "Oil_level=1 sur les 11 lignes: signal source indique un niveau sous la valeur attendue; mesure NON QUALIFIÉ, pas invalidée."
        else:
            warning = "Oil_level=0 sur les 11 lignes; cela ne qualifie pas à lui seul la qualité métier."

    return OperationalQualificationReport(
        source_file=csv_path.name,
        source_sha256=actual_hash,
        source_id="UCI:791 / DOI:10.24432/C5VW3R",
        timestamp_interpretation="horloge source naïve; UTC non vérifié",
        temporal_policy="10 échéances quotidiennes; observation originale la plus proche, tolérance inclusive ±10 s; égalités et doublons rejetés",
        operational_rule_version=OPERATIONAL_RULE_VERSION,
        operational_rule=OPERATIONAL_RULE,
        rows_in_source=row_count,
        temporal_windows_at_plus_minus_10s=assessment.temporal_windows,
        digitally_comparable_windows=assessment.digitally_comparable_windows,
        operationally_comparable_windows=assessment.comparable_windows,
        rejected_unknown_or_conflicting_state=assessment.unknown_or_conflicting_state,
        rejected_mixed_operating_mode=assessment.mixed_operating_mode,
        rejected_mixed_oil_level_flag=assessment.mixed_oil_level_flag,
        rejected_invalid_or_conflicting_current=assessment.invalid_or_conflicting_current,
        rejected_mixed_current_category=assessment.mixed_current_category,
        selected_window=selected_report,
        oil_state_warning=warning,
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_operational_report(args.csv, args.manifest)
    except (OSError, QualificationInputError) as exc:
        parser.error(str(exc))
    print(json.dumps(asdict(report), ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
