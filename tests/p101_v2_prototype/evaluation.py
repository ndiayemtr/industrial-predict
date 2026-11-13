"""Offline, exploratory statistical evaluation of all comparable MetroPT-3 windows."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
from typing import Any

from operational import (
    OPERATIONAL_RULE_VERSION,
    _read_operational_index,
    iter_comparable_windows,
)
from prototype import (
    POLICY_VERSION,
    QualificationInputError,
    Selection,
    _expected_csv_hash,
    _read_selected_rows,
    _sha256,
)


EVALUATION_VERSION = "p101-v2-metropt3-exploratory-three-sample-sigma-1"
QUALITY_STATUS = "NON QUALIFIÉ"


@dataclass(frozen=True)
class EvaluationRow:
    source_row_id: str
    csv_line: int
    timestamp_original: str
    offset_seconds: int
    temperature_original: str
    temperature_c: float | None
    unit: str
    quality_status: str = QUALITY_STATUS


@dataclass(frozen=True)
class WindowResult:
    window_id: str
    target: EvaluationRow
    references: tuple[EvaluationRow, ...]
    status: str
    abstention_reason: str | None
    reference_mean_c: float | None
    reference_sample_stddev_c: float | None
    target_absolute_deviation_c: float | None
    threshold_3_sample_stddev_c: float | None
    thermal_deviation_flag: bool | None
    quality_status: str = QUALITY_STATUS


@dataclass(frozen=True)
class EvaluationReport:
    evaluation_version: str
    source_file: str
    source_sha256: str
    source_id: str
    timestamp_interpretation: str
    temporal_policy_version: str
    operational_rule_version: str
    operational_rule: str
    statistical_rule: str
    quality_status: str
    windows_examined: int
    mathematically_evaluable: int
    thermal_flag_true: int
    thermal_flag_false: int
    mathematical_abstentions: int
    abstention_reasons: dict[str, int]
    chronology_by_month_source_clock: dict[str, dict[str, int]]
    distributions: dict[str, dict[str, float | int | None]]
    overlap: dict[str, int | float]
    first_thermal_flag_true_window_id: str | None
    window_results: tuple[WindowResult, ...]


def _evaluation_row(raw: dict[str, str], *, line: int, offset: int) -> EvaluationRow:
    source_id = raw.get("", "")
    timestamp = raw.get("timestamp", "")
    temperature_raw = raw.get("Oil_temperature", "")
    try:
        value = float(temperature_raw)
    except (TypeError, ValueError):
        value = None
    if value is not None and not math.isfinite(value):
        value = None
    return EvaluationRow(
        source_row_id=source_id,
        csv_line=line,
        timestamp_original=timestamp,
        offset_seconds=offset,
        temperature_original=temperature_raw,
        temperature_c=value,
        unit="°C",
    )


def evaluate_window(
    selection: Selection,
    raw_rows_by_line: dict[int, dict[str, str]],
) -> WindowResult:
    """Evaluate one already-selected window; selection never sees temperatures."""
    target_line = selection.target_index + 2
    reference_lines = [index + 2 for index in selection.reference_indices]
    if len(selection.reference_indices) != 10 or len(set([target_line, *reference_lines])) != 11:
        raise QualificationInputError("window must contain eleven distinct source rows")
    if len(selection.offsets_seconds) != 10:
        raise QualificationInputError("window must contain ten reference offsets")
    try:
        target = _evaluation_row(raw_rows_by_line[target_line], line=target_line, offset=0)
        references = tuple(
            _evaluation_row(raw_rows_by_line[line], line=line, offset=offset)
            for line, offset in zip(reference_lines, selection.offsets_seconds)
        )
    except KeyError as exc:
        raise QualificationInputError("selected source row is missing from reread") from exc
    rows = (target, *references)
    if any(not row.source_row_id or not row.timestamp_original for row in rows):
        raise QualificationInputError("selected source row lacks its original id or timestamp")
    if len({row.source_row_id for row in rows}) != 11:
        raise QualificationInputError("window reuses or duplicates a source row id")
    window_id = f"target-row-{target.source_row_id}-line-{target.csv_line}"
    values = [row.temperature_c for row in references]
    if target.temperature_c is None or any(value is None for value in values):
        return WindowResult(window_id, target, references, "ABSTAINED", "invalid_or_nonfinite_temperature",
                            None, None, None, None, None)
    finite_values = [float(value) for value in values]
    mean = statistics.mean(finite_values)
    stddev = statistics.stdev(finite_values)
    if stddev == 0.0:
        return WindowResult(window_id, target, references, "ABSTAINED", "zero_reference_sample_stddev",
                            mean, stddev, abs(float(target.temperature_c) - mean), 0.0, None)
    delta = abs(float(target.temperature_c) - mean)
    threshold = 3.0 * stddev
    return WindowResult(window_id, target, references, "EVALUABLE", None, mean, stddev,
                        delta, threshold, delta > threshold)


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "median": None, "p95": None, "max": None}
    ordered = sorted(values)
    p95 = ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]
    return {"count": len(ordered), "min": ordered[0], "median": statistics.median(ordered),
            "p95": p95, "max": ordered[-1]}


def build_evaluation(csv_path: Path, manifest_path: Path) -> EvaluationReport:
    expected_hash = _expected_csv_hash(manifest_path, csv_path)
    actual_hash = _sha256(csv_path)
    if actual_hash != expected_hash:
        raise QualificationInputError("CSV SHA-256 does not match the source manifest")

    timestamps, signatures, current_classes, row_count = _read_operational_index(csv_path)
    # Select all windows strictly from timestamps and operational fields first.
    selections = tuple(iter_comparable_windows(timestamps, signatures, current_classes))
    if len(selections) != 727:
        raise QualificationInputError(f"expected 727 previously qualified exploratory windows, got {len(selections)}")
    selected_lines = {
        index + 2
        for selection in selections
        for index in (selection.target_index, *selection.reference_indices)
    }
    raw_rows = _read_selected_rows(csv_path, selected_lines)
    results = tuple(evaluate_window(selection, raw_rows) for selection in selections)

    evaluable = [result for result in results if result.status == "EVALUABLE"]
    true_results = [result for result in evaluable if result.thermal_deviation_flag is True]
    false_results = [result for result in evaluable if result.thermal_deviation_flag is False]
    reasons: dict[str, int] = {}
    for result in results:
        if result.abstention_reason:
            reasons[result.abstention_reason] = reasons.get(result.abstention_reason, 0) + 1

    chronology: dict[str, dict[str, int]] = {}
    for result in results:
        month = datetime.fromisoformat(result.target.timestamp_original).strftime("%Y-%m")
        counts = chronology.setdefault(month, {"examined": 0, "evaluated": 0, "flag_true": 0, "flag_false": 0, "abstained": 0})
        counts["examined"] += 1
        if result.status == "ABSTAINED":
            counts["abstained"] += 1
        else:
            counts["evaluated"] += 1
            counts["flag_true" if result.thermal_deviation_flag else "flag_false"] += 1

    selected_indices = [
        index
        for selection in selections
        for index in (selection.target_index, *selection.reference_indices)
    ]
    memberships: dict[int, int] = {}
    for index in selected_indices:
        memberships[index] = memberships.get(index, 0) + 1
    deviations = [float(result.target_absolute_deviation_c) for result in evaluable]
    thresholds = [float(result.threshold_3_sample_stddev_c) for result in evaluable]
    stddevs = [float(result.reference_sample_stddev_c) for result in evaluable]
    return EvaluationReport(
        evaluation_version=EVALUATION_VERSION,
        source_file=csv_path.name,
        source_sha256=actual_hash,
        source_id="UCI:791 / DOI:10.24432/C5VW3R",
        timestamp_interpretation="horloge source naïve; UTC non vérifié",
        temporal_policy_version=POLICY_VERSION,
        operational_rule_version=OPERATIONAL_RULE_VERSION,
        operational_rule="Fenêtres strictement comparables par le sélecteur opérationnel v2, appliqué avant lecture des températures;",
        statistical_rule="10 références; moyenne arithmétique; écart-type d'échantillon; écart absolu cible-moyenne > 3 × écart-type; seuil strict.",
        quality_status=QUALITY_STATUS,
        windows_examined=len(results),
        mathematically_evaluable=len(evaluable),
        thermal_flag_true=len(true_results),
        thermal_flag_false=len(false_results),
        mathematical_abstentions=len(results) - len(evaluable),
        abstention_reasons=reasons,
        chronology_by_month_source_clock=chronology,
        distributions={"absolute_target_deviation_c": _distribution(deviations),
                       "reference_sample_stddev_c": _distribution(stddevs),
                       "threshold_3_sample_stddev_c": _distribution(thresholds)},
        overlap={"window_count": len(results), "row_slots_across_windows": len(selected_indices),
                 "unique_source_rows": len(memberships),
                 "source_rows_used_by_multiple_windows": sum(1 for count in memberships.values() if count > 1),
                 "maximum_windows_per_source_row": max(memberships.values(), default=0),
                 "windows_are_independent": 0},
        first_thermal_flag_true_window_id=true_results[0].window_id if true_results else None,
        window_results=results,
    )


def write_report(report: EvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=False)
    json_path = output_dir / "evaluation.json"
    markdown_path = output_dir / "evaluation.md"
    payload = asdict(report)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    true_rows = [row for row in report.window_results if row.thermal_deviation_flag is True]
    lines = [
        "# Évaluation expérimentale P101 v2 — MetroPT-3",
        "",
        f"- Version : `{report.evaluation_version}`",
        f"- Source : `{report.source_id}` — `{report.source_file}`",
        f"- SHA-256 : `{report.source_sha256}`",
        f"- Fuseau : {report.timestamp_interpretation}",
        f"- Qualité métier : **{report.quality_status}**",
        f"- Sélection : `{report.temporal_policy_version}` + `{report.operational_rule_version}`; les fenêtres sont sélectionnées avant lecture des températures.",
        f"- Règle statistique : {report.statistical_rule}",
        "",
        "## Résumé",
        "",
        f"- Fenêtres examinées : {report.windows_examined}",
        f"- Évaluables mathématiquement : {report.mathematically_evaluable}",
        f"- Indicateur vrai : {report.thermal_flag_true}",
        f"- Indicateur faux : {report.thermal_flag_false}",
        f"- Abstentions mathématiques : {report.mathematical_abstentions} — `{report.abstention_reasons}`",
        f"- Première fenêtre avec indicateur vrai : `{report.first_thermal_flag_true_window_id}`",
        f"- Chevauchement : {report.overlap['row_slots_across_windows']} places, {report.overlap['unique_source_rows']} lignes uniques, {report.overlap['source_rows_used_by_multiple_windows']} lignes réutilisées entre fenêtres.",
        "",
        "Un indicateur vrai signale uniquement un écart thermique exploratoire supérieur à 3σ. Ce n'est ni une panne confirmée, ni une prédiction validée, ni une probabilité. Les fenêtres se chevauchent et ne constituent pas des observations indépendantes.",
        "Oil_level=1 reste un signal opérationnel d'avertissement; il n'a pas été converti en invalidation automatique. Les onze températures de chaque fenêtre conservent leur statut NON QUALIFIÉ.",
        "Aucun timestamp n'a été converti ni attribué à UTC.",
        "",
        "## Chronologie sur l'horloge source brute",
        "",
        "| Mois source | Fenêtres | Évaluées | Vraies | Fausses | Abstentions |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for month, counts in report.chronology_by_month_source_clock.items():
        lines.append(f"| {month} | {counts['examined']} | {counts['evaluated']} | {counts['flag_true']} | {counts['flag_false']} | {counts['abstained']} |")
    lines += ["", "## Distributions", "", "| Mesure (°C) | N | Min | Médiane | P95 | Max |", "|---|---:|---:|---:|---:|---:|"]
    for name, distribution in report.distributions.items():
        lines.append(f"| {name} | {distribution['count']} | {distribution['min']} | {distribution['median']} | {distribution['p95']} | {distribution['max']} |")
    lines += ["", "## Chronologie des indicateurs vrais", "", "| Fenêtre | Ligne cible | Timestamp brut | Écart °C | Seuil 3σ °C |", "|---|---:|---|---:|---:|"]
    for result in true_rows:
        lines.append(f"| {result.window_id} | {result.target.csv_line} | {result.target.timestamp_original} | {result.target_absolute_deviation_c} | {result.threshold_3_sample_stddev_c} |")
    lines += ["", "Les détails des 727 fenêtres, des onze lignes sources et des températures originales sont dans `evaluation.json`.", ""]
    markdown_path.write_text("\n".join(lines), encoding="utf-8")
    return markdown_path, json_path


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_evaluation(args.csv, args.manifest)
        paths = write_report(report, args.output_dir)
    except (OSError, QualificationInputError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"summary": {key: value for key, value in asdict(report).items() if key != "window_results"},
                      "reports": [str(path) for path in paths]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
