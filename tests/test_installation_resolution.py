import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SUITE = Path(__file__).resolve().parents[1]
SKILLS = SUITE / "skills"
CORE = SKILLS / "short-drama"
EXPECTED_SKILLS = {
    "short-drama",
    "short-drama-novel-analyze",
    "short-drama-develop",
    "short-drama-write",
    "short-drama-assets",
    "short-drama-image-prompts",
    "short-drama-storyboard",
    "short-drama-video-prompts",
    "short-drama-produce",
    "short-drama-review",
}


class InstallationResolutionTests(unittest.TestCase):
    def test_each_skill_is_a_standalone_installation_unit(self) -> None:
        self.assertEqual(
            {path.name for path in SKILLS.iterdir() if path.is_dir()}, EXPECTED_SKILLS
        )
        for name in EXPECTED_SKILLS:
            with self.subTest(skill=name):
                skill = SKILLS / name
                self.assertTrue((skill / "SKILL.md").is_file())
                self.assertTrue((skill / "agents/openai.yaml").is_file())
                self.assertFalse((skill / "suite-ref.json").exists())
                for markdown in skill.rglob("*.md"):
                    targets = re.findall(r"\[[^]]+\]\(([^)#]+)(?:#[^)]+)?\)", markdown.read_text(encoding="utf-8"))
                    for target in targets:
                        if "://" in target:
                            continue
                        resolved = (markdown.parent / target).resolve()
                        self.assertTrue(
                            resolved.is_relative_to(skill.resolve()),
                            f"{markdown}: cross-skill link {target}",
                        )

    def test_suite_integrity_and_capability_manifests_are_not_shipped(self) -> None:
        self.assertFalse((CORE / "suite-manifest.json").exists())
        self.assertFalse((CORE / "scripts/suite_verify.py").exists())
        self.assertFalse((SUITE / "tools/update_suite_manifest.py").exists())
        self.assertFalse((SUITE / "tools/verify_suite.py").exists())

        forbidden = (
            "core_manifest_sha256",
            "core_manifest",
            "trust_boundary",
            "public_skills",
        )
        for path in SKILLS.rglob("*"):
            if not path.is_file() or path.suffix not in {".md", ".json", ".py"}:
                continue
            content = path.read_text(encoding="utf-8")
            for marker in forbidden:
                self.assertNotIn(marker, content, f"{path}: {marker}")

        project_tool = (CORE / "scripts/project_tool.py").read_text(encoding="utf-8")
        self.assertNotIn("DECLARED_PROJECT_ARTIFACT_OWNERS", project_tool)
        self.assertNotIn("DECLARED_EPISODE_ARTIFACT_OWNERS", project_tool)
        self.assertNotIn("_expected_path_owner", project_tool)

    def test_core_cli_initializes_when_only_the_core_skill_is_installed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            installed = temp / "CODEX HOME 空格/skills/short-drama"
            shutil.copytree(CORE, installed)
            tool = installed / "scripts/project_tool.py"
            arbitrary_cwd = temp / "unrelated cwd 空格"
            arbitrary_cwd.mkdir()
            project = temp / "创作者 项目"
            env = os.environ.copy()
            env["CODEX_HOME"] = str(temp / "empty CODEX_HOME")
            env["PYTHONIOENCODING"] = "cp1252"

            initialized = subprocess.run(
                [
                    sys.executable,
                    str(tool),
                    "init",
                    str(project),
                    "--title",
                    "失物登记",
                ],
                cwd=arbitrary_cwd,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            self.assertEqual(json.loads(initialized.stdout)["project"]["title"], "失物登记")

            nested = project / "剧集/EP001/notes"
            nested.mkdir(parents=True)
            status = subprocess.run(
                [sys.executable, str(tool), "status", "."],
                cwd=nested,
                env=env,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["project_root"], str(project.resolve()))

    def test_shipped_skills_declare_their_own_contract_metadata(self) -> None:
        for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
            with self.subTest(skill=skill_md.parent.name):
                frontmatter = skill_md.read_text(encoding="utf-8").split("---", 2)[1]
                self.assertRegex(frontmatter, rf"(?m)^name: {skill_md.parent.name}$")
                self.assertRegex(frontmatter, r"(?m)^description: .+$")
                self.assertRegex(frontmatter, r"(?m)^license: MIT$")
                self.assertNotRegex(frontmatter, r"(?m)^allowed-tools:")


if __name__ == "__main__":
    unittest.main()
