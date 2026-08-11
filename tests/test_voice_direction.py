import importlib.util
import json
import unittest
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama/scripts/project_tool.py"
SPEC = importlib.util.spec_from_file_location("sd_project_tool_voice", SCRIPT)
assert SPEC and SPEC.loader
project_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_tool)

ASSETS = SUITE / "skills/short-drama-assets"


class OwnershipTests(unittest.TestCase):
    def test_casting_sheet_and_the_identity_it_projects_share_one_owner(self) -> None:
        # Splitting them would put the reference binding that defines a
        # character in one stage and the check that two characters stay
        # distinguishable in another.
        owners = {
            path: project_tool._expected_path_owner(path)
            for path in (
                "设定集/characters.jsonl",
                "设定集/voice-casting.md",
                "剧集/EP001/voice-record-sheet.jsonl",
            )
        }
        self.assertEqual(
            owners,
            {
                "设定集/characters.jsonl": "short-drama-assets",
                "设定集/voice-casting.md": "short-drama-assets",
                "剧集/EP001/voice-record-sheet.jsonl": "short-drama-write",
            },
        )


class RuleTests(unittest.TestCase):
    def test_one_spelling_per_pronunciation_blocks(self) -> None:
        # A second spelling is invisible in text review and only audible in the
        # finished cut, so it cannot wait for a judgement call.
        contract = (ASSETS / "references/stage-contract.md").read_text(encoding="utf-8")
        row = next(r for r in contract.splitlines() if r.startswith("| AST-10 "))
        self.assertIn("structural_invariant", row)


class RecordShapeTests(unittest.TestCase):
    """The shipped example must stay a legal record, since it is what a run copies."""

    def test_example_carries_a_reference_first_voice_direction(self) -> None:
        direction = json.loads(
            (ASSETS / "assets/character-look.example.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()[0]
        )["voice_direction"]

        reference = direction["reference"]
        # Timbre rides on a recording, and the recording stays in creator inputs.
        self.assertTrue(reference["artifact_ref"]["artifact"].startswith("输入/"))
        self.assertIn(reference["admission_status"], {"creator_described", "audibly_inspected", "unverified"})
        self.assertTrue(reference["may_control"])
        # Present in every recording, belonging to none of them.
        excluded = "".join(reference["must_not_control"])
        self.assertIn("情绪", excluded)
        self.assertIn("混响", excluded)

        # Criteria judge a candidate; an unbounded one gets executed further
        # every take, so each carries its own upper bound.
        self.assertTrue(direction["selection_criteria"])
        for criterion in direction["selection_criteria"]:
            self.assertTrue(criterion["counter_example"])

        self.assertTrue(direction["distinction"]["nearest_character_id"])
        # Excluded and simply-absent must stay distinguishable downstream.
        self.assertTrue(direction["not_voice_identity"])


if __name__ == "__main__":
    unittest.main()
