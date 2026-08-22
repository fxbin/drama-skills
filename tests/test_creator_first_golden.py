"""Small regression for the creator-first authoring surface and native example."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EPISODE = ROOT / "examples/creator-first/EP001"
EXPECTED = {
    "剧本.md",
    "视觉设定.md",
    "分镜.md",
    "图片提示词.md",
    "视频提示词.md",
}


def text(name: str) -> str:
    return (EPISODE / name).read_text(encoding="utf-8")


def heading_ids(document: str, prefix: str) -> list[str]:
    return re.findall(rf"^## ({prefix}[A-Z0-9-]+)\b", document, flags=re.MULTILINE)


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
        self.assertGreaterEqual(len(re.findall(r"^## SC\d+", screenplay, re.MULTILINE)), 2)
        self.assertIn("**江晨**", screenplay)
        self.assertIn("剩余 4 天 23:59:58", screenplay)

        visual = text("视觉设定.md")
        for section in ("## 人物", "## 地点", "## 道具", "稳定锚点"):
            self.assertIn(section, visual)

    def test_storyboard_and_motion_cover_the_same_unique_shots(self) -> None:
        storyboard = text("分镜.md")
        video = text("视频提示词.md")
        shot_ids = heading_ids(storyboard, "SHOT-")
        motion_ids = heading_ids(video, "MOTION-")
        motion_shots = re.findall(r"^- 分镜：(SHOT-[A-Z0-9-]+)$", video, re.MULTILINE)

        self.assertEqual(len(shot_ids), 8)
        self.assertEqual(len(shot_ids), len(set(shot_ids)))
        self.assertEqual(len(motion_ids), len(set(motion_ids)))
        self.assertEqual(motion_shots, shot_ids)
        self.assertEqual(storyboard.count("### 冻结关键帧提示词"), len(shot_ids))
        self.assertEqual(video.count("### 可复制提示词"), len(shot_ids))

        durations = [int(value) for value in re.findall(r"^- 时长：(\d+)s$", storyboard, re.MULTILINE)]
        self.assertEqual(sum(durations), 50)

    def test_image_prompts_are_copyable_and_bounded(self) -> None:
        prompts = text("图片提示词.md")
        ids = heading_ids(prompts, "IMG-")
        self.assertEqual(len(ids), 4)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(prompts.count("### 可复制提示词"), len(ids))
        self.assertEqual(prompts.count("no watermark"), len(ids))

    def test_default_contract_forbids_the_removed_pipeline_noise(self) -> None:
        contract = (
            ROOT / "skills/short-drama/references/creator-workflow.md"
        ).read_text(encoding="utf-8")
        self.assertIn("默认只维护五份创作者可读 Markdown", contract)
        self.assertIn("不要另外落盘 JSON/JSONL、索引、指纹、覆盖表、QA 报告", contract)
        self.assertIn("preview -> explicit confirm -> run", contract)
        self.assertNotIn("creator_state.py", contract)


if __name__ == "__main__":
    unittest.main()
