#!/usr/bin/env python3
"""Offline self-test for storyboard bookkeeping checks."""

from __future__ import annotations

import copy
import sys
from typing import Any

from storyboard_check import check_episode_duration, check_keyframe_boundaries

MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.10 or newer")


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

    print("9 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
