import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any

SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama/scripts/project_tool.py"
SPEC = importlib.util.spec_from_file_location("short_drama_project_tool", SCRIPT)
assert SPEC and SPEC.loader
project_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(project_tool)

CORE = SUITE / "skills/short-drama"


class LanguageTagTests(unittest.TestCase):
    def test_well_formed_tags_are_accepted_and_trimmed(self) -> None:
        for value, expected in (
            ("zh-CN", "zh-CN"),
            (" en ", "en"),
            ("ko", "ko"),
            ("zh-Hant-TW", "zh-Hant-TW"),
        ):
            with self.subTest(value=value):
                self.assertEqual(
                    project_tool.normalize_language_tag(value, field="language"),
                    expected,
                )

    def test_malformed_tag_is_refused_at_init_not_at_use(self) -> None:
        # Nothing downstream re-checks this value, so a bad tag would otherwise
        # propagate into every artifact that claims to follow it.
        for value in ("", "   ", "zh_CN", "中文", "e", "en--US"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    project_tool.normalize_language_tag(value, field="language")


class ProjectLanguageTests(unittest.TestCase):
    def initialize(self, **kwargs: str) -> tuple[Path, dict[str, Any]]:
        directory = tempfile.mkdtemp()
        root = Path(directory) / "project"
        options: dict[str, str] = {
            "title": "测试项目",
            "language": "zh-CN",
            "aspect_ratio": "9:16",
        }
        options.update(kwargs)
        result = project_tool.initialize_project(root, suite_root=CORE, **options)
        return root, result["project"]

    def test_defaults_split_creator_language_from_prompt_language(self) -> None:
        _, project = self.initialize()
        self.assertEqual(project["language"], "zh-CN")
        self.assertEqual(project["format"]["prompt_language"], "en")

    def test_prompt_language_can_follow_the_project_language_on_request(self) -> None:
        _, project = self.initialize(prompt_language="zh-CN")
        self.assertEqual(project["format"]["prompt_language"], "zh-CN")
        self.assertEqual(project["language"], "zh-CN")

    def test_creator_language_change_does_not_move_prompt_language(self) -> None:
        # The two fields address different audiences. Writing a project in
        # Korean must not silently change what generators are asked to render.
        _, project = self.initialize(language="ko")
        self.assertEqual(project["language"], "ko")
        self.assertEqual(project["format"]["prompt_language"], "en")

    def test_malformed_language_refuses_initialization(self) -> None:
        for kwargs in ({"language": "zh_CN"}, {"prompt_language": ""}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    self.initialize(**kwargs)

    def test_status_reports_both_languages_so_skills_stop_guessing(self) -> None:
        root, _ = self.initialize(language="ja", prompt_language="en")
        status = project_tool.project_status(root)
        self.assertEqual(status["language"], "ja")
        self.assertEqual(status["prompt_language"], "en")

    def test_status_falls_back_for_projects_created_before_the_field(self) -> None:
        root, _ = self.initialize()
        project_path = root / project_tool.PROJECT_FILE
        project = json.loads(project_path.read_text(encoding="utf-8"))
        del project["format"]["prompt_language"]
        project_path.write_text(
            json.dumps(project, ensure_ascii=False), encoding="utf-8"
        )

        status = project_tool.project_status(root)
        self.assertEqual(
            status["prompt_language"], project_tool.DEFAULT_PROMPT_LANGUAGE
        )

    def test_one_resolver_owns_the_fallback(self) -> None:
        # Every reader goes through project_languages, so a project written
        # before the field existed resolves the default in exactly one place.
        self.assertEqual(
            project_tool.project_languages({}),
            {"language": "zh-CN", "prompt_language": "en"},
        )
        self.assertEqual(
            project_tool.project_languages({"language": "ko", "format": {}}),
            {"language": "ko", "prompt_language": "en"},
        )


class TemplateTests(unittest.TestCase):
    def test_template_ships_the_documented_default(self) -> None:
        template = json.loads(
            (CORE / "assets/project-template/short-drama.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(template["language"], "zh-CN")
        self.assertEqual(template["format"]["prompt_language"], "en")

    def test_contract_documents_both_fields(self) -> None:
        contract = (CORE / "references/contract-and-ownership.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("#/format/prompt_language", contract)
        self.assertIn("Output language contract", contract)


# The stages that hand a prompt body to a generator. Each must say which of its
# outputs follows which field, because these are exactly the artifacts where the
# creator-facing language and the generator-facing language disagree.
PROMPT_AUTHORING_SKILLS = (
    "short-drama-image-prompts",
    "short-drama-video-prompts",
    "short-drama-storyboard",
)
# Every skill that writes something a creator reads.
CREATOR_FACING_SKILLS = PROMPT_AUTHORING_SKILLS + (
    "short-drama",
    "short-drama-review",
)
# A language named as a literal default in skill prose. The contract says the
# project field decides, so a skill that spells one of these out has re-created
# the guess the field exists to remove.
HARDCODED_LANGUAGE_RE = re.compile(
    r"(默认使用创作者的?语言|中文项目使用中文|中文项目的[^\n]{0,40}使用中文)"
)


class SkillWiringTests(unittest.TestCase):
    """The contract is only landed if the stages that render text read it.

    Declaring the fields in the core contract while every prompt-authoring
    stage keeps its own hardcoded default is the failure this guards: the
    default would then apply to nothing, and `status` would report a value no
    one consumes.
    """

    def skill_text(self, skill: str) -> str:
        return (SUITE / "skills" / skill / "SKILL.md").read_text(encoding="utf-8")

    def test_prompt_authoring_skills_bind_prompt_bodies_to_prompt_language(
        self,
    ) -> None:
        for skill in PROMPT_AUTHORING_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn("#/format/prompt_language", self.skill_text(skill))

    def test_creator_facing_skills_bind_their_text_to_the_project_language(
        self,
    ) -> None:
        for skill in CREATOR_FACING_SKILLS:
            with self.subTest(skill=skill):
                self.assertIn("#/language", self.skill_text(skill))

    def test_no_skill_hardcodes_a_creator_facing_language(self) -> None:
        for path in sorted((SUITE / "skills").glob("*/SKILL.md")):
            with self.subTest(skill=path.parent.name):
                found = HARDCODED_LANGUAGE_RE.findall(path.read_text(encoding="utf-8"))
                self.assertEqual(found, [], f"{path.parent.name} hardcodes a language")

    def test_review_never_claims_authority_over_prompt_language(self) -> None:
        # A reviewer that flags an English prompt in a Chinese project as a
        # defect would turn a creator's accepted choice into a blocking finding.
        self.assertIn("prompt_language", self.skill_text("short-drama-review"))


if __name__ == "__main__":
    unittest.main()
