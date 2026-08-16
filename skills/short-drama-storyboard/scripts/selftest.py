#!/usr/bin/env python3
"""Offline self-test for storyboard bookkeeping checks."""

from __future__ import annotations

import copy
import sys

from storyboard_check import check_episode_duration, check_keyframe_boundaries

MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.10 or newer")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


SHOT = {
    "shot_id": "SHOT-001",
    "duration_seconds": 5,
    "start_boundary": "closed door",
    "end_boundary": "open door",
}
COVERAGE = {
    "dispositions": [{"shot_refs": [{"record_id": "SHOT-001"}]}],
    "episode_duration": {
        "counted_shot_ids": ["SHOT-001"],
        "unresolved_durations": [],
        "shot_seconds_total": 5,
        "delta_seconds": 0,
        "disposition": "within_creator_tolerance",
    },
}
KEYFRAME = {
    "keyframe_id": "KF-001-END",
    "boundary_role": "end",
    "boundary_ref": {"record_id": "SHOT-001", "field": "/end_boundary"},
}


def main() -> int:
    require(check_episode_duration(COVERAGE, [SHOT], 5) == [], "valid duration")
    require(check_keyframe_boundaries([KEYFRAME], [SHOT]) == [], "valid boundary")

    wrong_total = copy.deepcopy(COVERAGE)
    wrong_total["episode_duration"]["shot_seconds_total"] = 4
    require(
        any(
            item["code"] == "SHT16_TOTAL_IS_NOT_THE_SUM"
            for item in check_episode_duration(wrong_total, [SHOT], 5)
        ),
        "wrong duration total was not detected",
    )

    wrong_boundary = copy.deepcopy(KEYFRAME)
    wrong_boundary["boundary_ref"]["field"] = "/start_boundary"
    require(
        any(
            item["code"] == "SHT17_BOUNDARY_REF_DISAGREES_WITH_ROLE"
            for item in check_keyframe_boundaries([wrong_boundary], [SHOT])
        ),
        "wrong keyframe boundary was not detected",
    )

    print("4 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
