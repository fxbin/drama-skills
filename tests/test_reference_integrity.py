"""Semantic references must name something that is actually there.

A reference that names a real file can still point at nothing: ``field`` can
name a key the target record does not carry, ``projected_fields`` can name a
contract field that was removed, and ``source_step_pointer`` can name a causal
step that no longer exists. None of that is caught by checking that the
*artifact* exists, which is all the reference resolver does.

This is not hypothetical. Shrinking the episode map removed the single-step
``causal_escalation`` field and left eight episode cards pointing at
``/causal_escalation/0``. Every existing test stayed green; the dangling
pointers were found by reading. This module is the test that would have caught
them.

It runs over the golden project because that is the one complete, fully
resolvable project in the repository. Templates point at ``剧集/<EP>/...``
placeholders that resolve to nothing by design, so they are out of scope here.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
GOLDEN = SUITE / "examples/golden-project"

# Keys whose value is a JSON pointer into the artifact the same object (or its
# enclosing record) references.
POINTER_KEYS = ("field", "source_step_pointer", "motion_field")
POINTER_LIST_KEYS = ("projected_fields", "source_contract_fields")


def documents(path: Path) -> list[Any]:
    """Every JSON document a file carries; empty for non-JSON artifacts.

    References legitimately name Markdown targets such as ``screenplay.md``.
    Those carry no records, so a ``record_id`` against them is checked only for
    file existence.
    """
    if path.suffix not in {".json", ".jsonl"}:
        return []
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return [json.loads(text)]
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def data_records(path: Path) -> list[Any]:
    return [
        record
        for record in documents(path)
        if not (isinstance(record, dict) and record.get("record_type") == "sources")
    ]


def declared_sources(docs: list[Any]) -> dict[str, dict[str, Any]]:
    for document in docs:
        if isinstance(document, dict) and document.get("record_type") == "sources":
            sources = document.get("sources")
            if isinstance(sources, dict):
                return sources
    return {}


def resolve_reference(reference: Any, sources: dict[str, Any]) -> dict[str, Any] | None:
    """The artifact a reference names, in either the compact or expanded form."""
    if not isinstance(reference, dict):
        return None
    src = reference.get("src")
    if isinstance(src, str):
        entry = sources.get(src)
        if not isinstance(entry, dict):
            return None
        merged = dict(entry)
        merged.update({k: v for k, v in reference.items() if k != "src"})
        return merged
    if isinstance(reference.get("artifact"), str):
        return dict(reference)
    return None


def record_by_id(records: list[Any], record_id: str) -> Any:
    """The record a ``record_id`` names.

    Every record type spells its own identity key -- ``prop_id``, ``shot_id``,
    ``episode_id`` and so on -- so any ``*_id`` field carrying the value
    identifies the record. Enumerating the key names instead would silently
    skip whichever type was added last.
    """
    for record in records:
        if not isinstance(record, dict):
            continue
        for key, value in record.items():
            if key.endswith("_id") and value == record_id:
                return record
    return None


def pointer_resolves(document: Any, pointer: str) -> bool:
    """RFC-6901 style traversal, enough for the pointers this suite writes."""
    if pointer in {"", "/"}:
        return True
    node = document
    for raw in pointer.lstrip("/").split("/"):
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(node, dict):
            if token not in node:
                return False
            node = node[token]
        elif isinstance(node, list):
            if not token.isdigit() or int(token) >= len(node):
                return False
            node = node[int(token)]
        else:
            return False
    return True


def iter_pointer_claims(path: Path):
    """Yield (location, target_artifact, record_id, pointer) for one file.

    A pointer is resolved against the artifact its own object references when it
    has one, and otherwise against the nearest enclosing reference -- which is
    how ``projected_fields`` and ``source_contract_fields`` are written.
    """
    docs = documents(path)
    sources = declared_sources(docs)

    def document_default(document: Any) -> dict[str, Any] | None:
        """The reference a whole document is written against, if it declares one.

        An episode card puts its contract reference under ``contract_authority``
        and its pointers under ``execution_plan`` -- siblings, not ancestors, so
        inheriting only downward would leave those pointers unchecked. That is
        exactly the shape that shipped eight dangling pointers.
        """
        if not isinstance(document, dict):
            return None
        authority = document.get("contract_authority")
        if isinstance(authority, dict):
            return resolve_reference(authority.get("source_ref"), sources)
        return None

    def walk(node: Any, cursor: str, inherited: dict[str, Any] | None) -> None:
        if isinstance(node, dict):
            here = resolve_reference(node, sources) or inherited
            for key in POINTER_KEYS:
                pointer = node.get(key)
                if isinstance(pointer, str) and here is not None:
                    yield_target(f"{cursor}/{key}", here, pointer)
            for key in POINTER_LIST_KEYS:
                values = node.get(key)
                if isinstance(values, list) and here is not None:
                    for index, pointer in enumerate(values):
                        if isinstance(pointer, str):
                            yield_target(f"{cursor}/{key}/{index}", here, pointer)
            for key, child in node.items():
                walk(child, f"{cursor}/{key}", here)
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{cursor}/{index}", inherited)

    claims: list[tuple[str, str, Any, str]] = []

    def yield_target(location: str, reference: dict[str, Any], pointer: str) -> None:
        artifact = reference.get("artifact")
        if isinstance(artifact, str):
            claims.append((location, artifact, reference.get("record_id"), pointer))

    for index, document in enumerate(docs):
        walk(document, f"#doc{index}", document_default(document))
    return claims


class ReferenceIntegrityTests(unittest.TestCase):
    def test_every_semantic_pointer_resolves_in_its_target(self) -> None:
        checked = 0
        for path in sorted(GOLDEN.rglob("*")):
            if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
                continue
            for location, artifact, record_id, pointer in iter_pointer_claims(path):
                target = GOLDEN / artifact
                where = f"{path.relative_to(GOLDEN)}:{location} -> {artifact}"
                self.assertTrue(target.is_file(), f"{where}: target file is missing")
                records = data_records(target)
                if record_id is not None and not records:
                    continue
                if record_id is not None:
                    document = record_by_id(records, str(record_id))
                    self.assertIsNotNone(document, f"{where}#{record_id}: no such record")
                elif len(records) == 1:
                    document = records[0]
                else:
                    # A pointer into a multi-record file without naming the
                    # record cannot be checked; the reference itself is the
                    # defect, and the shape tests already report it.
                    continue
                checked += 1
                self.assertTrue(
                    pointer_resolves(document, pointer),
                    f"{where}{'#' + str(record_id) if record_id else ''}: "
                    f"{pointer} names nothing in the target",
                )
        self.assertGreater(checked, 0, "no semantic pointers were checked")

    def test_every_record_id_reference_names_a_real_record(self) -> None:
        checked = 0
        for path in sorted(GOLDEN.rglob("*")):
            if not path.is_file() or path.suffix not in {".json", ".jsonl"}:
                continue
            docs = documents(path)
            sources = declared_sources(docs)

            def walk(node: Any, cursor: str) -> None:
                nonlocal checked
                if isinstance(node, dict):
                    resolved = resolve_reference(node, sources)
                    record_id = node.get("record_id")
                    if resolved and isinstance(record_id, str):
                        artifact = resolved.get("artifact")
                        if isinstance(artifact, str):
                            target = GOLDEN / artifact
                            where = f"{path.relative_to(GOLDEN)}:{cursor} -> {artifact}"
                            self.assertTrue(target.is_file(), f"{where}: missing target")
                            records = data_records(target)
                            if not records:
                                return
                            checked += 1
                            self.assertIsNotNone(
                                record_by_id(records, record_id),
                                f"{where}#{record_id}: no such record",
                            )
                    for key, child in node.items():
                        walk(child, f"{cursor}/{key}")
                elif isinstance(node, list):
                    for index, child in enumerate(node):
                        walk(child, f"{cursor}/{index}")

            for index, document in enumerate(docs):
                walk(document, f"#doc{index}")
        self.assertGreater(checked, 0, "no record references were checked")


if __name__ == "__main__":
    unittest.main()
