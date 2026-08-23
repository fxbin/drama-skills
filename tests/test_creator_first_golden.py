"""Small regression for the creator-first authoring surface and native example."""

from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "examples/creator-first/EP001"
EXPECTED = {
    "剧本.md",
    "视觉设定.md",
    "分镜.md",
    "图片提示词.md",
    "视频提示词.md",
}
CREATOR_SKILLS = (
    "short-drama",
    "short-drama-write",
    "short-drama-assets",
    "short-drama-image-prompts",
    "short-drama-storyboard",
    "short-drama-video-prompts",
)
ACTIVE_CREATOR_SKILLS = (*CREATOR_SKILLS, "short-drama-review")
EXPECTED_KNOWHOW = {
    "short-drama": {
        "audience-reveal.md",
        "contract-and-ownership.md",
        "creator-documents.md",
        "creator-workflow.md",
        "knowhow-index.md",
        "look-development.md",
        "pickup-and-alternate.md",
        "production-form-profiles.md",
        "reference-roles.md",
        "runtime-preflight.md",
    },
    "short-drama-write": {
        "dialogue-craft.md",
        "production-format-dialect.md",
        "scene-handoff-capsule.md",
        "scene-sound-dramaturgy.md",
        "screenplay-format.md",
        "script-craft.md",
        "stage-contract.md",
        "substitutable-realization.md",
    },
    "short-drama-assets": {
        "asset-review-checklist.md",
        "character-and-look.md",
        "continuity-delta.md",
        "identity-vs-variant.md",
        "location-and-view.md",
        "occurrence-extraction.md",
        "prop-and-state.md",
        "stage-contract.md",
        "voice-direction.md",
    },
    "short-drama-image-prompts": {
        "character-and-look.md",
        "common-recipe.md",
        "edit-and-revision.md",
        "location-plate.md",
        "look-and-state-variant.md",
        "lookdev-frame.md",
        "production-sheet-recipes.md",
        "prop-plate.md",
        "review-and-fixtures.md",
        "stage-contract.md",
    },
    "short-drama-storyboard": {
        "blocking-playbooks.md",
        "comic-keyframe-lexicon.md",
        "coverage-audition.md",
        "keyframe-craft.md",
        "production-shot-grammar.md",
        "review-and-fixtures.md",
        "scene-visual-plan.md",
        "screenplay-to-keyframe-example.md",
        "shot-craft.md",
        "shot-revision-identity.md",
        "stage-contract.md",
    },
    "short-drama-video-prompts": {
        "camera-audio-continuity.md",
        "delivery-profile.md",
        "generability.md",
        "motion-recipe.md",
        "performance-action-timing.md",
        "production-prompt-grammar.md",
        "review-and-fixtures.md",
        "stage-contract.md",
    },
    "short-drama-review": {
        "anti-template-repair.md",
        "production-quality-gates.md",
        "project-calibration.md",
        "review-method.md",
        "rubric-assets-prompts.md",
        "rubric-source-analysis.md",
        "rubric-story-script.md",
        "rubric-visual-motion.md",
        "stage-contract.md",
    },
}
INDEXER_SPEC = importlib.util.spec_from_file_location(
    "creator_first_screenplay_index",
    ROOT / "skills/short-drama-write/scripts/screenplay_index.py",
)
assert INDEXER_SPEC and INDEXER_SPEC.loader
screenplay_index = importlib.util.module_from_spec(INDEXER_SPEC)
INDEXER_SPEC.loader.exec_module(screenplay_index)


def text(name: str) -> str:
    return (EPISODE / name).read_text(encoding="utf-8")


def heading_ids(document: str, prefix: str) -> list[str]:
    return re.findall(rf"^## ({prefix}[A-Z0-9-]+)\b", document, flags=re.MULTILINE)


def frozen_prompt(document: str, shot_id: str) -> str:
    section = document.split(f"## {shot_id}", 1)[1].split("\n## ", 1)[0]
    return section.split("### 冻结关键帧提示词", 1)[1]


def sections(document: str, prefix: str) -> dict[str, str]:
    matches = list(re.finditer(rf"^## ({prefix}[A-Z0-9-]+)\b", document, re.MULTILINE))
    return {
        match.group(1): document[match.start() : matches[index + 1].start() if index + 1 < len(matches) else None]
        for index, match in enumerate(matches)
    }


