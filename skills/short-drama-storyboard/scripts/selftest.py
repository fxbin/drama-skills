#!/usr/bin/env python3
"""Offline self-test for storyboard bookkeeping checks."""

from __future__ import annotations

import copy
import sys
import tempfile
from pathlib import Path
from typing import Any

from storyboard_check import (
    check_boundary_entries,
    check_episode_duration,
    check_keyframe_boundaries,
    check_screenplay_coverage,
)

MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.9 or newer")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def codes(findings: list[dict[str, Any]]) -> set[Any]:
    return {item["code"] for item in findings}


SHOT: dict[str, Any] = {
    "shot_id": "SHOT-001",
    "duration_seconds": 5,
    "start_boundary": "closed door",
    "end_boundary": "open door",
}
BOUNDED_SHOT: dict[str, Any] = {
    "shot_id": "SHOT-002",
    "duration_seconds": 5,
    "start_boundary": {
        "positions": ["站在柜台东侧（与上一镜相同）"],
        "facing": ["面向门口"],
    },
    "end_boundary": {"positions": ["退到门内一步"], "facing": ["面向柜台"]},
}
SHOTS_SOURCE: dict[str, Any] = {
    "owner": "short-drama-storyboard",
    "artifact": "剧集/EP001/storyboard/shots.jsonl",
    "hash": "a" * 64,
}
COVERAGE: dict[str, Any] = {
    "sources": {"shots": SHOTS_SOURCE},
    "dispositions": [{"shot_refs": [{"src": "shots", "record_id": "SHOT-001"}]}],
    "episode_duration": {
        "counted_shot_ids": ["SHOT-001"],
        "unresolved_durations": [],
        "shot_seconds_total": 5,
        "delta_seconds": 0,
        "disposition": "within_creator_tolerance",
    },
}
KEYFRAME_SOURCES: dict[str, Any] = {"shots": SHOTS_SOURCE}
KEYFRAME: dict[str, Any] = {
    "keyframe_id": "KF-001-END",
    "boundary_role": "end",
    "boundary_ref": {"src": "shots", "record_id": "SHOT-001", "field": "/end_boundary"},
}
# A reference may also carry its whole snapshot inline instead of naming a
# sources key; the checker resolves both to the same upstream binding.
EXPANDED_COVERAGE: dict[str, Any] = {
    "dispositions": [
        {"shot_refs": [{**SHOTS_SOURCE, "record_id": "SHOT-001", "authority": "accepted"}]}
    ],
    "episode_duration": COVERAGE["episode_duration"],
}
EXPANDED_KEYFRAME: dict[str, Any] = {
    "keyframe_id": "KF-001-END",
    "boundary_role": "end",
    "boundary_ref": {**SHOTS_SOURCE, "record_id": "SHOT-001", "field": "/end_boundary"},
}


def test_screenplay_coverage_flags_gaps_and_double_claims() -> None:
    """Every screenplay line must be claimed by exactly one shot.

    A line no shot claims never gets filmed; a line two shots claim gets shown
    twice. Both are referential facts, so both are checked here -- whether the
    coverage is *well designed* stays with the agent.
    """
    with tempfile.TemporaryDirectory() as directory:
        screenplay = Path(directory) / "screenplay.md"
        screenplay.write_text(
            "# EP001\n\n## EP001-SC001 内 · 房间 · 日\n\n"
            "他推开门。\n\n甲：你来了。\n\n她把钥匙放下。\n\n"
            "[连续性] 钥匙留在桌上。\n",
            encoding="utf-8",
        )
        shots = [
            {"shot_id": "SH001", "source_lines": ["他推开门。"]},
            {"shot_id": "SH002", "source_lines": ["甲：你来了。"]},
            {"shot_id": "SH003", "source_lines": ["甲：你来了。"]},
            {"shot_id": "SH004", "source_lines": ["屋外下着雨。"]},
        ]
        found = {f["code"] for f in check_screenplay_coverage(shots, screenplay)}
    require("SHT21_LINE_UNCLAIMED" in found, "an unfilmed line must be reported")
    require("SHT21_LINE_CLAIMED_TWICE" in found, "a doubly claimed line must be reported")
    require(
        "SHT21_LINE_NOT_IN_SCREENPLAY" in found,
        "a shot claiming absent text must be reported",
    )


def test_screenplay_coverage_is_skipped_when_not_supplied() -> None:
    require(check_screenplay_coverage([], None) == [], "no screenplay means no claim")


def main() -> int:
    require(check_episode_duration(COVERAGE, [SHOT], 5) == [], "valid duration")
    require(
        check_keyframe_boundaries([KEYFRAME], [SHOT], KEYFRAME_SOURCES) == [],
        "valid boundary",
    )
    require(check_episode_duration(EXPANDED_COVERAGE, [SHOT], 5) == [], "expanded duration")
    require(
        check_keyframe_boundaries([EXPANDED_KEYFRAME], [SHOT], {}) == [],
        "expanded boundary",
    )

    wrong_total = copy.deepcopy(COVERAGE)
    wrong_total["episode_duration"]["shot_seconds_total"] = 4
    require(
        "SHT16_TOTAL_IS_NOT_THE_SUM" in codes(check_episode_duration(wrong_total, [SHOT], 5)),
        "wrong duration total was not detected",
    )

    wrong_boundary = copy.deepcopy(KEYFRAME)
    wrong_boundary["boundary_ref"]["field"] = "/start_boundary"
    require(
        "SHT17_BOUNDARY_REF_DISAGREES_WITH_ROLE"
        in codes(check_keyframe_boundaries([wrong_boundary], [SHOT], KEYFRAME_SOURCES)),
        "wrong keyframe boundary was not detected",
    )

    undeclared = copy.deepcopy(COVERAGE)
    undeclared["sources"] = {}
    require(
        "REF_SRC_IS_NOT_DECLARED" in codes(check_episode_duration(undeclared, [SHOT], 5)),
        "a src without a sources entry was not detected",
    )
    require(
        "REF_SRC_IS_NOT_DECLARED"
        in codes(check_keyframe_boundaries([KEYFRAME], [SHOT], {})),
        "a keyframe src without a sources entry was not detected",
    )

    unbound = copy.deepcopy(COVERAGE)
    unbound["dispositions"][0]["shot_refs"] = [{"record_id": "SHOT-001"}]
    require(
        "REF_HAS_NO_UPSTREAM_BINDING" in codes(check_episode_duration(unbound, [SHOT], 5)),
        "a reference binding no snapshot was not detected",
    )

    # A boundary entry that only says "same as before" reads as written but tells
    # the next stage nothing; an absolute fact that mentions the previous shot in
    # passing is fine and must not be flagged.
    require(check_boundary_entries([BOUNDED_SHOT]) == [], "absolute boundary entries")
    relative = copy.deepcopy(BOUNDED_SHOT)
    relative["end_boundary"]["positions"] = ["（位置不变）"]
    require(
        "SHT05_BOUNDARY_ENTRY_IS_A_BACK_REFERENCE"
        in codes(check_boundary_entries([relative])),
        "a boundary entry that only points back was not detected",
    )

    test_screenplay_coverage_flags_gaps_and_double_claims()
    test_screenplay_coverage_is_skipped_when_not_supplied()

    print("13 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
