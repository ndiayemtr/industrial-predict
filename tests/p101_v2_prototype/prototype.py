"""Offline, exploratory P101 v2 temporal-selection prototype.

This module is intentionally independent of the P101 v1 evaluator, loader,
contracts, database, and writer. It selects source rows using timestamps only.
It does not assign business quality or UTC semantics to naive source times.
"""

from __future__ import annotations

import array
import bisect
import csv
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import statistics
from typing import Iterator, Sequence


POLICY_VERSION = "p101-v2-nearest-daily-10s-prototype-1"
REFERENCE_COUNT = 10
CADENCE_SECONDS = 86_400
TOLERANCE_SECONDS = 10
SOURCE_UNIT = "°C"
QUALITY_STATUS = "NON QUALIFIÉ"


@dataclass(frozen=True)
class Selection:
    target_index: int
    reference_indices: tuple[int, ...]
    deadline_seconds: tuple[int, ...]
    offsets_seconds: tuple[int, ...]


@dataclass(frozen=True)
class SourceObservation:
    source_row_id: str
    csv_line: int
    timestamp_original: str
    offset_seconds: int
    temperature_original: str
    temperature_value: float
    unit: str
    technical_status: str
    quality_status: str
    context: dict[str, str]


@dataclass(frozen=True)
class QualificationReport:
    policy_version: str
    source_file: str
    source_sha256: str
    source_id: str
    timestamp_interpretation: str
    rows_in_source: int
    target: SourceObservation
    references: tuple[SourceObservation, ...]
    no_duplicate_timestamps: bool
    no_reused_rows_within_window: bool
    quality_status: str
    technical_validation: str
    exploratory_statistics: dict[str, float | bool | str]


class QualificationInputError(ValueError):
    """The source file or its timestamp index violates the offline contract."""


def parse_naive_timestamp(value: str) -> int:
    """Parse a source wall-clock timestamp without inventing a timezone."""
    if not isinstance(value, str) or not value.strip():
        raise QualificationInputError("timestamp is empty")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise QualificationInputError("timestamp is invalid") from exc
    if parsed.tzinfo is not None and parsed.utcoffset() is not None:
        raise QualificationInputError("prototype accepts only source-naive timestamps")
    epoch = datetime(1970, 1, 1)
    delta = parsed - epoch
    if delta.microseconds:
        # The inspected source has whole-second precision. Preserve the rule
        # rather than silently rounding any future input.
        raise QualificationInputError("sub-second timestamps are unsupported")
    return delta.days * CADENCE_SECONDS + delta.seconds


def iter_temporal_windows(
    timestamps_seconds: Sequence[int],
    *,
    tolerance_seconds: int = TOLERANCE_SECONDS,
) -> Iterator[Selection]:
    """Yield complete windows in source timestamp order.

    Each deadline uses its unique nearest original timestamp within the
    inclusive tolerance. Equal-distance ties, duplicate timestamps, missing
    deadlines, or row reuse inside the window reject that target.
    """
    if type(tolerance_seconds) is not int or not 0 <= tolerance_seconds <= TOLERANCE_SECONDS:
        raise QualificationInputError("tolerance must be an integer from 0 through 10 seconds")
    if any(type(value) is not int for value in timestamps_seconds):
        raise QualificationInputError("timestamps must be integer source-clock seconds")
    if any(left >= right for left, right in zip(timestamps_seconds, timestamps_seconds[1:])):
        raise QualificationInputError("timestamps must be strictly increasing and unique")

    for target_index, target in enumerate(timestamps_seconds):
        refs: list[int] = []
        deadlines: list[int] = []
        offsets: list[int] = []
        used: set[int] = {target_index}
        valid = True
        for days_before in range(REFERENCE_COUNT, 0, -1):
            deadline = target - days_before * CADENCE_SECONDS
            right = bisect.bisect_left(timestamps_seconds, deadline)
            candidates = []
            if right:
                candidates.append(right - 1)
            if right < len(timestamps_seconds):
                candidates.append(right)
            if not candidates:
                valid = False
                break
            distances = [abs(timestamps_seconds[index] - deadline) for index in candidates]
            nearest = min(distances)
            if nearest > tolerance_seconds:
                valid = False
                break
            winners = [index for index, distance in zip(candidates, distances) if distance == nearest]
            if len(winners) != 1:
                valid = False
                break
            selected_index = winners[0]
            if selected_index in used:
                valid = False
                break
            used.add(selected_index)
            refs.append(selected_index)
            deadlines.append(deadline)
            offsets.append(timestamps_seconds[selected_index] - deadline)
        if valid and len(refs) == REFERENCE_COUNT:
            yield Selection(target_index, tuple(refs), tuple(deadlines), tuple(offsets))


