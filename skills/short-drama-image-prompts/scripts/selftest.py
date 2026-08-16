#!/usr/bin/env python3
"""Offline self-test for the standalone image-prompt checker."""

from __future__ import annotations

import copy
import sys

from image_prompt_check import SKILL_ROOT, ValidationError, load_jsonl, validate_records

MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.10 or newer")


def fail(records: list[dict], marker: str) -> None:
    try:
        validate_records(records)
    except ValidationError as exc:
        assert marker in str(exc), (marker, str(exc))
    else:
        raise AssertionError(f"expected failure containing {marker!r}")


def main() -> int:
    records = load_jsonl(SKILL_ROOT / "examples/minimal-image-prompt-specs.jsonl")
    assert validate_records(records)["specs"] == 1

    duplicate = [records[0], copy.deepcopy(records[0])]
    fail(duplicate, "duplicate spec_id")

    bad_order = copy.deepcopy(records)
    bad_order[0]["reference_bindings"].append(copy.deepcopy(bad_order[0]["reference_bindings"][0]))
    fail(bad_order, "duplicate slot_id")

    leaked = copy.deepcopy(records)
    leaked[0]["provider"] = "example"
    fail(leaked, "provider execution fields")

    print("4 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
