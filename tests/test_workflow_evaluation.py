"""The main-workflow evaluation: one real novel, run end to end, checked here.

`examples/golden-project` is a curated sample -- small, hand-shaped, and useful
for showing what a finished project looks like. It cannot tell us whether the
suite still works on a real book, because nothing in it came from one. Three
defects shipped past it: a duration estimate that timed voice-over at zero, a
voice sheet that could not hold a voice-over line at all, and a rebuild path
that renumbered blocks in silence. None of those are visible in a fixture with
no voice-over, no full-length source and no revision history.

`evaluations/让你管账号/reference-run` is the other kind of fixture: the recorded
output of the documented workflow, run against a 147 KB novel, carrying the
things the curated sample happens not to have -- `[VO]` and `[OS]` lines, a
complete voice sheet, a 20-chapter source index, and a screenplay that has been
revised once. This module holds it to the same bar every release.

It is a regression gate, not a quality judgement: it asserts that the checkers
still pass and that the derived layers still reproduce from their sources. What
the episode is worth as drama is a creative review, and the procedure for that
is in the directory's README.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"
EVAL = SUITE / "evaluations/让你管账号"
RUN = EVAL / "reference-run"
NOVEL = RUN / "输入/长篇-让你管账号，你高燃混剪炸全网.txt"
EPISODE = RUN / "剧集/EP001"


def script(relative: str) -> Path:
    return SKILLS / relative


def run_json(args: list[str]) -> dict[str, Any]:
    """Run a checker exactly as a creator would, and read its report."""
    completed = subprocess.run(
        [sys.executable, *args],
        capture_output=True,
        text=True,
        cwd=RUN,
    )
    payload = completed.stdout.strip() or completed.stderr.strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError:  # pragma: no cover - only on a broken checker
        raise AssertionError(f"{args[0]} did not print a JSON report:\n{payload}")


def records(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class SourceMaterialTests(unittest.TestCase):
    def test_the_novel_is_present_and_whole(self) -> None:
        self.assertTrue(NOVEL.is_file(), "the evaluation input is missing")
        data = NOVEL.read_bytes()
        self.assertEqual(len(data), 147010, "the evaluation input changed size")

    def test_the_chapter_index_still_reproduces_from_the_novel(self) -> None:
        """S0 is the single slicing truth; a drifting index moves every stage."""

        recorded = json.loads(
            (RUN / "项目开发/source-analysis/_index.json").read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            rebuilt_path = Path(directory) / "index.json"
            report = run_json(
                [
                    str(script("short-drama-novel-analyze/scripts/novel_index.py")),
                    "index",
                    str(NOVEL),
                    "--out",
                    str(rebuilt_path),
                ]
            )
            rebuilt = json.loads(rebuilt_path.read_text(encoding="utf-8"))

        self.assertEqual(report["problems"], [])
        self.assertEqual(report["chapter_count"], 20)
        self.assertEqual(
            [chapter["sequence"] for chapter in rebuilt["chapters"]],
            [chapter["sequence"] for chapter in recorded["chapters"]],
        )
        self.assertEqual(
            [chapter["line_start"] for chapter in rebuilt["chapters"]],
            [chapter["line_start"] for chapter in recorded["chapters"]],
        )


class CheckerSweepTests(unittest.TestCase):
    """Every checker the documented workflow runs, over the recorded output."""

    def test_asset_bible_passes(self) -> None:
        report = run_json(
            [
                str(script("short-drama-assets/scripts/asset_check.py")),
                "--characters",
                "设定集/characters.jsonl",
                "--looks",
                "设定集/looks.jsonl",
            ]
        )
        self.assertEqual(report["status"], "valid")

    def test_image_prompt_specs_pass(self) -> None:
        report = run_json(
            [
                str(script("short-drama-image-prompts/scripts/image_prompt_check.py")),
                "剧集/EP001/assets/image-prompt-specs.jsonl",
            ]
        )
        self.assertEqual(report["status"], "valid")

    def test_storyboard_covers_every_block(self) -> None:
        report = run_json(
            [
                str(script("short-drama-storyboard/scripts/storyboard_check.py")),
                "剧集/EP001/storyboard/coverage.json",
                "--shots",
                "剧集/EP001/storyboard/shots.jsonl",
                "--keyframes",
                "剧集/EP001/storyboard/keyframes.jsonl",
                "--screenplay-index",
                "剧集/EP001/screenplay-index.jsonl",
                "--project",
                "short-drama.json",
            ]
        )
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["status"], "pass")

    def test_delivery_containers_pack_the_whole_episode(self) -> None:
        report = run_json(
            [
                str(script("short-drama-video-prompts/scripts/container_check.py")),
                "剧集/EP001/storyboard/containers.jsonl",
                "--shots",
                "剧集/EP001/storyboard/shots.jsonl",
            ]
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["loose_shots"], [])

    def test_motion_timing_passes(self) -> None:
        report = run_json(
            [
                str(script("short-drama-video-prompts/scripts/motion_timing_check.py")),
                "剧集/EP001/storyboard/motion-specs.jsonl",
                "--shots",
                "剧集/EP001/storyboard/shots.jsonl",
            ]
        )
        self.assertEqual(report["status"], "pass")

    def test_music_specs_pass(self) -> None:
        report = run_json(
            [
                str(script("short-drama-video-prompts/scripts/music_spec_check.py")),
                "剧集/EP001/storyboard/music-specs.jsonl",
            ]
        )
        self.assertEqual(report["status"], "valid")


class VoiceOverCoverageTests(unittest.TestCase):
    """The coverage the curated sample does not have.

    `examples/golden-project` carries no `[VO]` or `[OS]` line in any of its
    eight episodes and no voice sheet at all, so two defects lived there without
    a failing test: voice-over timed at zero seconds, and a voice sheet that
    could not project a voice-over block. This episode carries eight of them.
    """

    def test_the_episode_actually_exercises_voice_over(self) -> None:
        blocks = [
            record
            for record in records(EPISODE / "screenplay-index.jsonl")
            if record.get("record_type") == "block"
        ]
        voiced = [b for b in blocks if b.get("tag") in {"VO", "OS"}]
        self.assertGreaterEqual(
            len(voiced), 5, "the evaluation stopped covering the voice-over path"
        )
        for block in voiced:
            self.assertTrue(
                block.get("speaker"),
                "a voice tag must name its speaker; the index enforces that grammar",
            )

    def test_voice_over_is_timed_as_speech(self) -> None:
        report = run_json(
            [
                str(script("short-drama-write/scripts/duration_estimate.py")),
                "剧集/EP001/screenplay.md",
                "--project",
                "short-drama.json",
            ]
        )
        self.assertIsNotNone(report["seconds"])
        self.assertLessEqual(
            abs(report["delta_ratio"]),
            0.15,
            "the episode left the declared tolerance; a voice-over regression "
            "shows up here first, as a large negative delta",
        )

    def test_the_voice_sheet_covers_every_spoken_line(self) -> None:
        report = run_json(
            [
                str(script("short-drama-write/scripts/voice_sheet_check.py")),
                "剧集/EP001/voice-sheet.jsonl",
                "--index",
                "剧集/EP001/screenplay-index.jsonl",
                "--screenplay",
                "剧集/EP001/screenplay.md",
            ]
        )
        self.assertEqual(report["status"], "pass")
        self.assertEqual(
            report["uncovered_dialogue_blocks"],
            [],
            "the recording list is missing spoken lines",
        )
        self.assertEqual(report["lines"], report["dialogue_blocks"])


class DerivedLayerTests(unittest.TestCase):
    def test_the_screenplay_index_reproduces_from_the_screenplay(self) -> None:
        """Rebuilt against itself, every block keeps its ID and its bytes."""

        screenplay = EPISODE / "screenplay.md"
        recorded = EPISODE / "screenplay-index.jsonl"
        speakers: set[str] = {
            record["speaker"]
            for record in records(recorded)
            if record.get("record_type") == "block" and record.get("speaker")
        }
        with tempfile.TemporaryDirectory() as directory:
            rebuilt = Path(directory) / "screenplay-index.jsonl"
            args = [
                str(script("short-drama-write/scripts/screenplay_index.py")),
                str(screenplay),
                "--output",
                str(rebuilt),
                "--source-ref",
                "剧集/EP001/screenplay.md",
                "--previous-index",
                str(recorded),
                "--previous-source",
                str(screenplay),
            ]
            for speaker in sorted(speakers):
                args += ["--speaker", speaker]
            report = run_json(args)
            rebuilt_blocks = [
                record
                for record in records(rebuilt)
                if record.get("record_type") == "block"
            ]

        self.assertEqual(report["review_status"], "clean")
        recorded_blocks = [
            record
            for record in records(recorded)
            if record.get("record_type") == "block"
        ]
        self.assertEqual(
            [block["block_id"] for block in rebuilt_blocks],
            [block["block_id"] for block in recorded_blocks],
            "an unchanged screenplay produced different block IDs",
        )
        for block in rebuilt_blocks:
            self.assertEqual(block["mapping"]["status"], "reused")

    def test_every_artifact_is_accepted(self) -> None:
        """A reference run ships in the state a creator would hand downstream."""

        report = run_json(
            [str(script("short-drama/scripts/project_tool.py")), "status", "."]
        )
        self.assertEqual(
            {state for state in report["artifacts"].values()},
            {"accepted"},
            f"artifact states: {report['artifact_states']}",
        )


if __name__ == "__main__":
    unittest.main()
