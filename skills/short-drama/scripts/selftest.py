#!/usr/bin/env python3
"""Offline self-test for the standalone project lifecycle."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

from project_tool import initialize_project, project_status, publish_candidate

MINIMUM_PYTHON = (3, 10)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit("selftest.py requires Python 3.10 or newer")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "project"
        created = initialize_project(
            root,
            title="Self-test",
            language="zh-CN",
            prompt_language="en",
            aspect_ratio="9:16",
        )
        require(created["project"]["title"] == "Self-test", "project title")
        require(
            project_status(root)["project_id"] == created["project"]["project_id"],
            "project discovery",
        )

        published = publish_candidate(
            root,
            owner="selftest",
            artifact_id="SELFTEST-001",
            outputs={"剧集/EP001/screenplay.md": "# EP001\n"},
        )
        require(published["state"] == "needs_confirmation", "publication state")

        try:
            publish_candidate(
                root,
                owner="selftest",
                artifact_id="SELFTEST-UNSAFE",
                outputs={"../escape.md": "unsafe"},
            )
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe publication path was accepted")

    print("4 self-tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
