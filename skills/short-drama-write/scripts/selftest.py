#!/usr/bin/env python3
"""Offline self-test for screenplay indexing and voice-sheet projection."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from screenplay_index import build_index
from voice_sheet_check import check

MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.10 or newer")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        screenplay = root / "screenplay.md"
        index_path = root / "screenplay-index.jsonl"
        screenplay.write_text(
            "# EP001\n\n## EP001-SC001 内 · 客厅 · 夜\n\n陈予安推开门。\n\n陈予安：我回来了。\n",
            encoding="utf-8",
        )
        summary = build_index(
            screenplay,
            index_path,
            source_ref="剧集/EP001/screenplay.md",
            speakers=["陈予安"],
        )
        require(summary["review_status"] == "clean", "valid screenplay index")
        records = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
        dialogue = next(record for record in records if record.get("kind") == "dialogue")
        sheet = [
            {
                "line_id": "LINE-001",
                "channel": "sync",
                "speaker_display": "陈予安",
                "line_text": "我回来了。",
                "source_ref": {"record_id": dialogue["block_id"]},
            }
        ]
        require(
            check(sheet, records, screenplay.read_bytes())["status"] == "pass",
            "faithful voice sheet",
        )

        changed = [dict(sheet[0], line_text="我走了。")]
        require(
            check(changed, records, screenplay.read_bytes())["status"] == "fail",
            "changed voice line was not detected",
        )

    print("3 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