def select_first_window(
    timestamps_seconds: Sequence[int],
    *,
    tolerance_seconds: int = TOLERANCE_SECONDS,
) -> Selection | None:
    """Return the earliest complete window in timestamp order."""
    return next(iter_temporal_windows(timestamps_seconds, tolerance_seconds=tolerance_seconds), None)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _expected_csv_hash(manifest_path: Path, csv_path: Path) -> str:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest["extracted_files"]:
            if entry["filename"] == csv_path.name:
                expected = entry["sha256"].upper()
                if len(expected) == 64 and all(c in "0123456789ABCDEF" for c in expected):
                    return expected
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise QualificationInputError("source manifest is unreadable or incomplete") from exc
    raise QualificationInputError("CSV hash is absent from the source manifest")


def _read_timestamp_index(csv_path: Path) -> tuple[array.array, int]:
    timestamps = array.array("q")
    row_count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or "timestamp" not in reader.fieldnames or "Oil_temperature" not in reader.fieldnames:
            raise QualificationInputError("CSV header is missing required columns")
        for csv_line, row in enumerate(reader, start=2):
            row_count += 1
            timestamp = parse_naive_timestamp(row.get("timestamp", ""))
            if timestamps and timestamp <= timestamps[-1]:
                raise QualificationInputError("source timestamps are duplicated or not increasing")
            timestamps.append(timestamp)
    return timestamps, row_count


