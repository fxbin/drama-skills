import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama/scripts/project_tool.py"
SPEC = importlib.util.spec_from_file_location("short_drama_project_tool", SCRIPT)
assert SPEC and SPEC.loader
project_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_tool)


class ProjectToolTests(unittest.TestCase):
    def test_windows_directory_sync_avoids_unsupported_directory_fsync(self) -> None:
        # Built outside the patch: on Python 3.11 pathlib reads os.name while
        # constructing, so an "nt" patch would demand an unusable WindowsPath.
        target = Path("unused-on-windows")
        with patch.object(project_tool.os, "name", "nt"), patch.object(
            project_tool.os, "open"
        ) as open_mock:
            project_tool._fsync_directory(target)
        open_mock.assert_not_called()

    def test_windows_transaction_lock_acquires_and_releases_on_error(self) -> None:
        events: list[tuple[int, int, int]] = []
        locking = types.SimpleNamespace(
            LK_LOCK=1,
            LK_UNLCK=2,
            locking=lambda descriptor, mode, length: events.append(
                (descriptor, mode, length)
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.object(project_tool.os, "name", "nt"), patch.object(
                project_tool.importlib,
                "import_module",
                return_value=locking,
            ) as importer:
                with self.assertRaisesRegex(RuntimeError, "injected"):
                    with project_tool._transaction_lock(root):
                        raise RuntimeError("injected")

        importer.assert_called_once_with("msvcrt")
        self.assertEqual([mode for _, mode, _ in events], [1, 2])
        self.assertEqual([length for _, _, length in events], [1, 1])

    def test_initializes_minimal_project_without_creative_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "项目 空格"
            result = project_tool.initialize_project(
                root,
                title="复检记录",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SUITE / "skills/short-drama",
            )

            self.assertEqual(result["project"]["title"], "复检记录")
            self.assertTrue((root / "short-drama.json").is_file())
            self.assertTrue((root / ".short-drama/state.json").is_file())
            self.assertFalse((root / "episodes/EP001/screenplay.md").exists())
            self.assertEqual(project_tool.find_project(root / "episodes"), root.resolve())

    def test_rerun_never_overwrites_existing_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            project_tool.initialize_project(
                root,
                title="原题",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SUITE / "skills/short-drama",
            )
            before = (root / "short-drama.json").read_bytes()

            with self.assertRaises(FileExistsError):
                project_tool.initialize_project(
                    root,
                    title="覆盖题",
                    language="en-US",
                    aspect_ratio="16:9",
                    suite_root=SUITE / "skills/short-drama",
                )

            self.assertEqual((root / "short-drama.json").read_bytes(), before)

    def test_status_exposes_summary_not_creative_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            project_tool.initialize_project(
                root,
                title="档案室",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SUITE / "skills/short-drama",
            )
            state_path = root / ".short-drama/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["artifacts"] = {
                "screenplay": {"build_state": "materialized", "hash": "secret-hash"}
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")

            status = project_tool.project_status(root)

            self.assertEqual(status["artifact_build_states"], {"materialized": 1})
            self.assertNotIn("hash", status)

    def test_lifecycle_axes_are_independent_and_strictly_validated(self) -> None:
        axes = project_tool.default_lifecycle()
        self.assertEqual(
            set(axes),
            {
                "build_state",
                "validation_state",
                "creator_acceptance",
                "independent_review",
                "delivery_gate",
            },
        )

        updated = project_tool.apply_lifecycle_changes(
            axes,
            {"creator_acceptance": "accepted"},
        )
        self.assertEqual(updated["creator_acceptance"], "accepted")
        self.assertEqual(updated["build_state"], "absent")
        with self.assertRaises(ValueError):
            project_tool.apply_lifecycle_changes(axes, {"accepted": True})
        with self.assertRaises(ValueError):
            project_tool.apply_lifecycle_changes(
                axes,
                {"delivery_gate": "accepted"},
            )

    def test_independent_reviewer_requires_fresh_context_provenance(self) -> None:
        reviewer = {
            "owner": "short-drama-review",
            "kind": "independent_agent",
            "independent": True,
            "excluded_owner_skills": ["short-drama-write"],
        }
        with self.assertRaisesRegex(ValueError, "fresh-context provenance"):
            project_tool._normalize_reviewer_evidence(
                reviewer,
                verdict_owner="short-drama-review",
                artifact_owner="short-drama-write",
            )

        reviewer["provenance"] = {
            "context_id": "fresh-review-test",
            "fresh_context": True,
            "authored_reviewed_artifacts": False,
        }
        normalized = project_tool._normalize_reviewer_evidence(
            reviewer,
            verdict_owner="short-drama-review",
            artifact_owner="short-drama-write",
        )
        self.assertTrue(normalized["provenance"]["fresh_context"])

        provisional = project_tool._normalize_reviewer_evidence(
            {
                "owner": "short-drama-review",
                "kind": "unattested",
                "independent": False,
                "excluded_owner_skills": ["short-drama-write"],
                "provenance": None,
            },
            verdict_owner="short-drama-review",
            artifact_owner="short-drama-write",
            require_independent=False,
        )
        self.assertFalse(provisional["independent"])
        self.assertIsNone(provisional["provenance"])

    def test_status_summarizes_all_axes_and_recovery_without_hashes_or_text(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            project_tool.initialize_project(
                root,
                title="夜班审计",
                language="zh-CN",
                aspect_ratio="9:16",
                suite_root=SUITE / "skills/short-drama",
            )
            screenplay = root / "episodes/EP001/screenplay.md"
            screenplay.parent.mkdir(parents=True)
            screenplay.write_text("# 第一集\n", encoding="utf-8")
            digest = project_tool.sha256_file(screenplay)
            state_path = root / ".short-drama/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["artifacts"] = {
                "screenplay": {
                    **project_tool.default_lifecycle(),
                    "build_state": "materialized",
                    "creator_acceptance": "accepted",
                    "creative_text": "不得出现在状态摘要里的台词",
                    "accepted_targets": {
                        "episodes/EP001/screenplay.md": digest
                    },
                }
            }
            project_tool.atomic_json(state_path, state)

            status = project_tool.project_status(root)

            self.assertEqual(status["artifact_build_states"], {"materialized": 1})
            self.assertEqual(
                status["lifecycle"]["creator_acceptance"], {"accepted": 1}
            )
            serialized = json.dumps(status, ensure_ascii=False)
            self.assertNotIn("台词", serialized)
            self.assertNotIn(digest, serialized)


if __name__ == "__main__":
    unittest.main()