def reachable_markdown(start: Path, root: Path) -> set[Path]:
    link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+\.md(?:#[^)]+)?)\)")
    seen: set[Path] = set()
    pending = [start.resolve()]
    root = root.resolve()

    while pending:
        current = pending.pop()
        if current in seen or not current.is_file():
            continue
        seen.add(current)
        for raw_target in link_pattern.findall(current.read_text(encoding="utf-8")):
            target = unquote(raw_target.split("#", 1)[0])
            resolved = (current.parent / target).resolve()
            if resolved == root or root in resolved.parents:
                pending.append(resolved)
    return seen


class CreatorFirstGoldenTests(unittest.TestCase):
    def test_episode_exposes_exactly_five_markdown_documents(self) -> None:
        files = {path.name for path in EPISODE.iterdir() if path.is_file()}
        self.assertEqual(files, EXPECTED)
        self.assertFalse(list(EPISODE.rglob("*.json")))
        self.assertFalse(list(EPISODE.rglob("*.jsonl")))

    def test_documents_are_complete_creator_content_not_placeholders(self) -> None:
        for name in EXPECTED:
            content = text(name)
            self.assertGreater(len(content), 500, name)
            self.assertNotRegex(content, r"(?i)TODO|TBD|PLACEHOLDER|待补|待定")

        screenplay = text("剧本.md")
        self.assertGreaterEqual(
            len(re.findall(r"^## EP001-SC\d+ (?:内|外|内外) · ", screenplay, re.MULTILINE)),
            2,
        )
        self.assertIn("江晨：", screenplay)
        self.assertIn("剩余 4 天 23:59:58", screenplay)

        visual = text("视觉设定.md")
        for section in ("## 人物", "## 地点", "## 道具", "识别锚点"):
            self.assertIn(section, visual)
        self.assertEqual(visual.count("- 识别锚点："), 6)

    def test_storyboard_and_motion_cover_the_same_unique_shots(self) -> None:
        storyboard = text("分镜.md")
        video = text("视频提示词.md")
        shot_ids = heading_ids(storyboard, "SHOT-")
        motion_ids = heading_ids(video, "MOTION-")
        motion_shots = re.findall(r"^- 分镜：(SHOT-[A-Z0-9-]+)$", video, re.MULTILINE)

        self.assertGreater(len(shot_ids), 0)
        self.assertEqual(len(shot_ids), len(set(shot_ids)))
        self.assertEqual(len(motion_ids), len(set(motion_ids)))
        self.assertEqual(motion_shots, shot_ids)
        self.assertEqual(storyboard.count("### 冻结关键帧提示词"), len(shot_ids))
        self.assertEqual(video.count("### 可复制提示词"), len(shot_ids))

        storyboard_durations = {
            shot_id: int(re.search(r"^- 时长：(\d+)s$", body, re.MULTILINE).group(1))
            for shot_id, body in sections(storyboard, "SHOT-").items()
        }
        motion_durations = {
            re.search(r"^- 分镜：(SHOT-[A-Z0-9-]+)$", body, re.MULTILINE).group(1): int(
                re.search(r"^- 时长：(\d+)s$", body, re.MULTILINE).group(1)
            )
            for body in sections(video, "MOTION-").values()
        }
        self.assertEqual(motion_durations, storyboard_durations)

    def test_each_shot_names_its_image_references(self) -> None:
        image_ids = set(heading_ids(text("图片提示词.md"), "IMG-"))
        for shot_id, body in sections(text("分镜.md"), "SHOT-").items():
            with self.subTest(shot=shot_id):
                reference_line = re.search(r"^- 参考：(.+)$", body, re.MULTILINE)
                self.assertIsNotNone(reference_line)
                referenced = set(re.findall(r"\bIMG-[A-Z0-9-]+\b", reference_line.group(1)))
                self.assertTrue(referenced)
                self.assertLessEqual(referenced, image_ids)

    def test_frozen_keyframes_are_motion_start_states(self) -> None:
        storyboard = text("分镜.md")
        self.assertIn("formal neutral expression", frozen_prompt(storyboard, "SHOT-EP001-003"))
        self.assertNotIn("8,472", frozen_prompt(storyboard, "SHOT-EP001-005"))
        self.assertNotIn("配乐", frozen_prompt(storyboard, "SHOT-EP001-006"))
        self.assertIn("screen completely dark", frozen_prompt(storyboard, "SHOT-EP001-007"))
        self.assertNotIn("23:59", frozen_prompt(storyboard, "SHOT-EP001-008"))

    def test_screenplay_is_accepted_by_the_documented_indexer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = screenplay_index.build_index(
                EPISODE / "剧本.md",
                Path(directory) / "index.jsonl",
                speakers={"江晨", "周薄森", "系统"},
            )
        self.assertEqual(summary["review_status"], "clean")
        self.assertEqual(summary["source_issue_count"], 0)
        self.assertGreater(summary["block_count"], 0)

    def test_image_prompts_are_copyable_and_bounded(self) -> None:
        prompts = text("图片提示词.md")
        ids = heading_ids(prompts, "IMG-")
        self.assertGreater(len(ids), 0)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(prompts.count("### 可复制提示词"), len(ids))
        for image_id, body in sections(prompts, "IMG-").items():
            with self.subTest(prompt=image_id):
                self.assertRegex(body.lower(), r"no [^\n>]*watermark")

    def test_story_critical_text_and_lines_reach_the_delivery_prompts(self) -> None:
        downstream = "\n".join((text("分镜.md"), text("图片提示词.md"), text("视频提示词.md")))
        for fact in (
            "微博 2",
            "短视频 0",
            "全站创作者榜",
            "演唱",
            "伴奏素材《亮剑》×1",
            "剩余 4 天 23:59:58",
            "一片没人动过的地",
            "我不懂音乐。连抄都抄不出来。",
        ):
            with self.subTest(fact=fact):
                self.assertIn(fact, downstream)

    def test_every_screenplay_tag_is_documented_for_creator_first(self) -> None:
        guidance = "\n".join(
            (
                (ROOT / "skills/short-drama-write/SKILL.md").read_text(encoding="utf-8"),
                (ROOT / "skills/short-drama/references/creator-documents.md").read_text(encoding="utf-8"),
            )
        )
        for tag in screenplay_index.SUPPORTED_TAGS:
            with self.subTest(tag=tag):
                self.assertIn(f"[{tag}]", guidance)

    def test_every_creator_knowledge_reference_is_reachable(self) -> None:
        for skill_name in ACTIVE_CREATOR_SKILLS:
            skill_root = ROOT / "skills" / skill_name
            references = {path.resolve() for path in (skill_root / "references").rglob("*.md")}
            reachable = reachable_markdown(skill_root / "SKILL.md", skill_root)
            with self.subTest(skill=skill_name):
                self.assertEqual(
                    references - reachable,
                    set(),
                    "knowledge kept on disk but unreachable from the skill",
                )

    def test_creator_knowledge_inventory_is_preserved(self) -> None:
        for skill_name, expected in EXPECTED_KNOWHOW.items():
            references = ROOT / "skills" / skill_name / "references"
            actual = {path.name for path in references.glob("*.md")}
            with self.subTest(skill=skill_name):
                self.assertEqual(actual, expected)

    def test_creator_knowledge_does_not_route_back_to_retired_artifacts(self) -> None:
        retired = (
            "screenplay.md",
            "screenplay-index.jsonl",
            "creator_authority",
            "creator-decisions",
            "set-authority",
            "创作者决策/",
            "设定集/voice-casting.md",
            "shots.jsonl",
            "motion-specs.jsonl",
            "look_development",
            "record_id",
            "evidence_refs",
            "target_ref",
            "coverage_scope",
            "supersession-decision.example.json",
            "accepted structured spec",
        )
        for skill_name in ACTIVE_CREATOR_SKILLS:
            references = ROOT / "skills" / skill_name / "references"
            for path in references.glob("*.md"):
                document = path.read_text(encoding="utf-8")
                for term in retired:
                    with self.subTest(skill=skill_name, reference=path.name, term=term):
                        self.assertNotIn(term, document)

    def test_creator_rule_catalogs_keep_every_craft_rule(self) -> None:
        expected = {
            "short-drama-write": {*(f"SCR-{number:02d}" for number in range(1, 18))},
            "short-drama-assets": {
                *(f"AST-{number:02d}" for number in range(1, 13)),
                *(f"CON-{number:02d}" for number in range(1, 7)),
            },
            "short-drama-image-prompts": {
                *(f"IMG-{number:02d}" for number in range(1, 13))
            },
            "short-drama-storyboard": {
                *(f"SHT-{number:02d}" for number in range(1, 22)),
                *(f"CON-{number:02d}" for number in range(1, 7)),
            },
            "short-drama-video-prompts": {
                *(f"VID-{number:02d}" for number in range(1, 23)),
                *(f"CON-{number:02d}" for number in range(1, 7)),
            },
            "short-drama-review": {*(f"REV-{number:02d}" for number in range(1, 12))},
        }
        for skill_name, rule_ids in expected.items():
            contract = (
                ROOT / "skills" / skill_name / "references/stage-contract.md"
            ).read_text(encoding="utf-8")
            actual = set(re.findall(r"\b(?:SCR|AST|IMG|SHT|VID|CON|REV)-\d{2}\b", contract))
            with self.subTest(skill=skill_name):
                self.assertEqual(actual, rule_ids)

    def test_creator_skills_have_one_layout_not_a_compatibility_branch(self) -> None:
        for skill_name in CREATOR_SKILLS:
            document = (ROOT / "skills" / skill_name / "SKILL.md").read_text(encoding="utf-8")
            with self.subTest(skill=skill_name):
                self.assertNotIn("旧项目兼容", document)
                self.assertNotIn("已有结构化", document)

        produce = (ROOT / "skills/short-drama-produce/SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn("旧版规格", produce)
        for retired_name in ("image-prompt-specs.jsonl", "motion-specs.jsonl", "voice-record-sheet.jsonl"):
            self.assertNotIn(retired_name, produce)

    def test_review_outputs_creator_readable_markdown(self) -> None:
        review = (ROOT / "skills/short-drama-review/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("审查/EP001-审查.md", review)
        self.assertNotIn("findings.jsonl", review)
        self.assertNotIn("verdict.json", review)

    def test_removed_pipeline_does_not_return(self) -> None:
        contract = (
            ROOT / "skills/short-drama/references/creator-workflow.md"
        ).read_text(encoding="utf-8")
        # ddfdbe3 briefly reintroduced a nested creator root and a generated
        # state module. These guards lock the corrected simple layout.
        self.assertNotIn("创作内容/剧集", contract)
        self.assertNotIn("creator_state.py", contract)


if __name__ == "__main__":
    unittest.main()
