#!/usr/bin/env python3
"""Estimate how long a screenplay runs, using the project's own declared rates.

This reports a number; it never judges one. The suite carries no cross-project
speech rate and no tolerance band, because a 90-second episode of dense argument
and a 90-second episode of silent work do not convert at the same ratio. The
creator declares the two rates their project actually uses, and this script
applies them.

Without declared rates the script still counts dialogue characters and action
paragraphs -- those counts are facts about the text -- and says the seconds
cannot be derived yet. That is the honest output, not a guess from a default.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


# Creators run these scripts on whatever interpreter their machine provides, so
# an unsupported version must say so instead of failing inside an import.
MINIMUM_PYTHON = (3, 9)
if sys.version_info < MINIMUM_PYTHON:
    raise SystemExit(
        "short-drama needs Python {}.{} or newer; this interpreter is {}.{}".format(
            *MINIMUM_PYTHON, sys.version_info.major, sys.version_info.minor
        )
    )


# Most production tags carry no performed duration: they are instructions to a
# later stage, not something an actor speaks or does on screen.
TAG_LINE = re.compile(r"^\[[^\]]+\]")
# [VO] and [OS] are the exception. The format contract writes them as
# ``[VO] 角色：台词`` -- a real line, delivered off-camera. Timing them at zero
# silently shortens every episode that carries its interiority in voice-over,
# and the estimate reads as a deficit the writer then pads to fill.
VOICE_TAG_LINE = re.compile(r"^\[(?:VO|OS)\]\s*(?P<body>.+)$")
SCENE_HEADING = re.compile(r"^#{1,6}\s")
# ``角色（提示）：台词`` -- the speaker label may carry a parenthesised direction.
# Only the spoken half is timed; the direction is a note to the performer.
DIALOGUE = re.compile(r"^(?P<who>[^：:（(\[\]]{1,24})(?:（[^）]*）|\([^)]*\))?[：:](?P<line>.+)$")


def _spoken_characters(line: str) -> int:
    """Count what is actually voiced: no whitespace, no bracketed directions."""
    stripped = re.sub(r"（[^）]*）|\([^)]*\)", "", line)
    return len(re.sub(r"\s", "", stripped))


def measure(screenplay: str) -> dict[str, Any]:
    """Count the timed material in a screenplay without converting to seconds."""
    dialogue_lines = 0
    dialogue_characters = 0
    action_paragraphs = 0
    tag_lines = 0

    for raw in screenplay.splitlines():
        line = raw.strip()
        if not line or SCENE_HEADING.match(line):
            continue
        voiced = VOICE_TAG_LINE.match(line)
        if voiced:
            # A voice tag still has to name its speaker with a full-width colon;
            # the index enforces that grammar. One that does not is a tag, not a
            # line, and is timed as such rather than guessed at.
            spoken = DIALOGUE.match(voiced.group("body"))
            if spoken:
                dialogue_lines += 1
                dialogue_characters += _spoken_characters(spoken.group("line"))
                continue
            tag_lines += 1
            continue
        if TAG_LINE.match(line):
            tag_lines += 1
            continue
        spoken = DIALOGUE.match(line)
        if spoken:
            dialogue_lines += 1
            dialogue_characters += _spoken_characters(spoken.group("line"))
            continue
        action_paragraphs += 1

    return {
        "dialogue_lines": dialogue_lines,
        "dialogue_characters": dialogue_characters,
        "action_paragraphs": action_paragraphs,
        "production_tag_lines": tag_lines,
    }


def declared_rates(project: dict[str, Any] | None) -> dict[str, Any]:
    """Read the project's own pacing rates, or report that it declared none."""
    pacing = ((project or {}).get("format") or {}).get("pacing") or {}
    per_second = pacing.get("spoken_characters_per_second")
    per_action = pacing.get("seconds_per_action_paragraph")
    usable = isinstance(per_second, (int, float)) and per_second > 0 and (
        isinstance(per_action, (int, float)) and per_action >= 0
    )
    return {
        "declared": bool(usable),
        "spoken_characters_per_second": per_second if usable else None,
        "seconds_per_action_paragraph": per_action if usable else None,
    }


def estimate(screenplay: str, project: dict[str, Any] | None = None) -> dict[str, Any]:
    counts = measure(screenplay)
    rates = declared_rates(project)
    target = ((project or {}).get("format") or {}).get("target_seconds_per_episode")

    result: dict[str, Any] = {"counts": counts, "rates": rates, "seconds": None}
    result["target_seconds"] = target if isinstance(target, (int, float)) else None

    if not rates["declared"]:
        result["note"] = (
            "the project declares no format.pacing rates, so seconds cannot be "
            "derived; the counts above are still exact"
        )
        return result

    seconds = (
        counts["dialogue_characters"] / rates["spoken_characters_per_second"]
        + counts["action_paragraphs"] * rates["seconds_per_action_paragraph"]
    )
    result["seconds"] = round(seconds, 1)
    if result["target_seconds"]:
        delta = seconds - result["target_seconds"]
        result["delta_seconds"] = round(delta, 1)
        result["delta_ratio"] = round(delta / result["target_seconds"], 3)
        result["note"] = (
            "informational only: the suite sets no tolerance band, because the "
            "right spread depends on the project's own scenes"
        )
    else:
        result["note"] = (
            "no format.target_seconds_per_episode is declared, so there is "
            "nothing to compare the estimate against"
        )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Estimate screenplay duration from the project's declared rates."
    )
    parser.add_argument("screenplay", type=Path)
    parser.add_argument(
        "--project",
        type=Path,
        default=None,
        help="short-drama.json carrying format.pacing and target_seconds_per_episode",
    )
    args = parser.parse_args(argv)

    if not args.screenplay.is_file():
        raise SystemExit("screenplay not found: {}".format(args.screenplay))

    project = None
    if args.project is not None:
        if not args.project.is_file():
            raise SystemExit("project file not found: {}".format(args.project))
        project = json.loads(args.project.read_text(encoding="utf-8"))

    report = estimate(args.screenplay.read_text(encoding="utf-8"), project)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    # An estimate is never a verdict, so this exits successfully even when the
    # episode lands far from its target. Blocking here would turn a reported
    # number into the cross-project threshold this suite refuses to carry.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
