"""A shared bible is appended to constantly; its readers must not all go stale.

Whole-file binding makes every downstream artifact stale the moment a new
character is added, which on a long serial means most of the project is stale
most of the time. These tests pin the narrower contract: an artifact that
declared which records it read stays current until one of those records moves.
"""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama/scripts/project_tool.py"
SPEC = importlib.util.spec_from_file_location("short_drama_record_staleness", SCRIPT)
assert SPEC and SPEC.loader
project_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_tool)


BIBLE = "bible/characters.jsonl"
SHOTS = "episodes/EP001/storyboard/shots.jsonl"
MOTIONS = "episodes/EP001/storyboard/motion-specs.jsonl"
AUDITIONS = "episodes/EP001/storyboard/coverage-auditions/SC001.jsonl"
SCENE_PLANS = "episodes/EP001/storyboard/scene-visual-plans/SC001.jsonl"

FIRST = {"character_id": "CHAR-A", "display_name": "甲", "look": "工装"}
SECOND = {"character_id": "CHAR-B", "display_name": "乙", "look": "西装"}
THIRD = {"character_id": "CHAR-C", "display_name": "丙", "look": "校服"}


def jsonl(*records: dict[str, object]) -> str:
    return "".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        for record in records
    )


class RecordLevelStalenessTests(unittest.TestCase):
    def make_project(self, directory: str) -> Path:
        root = Path(directory) / "记录级项目"
        project_tool.initialize_project(
            root,
            title="记录级失效半径",
            language="zh-CN",
            aspect_ratio="9:16",
            suite_root=SUITE / "skills/short-drama",
        )
        return root

    def stage(self, root: Path, relative: str, text: str) -> str:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return project_tool.sha256_file(path)

    def accept(self, root: Path, artifact_id: str, targets: dict[str, str]) -> None:
        slug = artifact_id.replace(":", "-").replace("/", "-")
        relative = f"creator-decisions/{slug}.json"
        decision = root / relative
        decision.parent.mkdir(parents=True, exist_ok=True)
        decision.write_text(
            json.dumps(
                {
                    "decision_id": f"CD-{slug}",
                    "decision_kind": "artifact_acceptance",
                    "artifact_id": artifact_id,
                    "decision": "accepted",
                    "target_hashes": targets,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        project_tool.record_creator_acceptance(
            root,
            artifact_id=artifact_id,
            decision="accepted",
            target_hashes=targets,
            evidence_ref={
                "owner": "creator",
                "artifact": relative,
                "hash": project_tool.sha256_file(decision),
                "record_id": f"CD-{slug}",
            },
        )

    def publish_and_accept(
        self,
        root: Path,
        *,
        artifact_id: str,
        owner: str,
        outputs: dict[str, str],
        input_hashes: dict[str, str] | None = None,
        input_records: dict[str, list[str]] | None = None,
    ) -> dict[str, str]:
        project_tool.publish_candidate(
            root,
            owner=owner,
            artifact_id=artifact_id,
            outputs=outputs,
            input_hashes=input_hashes,
            input_records=input_records,
        )
        targets = {
            relative: project_tool.sha256_file(root / relative) for relative in outputs
        }
        self.accept(root, artifact_id, targets)
        return targets

    def bible_with_reader(
        self, root: Path, *, selectors: list[str] | None
    ) -> str:
        """Accept a two-character bible, then a reader bound to it."""

        bible_hash = self.publish_and_accept(
            root,
            artifact_id="assets:bible",
            owner="short-drama-assets",
            outputs={BIBLE: jsonl(FIRST, SECOND)},
        )[BIBLE]
        self.publish_and_accept(
            root,
            artifact_id="storyboard:EP001",
            owner="short-drama-storyboard",
            outputs={SHOTS: jsonl({"shot_id": "SHOT-001", "subject": "CHAR-A"})},
            input_hashes={BIBLE: bible_hash},
            input_records={BIBLE: selectors} if selectors else None,
        )
        return bible_hash

    def build_state(self, root: Path, artifact_id: str) -> str:
        state = json.loads((root / ".short-drama/state.json").read_text(encoding="utf-8"))
        return state["artifacts"][artifact_id]["build_state"]

    def test_unrelated_append_leaves_a_record_bound_reader_current(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.bible_with_reader(root, selectors=["CHAR-A"])
            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:bible",
                outputs={BIBLE: jsonl(FIRST, SECOND, THIRD)},
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "materialized")

    def test_whole_file_binding_still_goes_stale_on_the_same_append(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.bible_with_reader(root, selectors=None)
            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:bible",
                outputs={BIBLE: jsonl(FIRST, SECOND, THIRD)},
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "stale")

    def test_editing_a_bound_record_invalidates_its_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.bible_with_reader(root, selectors=["CHAR-A"])
            changed = {**FIRST, "look": "西装"}
            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:bible",
                outputs={BIBLE: jsonl(changed, SECOND, THIRD)},
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "stale")

    def test_removing_a_bound_record_invalidates_its_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.bible_with_reader(root, selectors=["CHAR-A"])
            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:bible",
                outputs={BIBLE: jsonl(SECOND, THIRD)},
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "stale")

    def test_a_record_that_turns_ambiguous_invalidates_its_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.bible_with_reader(root, selectors=["CHAR-A"])
            duplicate = {"character_id": "CHAR-A", "display_name": "甲の影", "look": "风衣"}
            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:bible",
                outputs={BIBLE: jsonl(FIRST, SECOND, duplicate)},
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "stale")

    def test_reordering_and_reformatting_do_not_invalidate_a_bound_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.bible_with_reader(root, selectors=["CHAR-A"])
            reordered = json.dumps(
                {"look": "工装", "display_name": "甲", "character_id": "CHAR-A"},
                ensure_ascii=False,
            )
            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:bible",
                outputs={BIBLE: jsonl(SECOND) + reordered + "\n"},
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "materialized")

    def test_delivery_closure_accepts_a_reader_whose_input_file_moved_on(self) -> None:
        """The narrowing is worthless if the closure check still demands the
        binding-time file hash, so prove the reader can still be delivered."""

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.bible_with_reader(root, selectors=["CHAR-A"])
            appended = self.publish_and_accept(
                root,
                artifact_id="assets:bible",
                owner="short-drama-assets",
                outputs={BIBLE: jsonl(FIRST, SECOND, THIRD)},
            )
            self.assertNotEqual(appended[BIBLE], project_tool.sha256_bytes(b""))
            state = json.loads(
                (root / ".short-drama/state.json").read_text(encoding="utf-8")
            )
            project_tool._validate_input_closure(root, state, "storyboard:EP001")

    def test_delivery_closure_rejects_a_reader_whose_bound_record_changed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.bible_with_reader(root, selectors=["CHAR-A"])
            self.publish_and_accept(
                root,
                artifact_id="assets:bible",
                owner="short-drama-assets",
                outputs={BIBLE: jsonl({**FIRST, "look": "睡衣"}, SECOND)},
            )
            state = json.loads(
                (root / ".short-drama/state.json").read_text(encoding="utf-8")
            )
            with self.assertRaises(ValueError) as raised:
                project_tool._validate_input_closure(root, state, "storyboard:EP001")
            self.assertIn("record hash does not match", str(raised.exception))

    def test_binding_an_ambiguous_record_id_is_refused_at_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            twin = {"character_id": "CHAR-A", "display_name": "另一个甲"}
            bible_hash = self.publish_and_accept(
                root,
                artifact_id="assets:bible",
                owner="short-drama-assets",
                outputs={BIBLE: jsonl(FIRST, twin)},
            )[BIBLE]
            with self.assertRaises(ValueError) as raised:
                project_tool.publish_candidate(
                    root,
                    owner="short-drama-storyboard",
                    artifact_id="storyboard:EP001",
                    outputs={SHOTS: jsonl({"shot_id": "SHOT-001"})},
                    input_hashes={BIBLE: bible_hash},
                    input_records={BIBLE: ["CHAR-A"]},
                )
            self.assertIn("exactly once", str(raised.exception))

    def test_binding_an_unknown_record_id_is_refused_at_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            bible_hash = self.publish_and_accept(
                root,
                artifact_id="assets:bible",
                owner="short-drama-assets",
                outputs={BIBLE: jsonl(FIRST, SECOND)},
            )[BIBLE]
            with self.assertRaises(ValueError):
                project_tool.publish_candidate(
                    root,
                    owner="short-drama-storyboard",
                    artifact_id="storyboard:EP001",
                    outputs={SHOTS: jsonl({"shot_id": "SHOT-001"})},
                    input_hashes={BIBLE: bible_hash},
                    input_records={BIBLE: ["CHAR-MISSING"]},
                )

    def test_markdown_cannot_carry_a_record_level_binding(self) -> None:
        """Markdown has no machine-checkable record identity, so narrowing it
        would be an unverifiable promise rather than a smaller radius."""

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            screenplay = "episodes/EP001/screenplay.md"
            script_hash = self.publish_and_accept(
                root,
                artifact_id="write:EP001",
                owner="short-drama-write",
                outputs={screenplay: "## SC001\n对白。\n"},
            )[screenplay]
            with self.assertRaises(ValueError) as raised:
                project_tool.publish_candidate(
                    root,
                    owner="short-drama-storyboard",
                    artifact_id="storyboard:EP001",
                    outputs={SHOTS: jsonl({"shot_id": "SHOT-001"})},
                    input_hashes={screenplay: script_hash},
                    input_records={screenplay: ["SC001"]},
                )
            self.assertIn(".json or .jsonl", str(raised.exception))

    def test_a_json_pointer_narrows_a_shared_project_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            settings = "bible/series.json"
            settings_hash = self.publish_and_accept(
                root,
                artifact_id="develop:series",
                owner="short-drama-develop",
                outputs={
                    settings: json.dumps(
                        {"production_profile": {"form": "实拍"}, "notes": "初稿"},
                        ensure_ascii=False,
                    )
                    + "\n"
                },
            )[settings]
            self.publish_and_accept(
                root,
                artifact_id="storyboard:EP001",
                owner="short-drama-storyboard",
                outputs={SHOTS: jsonl({"shot_id": "SHOT-001"})},
                input_hashes={settings: settings_hash},
                input_records={settings: ["/production_profile"]},
            )
            project_tool.publish_candidate(
                root,
                owner="short-drama-develop",
                artifact_id="develop:series",
                outputs={
                    settings: json.dumps(
                        {"production_profile": {"form": "实拍"}, "notes": "二稿"},
                        ensure_ascii=False,
                    )
                    + "\n"
                },
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "materialized")

    def test_changing_the_pointed_at_branch_invalidates_the_reader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            settings = "bible/series.json"
            settings_hash = self.publish_and_accept(
                root,
                artifact_id="develop:series",
                owner="short-drama-develop",
                outputs={
                    settings: json.dumps(
                        {"production_profile": {"form": "实拍"}, "notes": "初稿"},
                        ensure_ascii=False,
                    )
                    + "\n"
                },
            )[settings]
            self.publish_and_accept(
                root,
                artifact_id="storyboard:EP001",
                owner="short-drama-storyboard",
                outputs={SHOTS: jsonl({"shot_id": "SHOT-001"})},
                input_hashes={settings: settings_hash},
                input_records={settings: ["/production_profile"]},
            )
            project_tool.publish_candidate(
                root,
                owner="short-drama-develop",
                artifact_id="develop:series",
                outputs={
                    settings: json.dumps(
                        {"production_profile": {"form": "二维动态漫"}, "notes": "初稿"},
                        ensure_ascii=False,
                    )
                    + "\n"
                },
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "stale")

    def test_a_record_binding_needs_a_matching_exact_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.stage(root, BIBLE, jsonl(FIRST))
            with self.assertRaises(ValueError) as raised:
                project_tool.publish_candidate(
                    root,
                    owner="short-drama-storyboard",
                    artifact_id="storyboard:EP001",
                    outputs={SHOTS: jsonl({"shot_id": "SHOT-001"})},
                    input_records={BIBLE: ["CHAR-A"]},
                )
            self.assertIn("record binding needs an exact input", str(raised.exception))

    def three_level_chain(self, root: Path) -> None:
        """bible -> shots -> motions, each binding one record of its provider."""

        bible_hash = self.publish_and_accept(
            root,
            artifact_id="assets:bible",
            owner="short-drama-assets",
            outputs={BIBLE: jsonl(FIRST, SECOND)},
        )[BIBLE]
        shots_hash = self.publish_and_accept(
            root,
            artifact_id="storyboard:EP001",
            owner="short-drama-storyboard",
            outputs={SHOTS: jsonl({"shot_id": "SHOT-001", "subject": "CHAR-A"})},
            input_hashes={BIBLE: bible_hash},
            input_records={BIBLE: ["CHAR-A"]},
        )[SHOTS]
        self.publish_and_accept(
            root,
            artifact_id="video:EP001",
            owner="short-drama-video-prompts",
            outputs={
                MOTIONS: jsonl({"motion_id": "MOTION-001", "covers": "SHOT-001"})
            },
            input_hashes={SHOTS: shots_hash},
            input_records={SHOTS: ["SHOT-001"]},
        )

    def test_narrowing_carries_all_the_way_down_a_three_level_chain(self) -> None:
        """The relief is not limited to the direct consumer: a survivor's own
        targets never enter the affected set, so nothing below it is touched."""

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.three_level_chain(root)
            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:bible",
                outputs={BIBLE: jsonl(FIRST, SECOND, THIRD)},
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "materialized")
            self.assertEqual(self.build_state(root, "video:EP001"), "materialized")

    def test_a_changed_record_invalidates_the_whole_chain_below_it(self) -> None:
        """Once the direct consumer must be re-derived, its own bytes are
        suspect even though they have not moved, so its readers go stale too."""

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            self.three_level_chain(root)
            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:bible",
                outputs={BIBLE: jsonl({**FIRST, "look": "睡衣"}, SECOND)},
            )
            self.assertEqual(self.build_state(root, "storyboard:EP001"), "stale")
            self.assertEqual(self.build_state(root, "video:EP001"), "stale")

    def test_recovery_restores_the_record_binding_not_only_the_file_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            bible_hash = self.publish_and_accept(
                root,
                artifact_id="assets:bible",
                owner="short-drama-assets",
                outputs={BIBLE: jsonl(FIRST, SECOND)},
            )[BIBLE]

            def crash(point: str, _context: dict[str, object]) -> None:
                if point == "after_commit_marker":
                    raise RuntimeError("injected")

            with self.assertRaises(RuntimeError):
                project_tool.publish_candidate(
                    root,
                    owner="short-drama-storyboard",
                    artifact_id="storyboard:EP001",
                    outputs={SHOTS: jsonl({"shot_id": "SHOT-001"})},
                    input_hashes={BIBLE: bible_hash},
                    input_records={BIBLE: ["CHAR-A"]},
                    fault_injector=crash,
                )
            project_tool.recover_project(root)
            state = json.loads(
                (root / ".short-drama/state.json").read_text(encoding="utf-8")
            )
            bound = state["artifacts"]["storyboard:EP001"]["candidate_input_records"]
            self.assertEqual(list(bound), [BIBLE])
            self.assertEqual(list(bound[BIBLE]), ["CHAR-A"])

    def test_selected_scene_plan_propagates_upstream_staleness_to_motion(self) -> None:
        """A selected optional plan remains an ordinary acyclic dependency."""

        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            location_path = "bible/locations.jsonl"
            location_hash = self.publish_and_accept(
                root,
                artifact_id="assets:locations",
                owner="short-drama-assets",
                outputs={
                    location_path: jsonl(
                        {"location_id": "LOC-LOBBY", "shape": "狭长"}
                    )
                },
            )[location_path]

            audition = {
                "audition_id": "AUD-EP001-SC001",
                "approaches": [{"approach_id": "APPROACH-A"}],
            }
            project_tool.publish_candidate(
                root,
                owner="short-drama-storyboard",
                artifact_id="storyboard:EP001:audition:SC001",
                outputs={AUDITIONS: jsonl(audition)},
            )
            audition_hash = project_tool.sha256_file(root / AUDITIONS)
            selection_path = "creator-decisions/EP001-coverage-audition-SC001.json"
            selection = {
                "decision_id": "CD-EP001-COVERAGE-AUDITION-SC001",
                "decision_kind": "artifact_acceptance",
                "artifact_id": "storyboard:EP001:audition:SC001",
                "status": "accepted",
                "target_hashes": {AUDITIONS: audition_hash},
                "selected_audition_record_id": "AUD-EP001-SC001",
                "selected_approach_id": "APPROACH-A",
            }
            selection_hash = self.stage(
                root, selection_path, json.dumps(selection, ensure_ascii=False) + "\n"
            )
            project_tool.record_creator_acceptance(
                root,
                artifact_id="storyboard:EP001:audition:SC001",
                decision="accepted",
                target_hashes={AUDITIONS: audition_hash},
                evidence_ref={
                    "owner": "creator",
                    "artifact": selection_path,
                    "hash": selection_hash,
                    "record_id": selection["decision_id"],
                },
            )

            plan = {
                "plan_id": "SVP-EP001-SC001",
                "location_ref": {
                    "owner": "short-drama-assets",
                    "artifact": location_path,
                    "hash": location_hash,
                    "record_id": "LOC-LOBBY",
                },
                "source_audition_ref": {
                    "owner": "short-drama-storyboard",
                    "artifact": AUDITIONS,
                    "hash": audition_hash,
                    "record_id": "AUD-EP001-SC001",
                },
                "creator_selection_ref": {
                    "owner": "creator",
                    "artifact": selection_path,
                    "hash": selection_hash,
                    "record_id": selection["decision_id"],
                    "field": "/selected_approach_id",
                },
            }
            plan_hash = self.publish_and_accept(
                root,
                artifact_id="storyboard:EP001:scene-plan:SC001",
                owner="short-drama-storyboard",
                outputs={SCENE_PLANS: jsonl(plan)},
                input_hashes={
                    location_path: location_hash,
                    AUDITIONS: audition_hash,
                    selection_path: selection_hash,
                },
                input_records={
                    location_path: ["LOC-LOBBY"],
                    AUDITIONS: ["AUD-EP001-SC001"],
                    selection_path: ["/selected_approach_id"],
                },
            )[SCENE_PLANS]
            shots_hash = self.publish_and_accept(
                root,
                artifact_id="storyboard:EP001:shots",
                owner="short-drama-storyboard",
                outputs={
                    SHOTS: jsonl(
                        {
                            "shot_id": "SHOT-001",
                            "scene_visual_plan_ref": {
                                "owner": "short-drama-storyboard",
                                "artifact": SCENE_PLANS,
                                "hash": plan_hash,
                                "record_id": "SVP-EP001-SC001",
                            },
                        }
                    )
                },
                input_hashes={SCENE_PLANS: plan_hash},
                input_records={SCENE_PLANS: ["SVP-EP001-SC001"]},
            )[SHOTS]
            self.publish_and_accept(
                root,
                artifact_id="video:EP001",
                owner="short-drama-video-prompts",
                outputs={
                    MOTIONS: jsonl(
                        {
                            "motion_id": "MOTION-001",
                            "shot_ref": {
                                "owner": "short-drama-storyboard",
                                "artifact": SHOTS,
                                "hash": shots_hash,
                                "record_id": "SHOT-001",
                            },
                        }
                    )
                },
                input_hashes={SHOTS: shots_hash},
                input_records={SHOTS: ["SHOT-001"]},
            )

            project_tool.publish_candidate(
                root,
                owner="short-drama-assets",
                artifact_id="assets:locations",
                outputs={
                    location_path: jsonl(
                        {"location_id": "LOC-LOBBY", "shape": "方正"}
                    )
                },
            )
            state = json.loads(
                (root / ".short-drama/state.json").read_text(encoding="utf-8")
            )
            for artifact_id in (
                "storyboard:EP001:scene-plan:SC001",
                "storyboard:EP001:shots",
                "video:EP001",
            ):
                self.assertEqual(state["artifacts"][artifact_id]["build_state"], "stale")

    def test_two_scene_scoped_directing_layers_keep_independent_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            for scene_id in ("SC001", "SC002"):
                audition_path = (
                    f"episodes/EP001/storyboard/coverage-auditions/{scene_id}.jsonl"
                )
                plan_path = (
                    f"episodes/EP001/storyboard/scene-visual-plans/{scene_id}.jsonl"
                )
                self.publish_and_accept(
                    root,
                    artifact_id=f"storyboard:EP001:audition:{scene_id}",
                    owner="short-drama-storyboard",
                    outputs={
                        audition_path: jsonl(
                            {
                                "audition_id": f"AUD-EP001-{scene_id}",
                                "approaches": [{"approach_id": "APPROACH-A"}],
                            }
                        )
                    },
                )
                self.publish_and_accept(
                    root,
                    artifact_id=f"storyboard:EP001:scene-plan:{scene_id}",
                    owner="short-drama-storyboard",
                    outputs={
                        plan_path: jsonl(
                            {"plan_id": f"SVP-EP001-{scene_id}"}
                        )
                    },
                )

            state = json.loads(
                (root / ".short-drama/state.json").read_text(encoding="utf-8")
            )
            for scene_id in ("SC001", "SC002"):
                for kind in ("audition", "scene-plan"):
                    artifact = state["artifacts"][
                        f"storyboard:EP001:{kind}:{scene_id}"
                    ]
                    self.assertEqual(artifact["build_state"], "materialized")
                    self.assertEqual(artifact["creator_acceptance"], "accepted")
            self.assertTrue(
                (root / "episodes/EP001/storyboard/coverage-auditions/SC001.jsonl").is_file()
            )
            self.assertTrue(
                (root / "episodes/EP001/storyboard/coverage-auditions/SC002.jsonl").is_file()
            )


if __name__ == "__main__":
    unittest.main()
