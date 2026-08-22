from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from evaluations.content_quality_gate import DIMENSIONS, GateError, evaluate


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distributed_score(total: int) -> dict[str, int]:
    result: dict[str, int] = {}
    remaining = total
    for dimension, maximum in DIMENSIONS.items():
        score = min(maximum, remaining)
        result[dimension] = score
        remaining -= score
    if remaining:
        raise ValueError(total)
    return result


class ContentQualityGateTests(unittest.TestCase):
    def build_manifest(self, root: Path, *, candidate_total: int = 70) -> Path:
        cases = []
        for case_index in range(2):
            case_id = f"case-{case_index + 1}"
            baseline = root / f"{case_id}-baseline.md"
            candidate = root / f"{case_id}-candidate.md"
            baseline.write_text(f"baseline {case_id}\n", encoding="utf-8")
            candidate.write_text(f"candidate {case_id}\n", encoding="utf-8")
            runs = []
            for family in ("codex", "kimi"):
                for position in ("A", "B"):
                    judge_id = f"{case_id}-{family}-{position}"
                    candidate_label = "B" if position == "A" else "A"
                    scores = {
                        position: distributed_score(50),
                        candidate_label: distributed_score(candidate_total),
                    }
                    report = {
                        "case_id": case_id,
                        "judge_id": judge_id,
                        "family": family,
                        "artifact_sha256": {
                            position: digest(baseline),
                            candidate_label: digest(candidate),
                        },
                        "scores": scores,
                        "evidence": {
                            "A": {dimension: "specific evidence" for dimension in DIMENSIONS},
                            "B": {dimension: "specific evidence" for dimension in DIMENSIONS},
                        },
                        "preference": candidate_label,
                    }
                    report_path = root / f"{judge_id}.json"
                    report_path.write_text(
                        json.dumps(report, ensure_ascii=False), encoding="utf-8"
                    )
                    runs.append(
                        {
                            "judge_id": judge_id,
                            "family": family,
                            "baseline_label": position,
                            "report": report_path.name,
                            "report_sha256": digest(report_path),
                        }
                    )
            cases.append(
                {
                    "case_id": case_id,
                    "baseline_artifact": baseline.name,
                    "baseline_sha256": digest(baseline),
                    "candidate_artifact": candidate.name,
                    "candidate_sha256": digest(candidate),
                    "judge_runs": runs,
                }
            )
        manifest = root / "manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "target_quality_gap_reduction": 0.30,
                    "cases": cases,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return manifest

    def test_balanced_two_case_evidence_passes_at_thirty_percent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate(self.build_manifest(Path(directory)))
        self.assertTrue(result["passed"])
        self.assertEqual(result["quality_gap_reduction"], 0.4)

    def test_macro_improvement_below_target_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate(
                self.build_manifest(Path(directory), candidate_total=64)
            )
        self.assertFalse(result["passed"])
        self.assertEqual(result["quality_gap_reduction"], 0.28)

    def test_target_measures_closed_quality_gap_not_impossible_raw_uplift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = self.build_manifest(root, candidate_total=86)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for case in manifest["cases"]:
                for run in case["judge_runs"]:
                    report_path = root / run["report"]
                    report = json.loads(report_path.read_text(encoding="utf-8"))
                    baseline_label = run["baseline_label"]
                    report["scores"][baseline_label] = distributed_score(80)
                    report_path.write_text(json.dumps(report), encoding="utf-8")
                    run["report_sha256"] = digest(report_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = evaluate(manifest_path)
        self.assertTrue(result["passed"])
        self.assertEqual(result["raw_relative_score_change"], 0.075)
        self.assertEqual(result["quality_gap_reduction"], 0.3)

    def test_unbalanced_model_positions_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = self.build_manifest(Path(directory))
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["cases"][0]["judge_runs"][1]["baseline_label"] = "A"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(GateError, "baseline label digest mismatch"):
                evaluate(manifest_path)


if __name__ == "__main__":
    unittest.main()
