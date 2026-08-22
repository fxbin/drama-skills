#!/usr/bin/env python3
"""Validate balanced blind screenplay judgments and enforce the quality target."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


DIMENSIONS = {
    "hook_payoff": 20,
    "causality": 20,
    "character": 15,
    "dialogue_action": 15,
    "visual_drama": 15,
    "pacing_retention": 15,
}
FAMILIES = {"codex", "kimi"}
SHA256_RE = re.compile(r"[0-9a-f]{64}")
TARGET_GAP_REDUCTION = 0.30


class GateError(ValueError):
    """The evaluation evidence is malformed or insufficient."""


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GateError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise GateError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validated_scores(value: object, *, report: Path, label: str) -> float:
    if not isinstance(value, dict) or set(value) != set(DIMENSIONS):
        raise GateError(f"{report}: {label} must score every fixed dimension")
    total = 0.0
    for dimension, maximum in DIMENSIONS.items():
        score = value[dimension]
        if isinstance(score, bool) or not isinstance(score, (int, float)):
            raise GateError(f"{report}: {label}.{dimension} must be numeric")
        if score < 0 or score > maximum:
            raise GateError(
                f"{report}: {label}.{dimension} must be between 0 and {maximum}"
            )
        total += float(score)
    return total


def _artifact(path_value: object, root: Path, expected_sha: object, label: str) -> str:
    if not isinstance(path_value, str) or not path_value:
        raise GateError(f"{label} artifact path is required")
    if not isinstance(expected_sha, str) or SHA256_RE.fullmatch(expected_sha) is None:
        raise GateError(f"{label} artifact sha256 is invalid")
    path = (root / path_value).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise GateError(f"{label} artifact is missing or escapes the evaluation root")
    actual = _sha256(path)
    if actual != expected_sha:
        raise GateError(f"{label} artifact digest changed")
    return actual


def evaluate(manifest_path: Path) -> dict[str, Any]:
    manifest_path = manifest_path.expanduser().resolve(strict=True)
    root = manifest_path.parent
    manifest = _load_object(manifest_path)
    if manifest.get("schema_version") != 2:
        raise GateError("schema_version must be 2")
    threshold = manifest.get("target_quality_gap_reduction")
    if threshold != TARGET_GAP_REDUCTION:
        raise GateError(
            f"target_quality_gap_reduction must be {TARGET_GAP_REDUCTION}"
        )
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) < 2:
        raise GateError("at least two fixed cases are required")

    case_results: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    for case in cases:
        if not isinstance(case, dict):
            raise GateError("each case must be an object")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen_case_ids:
            raise GateError("case_id must be unique and non-empty")
        seen_case_ids.add(case_id)
        baseline_sha = _artifact(
            case.get("baseline_artifact"), root, case.get("baseline_sha256"), "baseline"
        )
        candidate_sha = _artifact(
            case.get("candidate_artifact"), root, case.get("candidate_sha256"), "candidate"
        )
        if baseline_sha == candidate_sha:
            raise GateError(f"{case_id}: baseline and candidate artifacts are identical")

        runs = case.get("judge_runs")
        expected_run_count = len(FAMILIES) * 2
        if not isinstance(runs, list) or len(runs) != expected_run_count:
            raise GateError(
                f"{case_id}: exactly {expected_run_count} balanced judge runs are required"
            )
        family_counts: Counter[str] = Counter()
        family_positions: dict[str, Counter[str]] = {
            family: Counter() for family in FAMILIES
        }
        seen_judges: set[str] = set()
        baseline_scores: list[float] = []
        candidate_scores: list[float] = []

        for run in runs:
            if not isinstance(run, dict):
                raise GateError(f"{case_id}: judge run must be an object")
            judge_id = run.get("judge_id")
            family = run.get("family")
            baseline_label = run.get("baseline_label")
            report_value = run.get("report")
            if (
                not isinstance(judge_id, str)
                or not judge_id
                or judge_id in seen_judges
            ):
                raise GateError(f"{case_id}: judge_id must be unique and non-empty")
            seen_judges.add(judge_id)
            if family not in FAMILIES:
                raise GateError(f"{case_id}: unsupported judge family {family!r}")
            if baseline_label not in {"A", "B"}:
                raise GateError(f"{case_id}: baseline_label must be A or B")
            if not isinstance(report_value, str) or not report_value:
                raise GateError(f"{case_id}: report path is required")
            report_path = (root / report_value).resolve()
            if not report_path.is_relative_to(root) or not report_path.is_file():
                raise GateError(f"{case_id}: report is missing or escapes the root")
            report_sha = run.get("report_sha256")
            if not isinstance(report_sha, str) or _sha256(report_path) != report_sha:
                raise GateError(f"{case_id}: judge report digest changed")
            report = _load_object(report_path)
            if report.get("case_id") != case_id or report.get("judge_id") != judge_id:
                raise GateError(f"{report_path}: report identity does not match manifest")
            if report.get("family") != family:
                raise GateError(f"{report_path}: report family does not match manifest")
            artifact_shas = report.get("artifact_sha256")
            scores = report.get("scores")
            evidence = report.get("evidence")
            if not isinstance(artifact_shas, dict) or set(artifact_shas) != {"A", "B"}:
                raise GateError(f"{report_path}: artifact_sha256 must contain A and B")
            candidate_label = "B" if baseline_label == "A" else "A"
            if artifact_shas.get(baseline_label) != baseline_sha:
                raise GateError(f"{report_path}: baseline label digest mismatch")
            if artifact_shas.get(candidate_label) != candidate_sha:
                raise GateError(f"{report_path}: candidate label digest mismatch")
            if not isinstance(scores, dict) or set(scores) != {"A", "B"}:
                raise GateError(f"{report_path}: scores must contain A and B")
            if not isinstance(evidence, dict) or set(evidence) != {"A", "B"}:
                raise GateError(f"{report_path}: evidence must contain A and B")
            for label in ("A", "B"):
                per_dimension = evidence[label]
                if (
                    not isinstance(per_dimension, dict)
                    or set(per_dimension) != set(DIMENSIONS)
                    or not all(isinstance(text, str) and text.strip() for text in per_dimension.values())
                ):
                    raise GateError(
                        f"{report_path}: {label} needs evidence for every dimension"
                    )
            total_a = _validated_scores(scores["A"], report=report_path, label="A")
            total_b = _validated_scores(scores["B"], report=report_path, label="B")
            preference = report.get("preference")
            expected_preference = (
                "TIE"
                if abs(total_a - total_b) < 1
                else ("A" if total_a > total_b else "B")
            )
            if preference != expected_preference:
                raise GateError(f"{report_path}: preference conflicts with total scores")

            family_counts[family] += 1
            family_positions[family][baseline_label] += 1
            baseline_scores.append(total_a if baseline_label == "A" else total_b)
            candidate_scores.append(total_b if baseline_label == "A" else total_a)

        if family_counts != Counter({family: 2 for family in FAMILIES}):
            raise GateError(f"{case_id}: each judge family must run exactly twice")
        if any(positions != Counter({"A": 1, "B": 1}) for positions in family_positions.values()):
            raise GateError(f"{case_id}: each family must swap baseline A/B position")

        baseline_mean = sum(baseline_scores) / len(baseline_scores)
        candidate_mean = sum(candidate_scores) / len(candidate_scores)
        raw_score_change = (candidate_mean - baseline_mean) / baseline_mean
        baseline_gap = 100.0 - baseline_mean
        gap_reduction = (
            (candidate_mean - baseline_mean) / baseline_gap if baseline_gap > 0 else 0.0
        )
        case_results.append(
            {
                "case_id": case_id,
                "baseline_mean": round(baseline_mean, 4),
                "candidate_mean": round(candidate_mean, 4),
                "raw_relative_score_change": round(raw_score_change, 6),
                "quality_gap_reduction": round(gap_reduction, 6),
                "non_regression": candidate_mean >= baseline_mean,
            }
        )

    baseline_macro = sum(item["baseline_mean"] for item in case_results) / len(case_results)
    candidate_macro = sum(item["candidate_mean"] for item in case_results) / len(case_results)
    raw_score_change_macro = (candidate_macro - baseline_macro) / baseline_macro
    baseline_gap_macro = 100.0 - baseline_macro
    gap_reduction_macro = (
        (candidate_macro - baseline_macro) / baseline_gap_macro
        if baseline_gap_macro > 0
        else 0.0
    )
    passed = gap_reduction_macro >= TARGET_GAP_REDUCTION and all(
        item["non_regression"] for item in case_results
    )
    return {
        "passed": passed,
        "target_quality_gap_reduction": TARGET_GAP_REDUCTION,
        "baseline_macro_mean": round(baseline_macro, 4),
        "candidate_macro_mean": round(candidate_macro, 4),
        "raw_relative_score_change": round(raw_score_change_macro, 6),
        "quality_gap_reduction": round(gap_reduction_macro, 6),
        "cases": case_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(args.manifest)
    except (GateError, FileNotFoundError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