def _read_selected_rows(csv_path: Path, selected_lines: set[int]) -> dict[int, dict[str, str]]:
    selected: dict[int, dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        for csv_line, row in enumerate(reader, start=2):
            if csv_line in selected_lines:
                selected[csv_line] = {key: value or "" for key, value in row.items() if key is not None}
                if len(selected) == len(selected_lines):
                    break
    if set(selected) != selected_lines:
        raise QualificationInputError("one or more selected source lines could not be reread")
    return selected


def _observation(
    row: dict[str, str],
    *,
    csv_line: int,
    offset_seconds: int,
) -> SourceObservation:
    raw_value = row.get("Oil_temperature", "")
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise QualificationInputError("selected temperature is not numeric") from exc
    if not math.isfinite(value):
        raise QualificationInputError("selected temperature is not finite")
    source_row_id = row.get("") or ""
    if not source_row_id:
        raise QualificationInputError("unnamed CSV index value is empty for a selected row")
    context_names = (
        "COMP", "Oil_level", "Motor_current", "DV_eletric", "DV_pressure",
        "TP2", "TP3", "Reservoirs", "Towers", "MPG", "LPS", "Pressure_switch",
    )
    return SourceObservation(
        source_row_id=source_row_id,
        csv_line=csv_line,
        timestamp_original=row.get("timestamp", ""),
        offset_seconds=offset_seconds,
        temperature_original=raw_value,
        temperature_value=value,
        unit=SOURCE_UNIT,
        technical_status="VALIDÉ: ligne source, timestamp naïf unique, valeur numérique finie",
        quality_status=QUALITY_STATUS,
        context={name: row.get(name, "") for name in context_names},
    )


def _report_for_selection(
    csv_path: Path,
    actual_hash: str,
    row_count: int,
    selection: Selection,
) -> QualificationReport:
    target_line = selection.target_index + 2  # header is physical CSV line 1
    ref_lines = [index + 2 for index in selection.reference_indices]
    selected_lines = {target_line, *ref_lines}
    if len(selected_lines) != REFERENCE_COUNT + 1:
        raise QualificationInputError("selected source row was reused within the window")
    raw_rows = _read_selected_rows(csv_path, selected_lines)
    target_row = raw_rows[target_line]
    target = _observation(target_row, csv_line=target_line, offset_seconds=0)
    references = tuple(
        _observation(raw_rows[line], csv_line=line, offset_seconds=offset)
        for line, offset in zip(ref_lines, selection.offsets_seconds)
    )
    if len({row.source_row_id for row in (target, *references)}) != REFERENCE_COUNT + 1:
        raise QualificationInputError("selected source row identifiers are not unique")

    ref_values = [row.temperature_value for row in references]
    target_value = target.temperature_value
    mean = statistics.mean(ref_values)
    deviation = statistics.stdev(ref_values)
    target_delta = abs(target_value - mean)
    threshold = deviation * 3
    exploratory = {
        "reference_mean_c": mean,
        "reference_sample_stddev_c": deviation,
        "target_absolute_deviation_c": target_delta,
        "reference_threshold_3_sample_stddev_c": threshold,
        "exploratory_flag_only": target_delta > threshold,
        "interpretation": "statistique expérimentale; ni résultat P101 validé ni probabilité de panne",
    }
    return QualificationReport(
        policy_version=POLICY_VERSION,
        source_file=csv_path.name,
        source_sha256=actual_hash,
        source_id="UCI:791 / DOI:10.24432/C5VW3R",
        timestamp_interpretation="horloge source naïve; UTC non vérifié",
        rows_in_source=row_count,
        target=target,
        references=references,
        no_duplicate_timestamps=True,
        no_reused_rows_within_window=True,
        quality_status=QUALITY_STATUS,
        technical_validation="11/11 lignes originales relues; timestamps conservés; valeurs finies; unité °C déclarée par UCI",
        exploratory_statistics=exploratory,
    )


def build_report_for_selection(
    csv_path: Path,
    manifest_path: Path,
    selection: Selection,
) -> QualificationReport:
    """Build a report for a preselected timestamp-only window."""
    expected_hash = _expected_csv_hash(manifest_path, csv_path)
    actual_hash = _sha256(csv_path)
    if actual_hash != expected_hash:
        raise QualificationInputError("CSV SHA-256 does not match the source manifest")

    timestamps, row_count = _read_timestamp_index(csv_path)
    if selection.target_index >= len(timestamps) or any(index >= len(timestamps) for index in selection.reference_indices):
        raise QualificationInputError("selection points outside the source CSV")
    if len(selection.reference_indices) != REFERENCE_COUNT:
        raise QualificationInputError("selection does not contain ten references")
    if len({selection.target_index, *selection.reference_indices}) != REFERENCE_COUNT + 1:
        raise QualificationInputError("selection reuses a source row")
    if len(selection.offsets_seconds) != REFERENCE_COUNT or any(
        type(offset) is not int or abs(offset) > TOLERANCE_SECONDS for offset in selection.offsets_seconds
    ):
        raise QualificationInputError("selection offsets do not satisfy the v2 tolerance")
    for index, deadline, offset in zip(selection.reference_indices, selection.deadline_seconds, selection.offsets_seconds):
        if timestamps[index] - deadline != offset:
            raise QualificationInputError("selection offset does not match the source timestamp")
    return _report_for_selection(csv_path, actual_hash, row_count, selection)


def build_report(csv_path: Path, manifest_path: Path) -> QualificationReport:
    expected_hash = _expected_csv_hash(manifest_path, csv_path)
    actual_hash = _sha256(csv_path)
    if actual_hash != expected_hash:
        raise QualificationInputError("CSV SHA-256 does not match the source manifest")
    timestamps, row_count = _read_timestamp_index(csv_path)
    selection = select_first_window(timestamps)
    if selection is None:
        raise QualificationInputError("no complete unique window exists within ±10 seconds")
    return _report_for_selection(csv_path, actual_hash, row_count, selection)


def report_as_dict(report: QualificationReport) -> dict[str, object]:
    return asdict(report)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_report(args.csv, args.manifest)
    except (OSError, QualificationInputError) as exc:
        # Error messages intentionally exclude data rows and temperature values.
        parser.error(str(exc))
    print(json.dumps(report_as_dict(report), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
