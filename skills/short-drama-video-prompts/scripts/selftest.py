#!/usr/bin/env python3
"""Offline self-test for standalone video and music prompt tooling."""

from __future__ import annotations

import copy
import sys

from music_spec_check import SKILL_ROOT, ValidationError, load_jsonl, validate_records

MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.10 or newer")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def fail(records: list[dict], marker: str) -> None:
    try:
        validate_records(records)
    except ValidationError as exc:
        require(marker in str(exc), f"expected {marker!r}, got {exc!s}")
    else:
        raise AssertionError(f"expected failure containing {marker!r}")


def main() -> int:
    records = load_jsonl(SKILL_ROOT / "examples/minimal-music-specs.jsonl")
    require(validate_records(records)["music_specs"] == 1, "valid fixture count")

    duplicate = [records[0], copy.deepcopy(records[0])]
    fail(duplicate, "duplicate music_id")

    leaked = copy.deepcopy(records)
    leaked[0]["model"] = "example"
    fail(leaked, "provider execution fields")

    song_without_lyrics = copy.deepcopy(records)
    song_without_lyrics[0]["mode"] = "song"
    fail(song_without_lyrics, "lyrics")

    invalid_scope = copy.deepcopy(records)
    invalid_scope[0]["scope"]["end_seconds"] = 0
    fail(invalid_scope, "0 <= start < end")

    unsupported = copy.deepcopy(records)
    unsupported[0]["token"] = "not provider-neutral"
    fail(unsupported, "unsupported fields")

    print("6 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
