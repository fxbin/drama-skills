import importlib.util
import json
from unittest import mock
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SUITE = Path(__file__).resolve().parents[1]
CORE_SCRIPT = SUITE / "skills/short-drama/scripts/project_tool.py"
PRODUCTION_SCRIPT = SUITE / "skills/short-drama-produce/scripts/production_tool.py"
FIXTURE_ADAPTER = SUITE / "skills/short-drama-produce/scripts/fixture_adapter.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


project_tool = load_module("production_core", CORE_SCRIPT)
production_tool = load_module("confirmed_production", PRODUCTION_SCRIPT)


class ConfirmedProductionTests(unittest.TestCase):
    def make_project(self, directory: str) -> Path:
        root = Path(directory) / "project"
        project_tool.initialize_project(
            root,
            title="投产测试",
            language="zh-CN",
            aspect_ratio="9:16",
            suite_root=SUITE / "skills/short-drama",
        )
        source = root / "剧集/EP001/prompts/current.md"
        source.parent.mkdir(parents=True)
        source.write_text("当前提示词来源\n", encoding="utf-8")
        reference = root / "输入/reference.png"
        reference.write_bytes(b"reference")
        return root

    def write_job(
        self,
        root: Path,
        *,
        modality: str = "image",
        job_id: str = "EP001-SHOT001",
        prompt: str = "一名角色站在雨夜门口",
        output: str | None = None,
        overwrite: bool = False,
        parameters: dict | None = None,
    ) -> Path:
        extensions = {"image": "png", "video": "mp4", "tts": "wav", "music": "wav"}
        output = output or (
            f"剧集/EP001/制作成果/{modality}/{job_id}.{extensions[modality]}"
        )
        path = root / "job.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "job_id": job_id,
                    "modality": modality,
                    "adapter": "fixture",
                    "prompt": prompt,
                    "source": "剧集/EP001/prompts/current.md",
                    "references": ["输入/reference.png"],
                    "outputs": [output],
                    "parameters": parameters or {"count": 1},
                    "overwrite": overwrite,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def adapter_config(self, directory: str, *, fail: bool = False) -> Path:
        command = [sys.executable, str(FIXTURE_ADAPTER)]
        if fail:
            command.append("--fail")
        path = Path(directory) / "adapters.json"
        path.write_text(
            json.dumps(
                {
                    "adapters": {
                        "fixture": {
                            "command": command,
                            "timeout_seconds": 30,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        return path

    def prepare_and_confirm(self, root: Path, job: Path) -> dict:
        preview = production_tool.prepare_job(root, job)
        production_tool.confirm_job(
            root,
            job_id=preview["job_id"],
            confirmation=preview["confirmation"],
        )
        return preview

    def test_prepare_only_returns_a_complete_preview_and_creates_no_media(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = production_tool.prepare_job(root, job)

            self.assertEqual(preview["state"], "needs_confirmation")
            self.assertEqual(preview["count"], 1)
            self.assertEqual(preview["prompt"], "一名角色站在雨夜门口")
            self.assertEqual(preview["adapter"], "fixture")
            self.assertTrue(preview["confirmation"].startswith("CONFIRM EP001-SHOT001 "))
            self.assertFalse((root / preview["outputs"][0]).exists())
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "needs_confirmation",
            )

    def test_run_requires_the_exact_explicit_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            config = self.adapter_config(directory)
            preview = production_tool.prepare_job(root, job)

            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.confirm_job(
                    root,
                    job_id="EP001-SHOT001",
                    confirmation="yes, generate it",
                )

            production_tool.confirm_job(
                root,
                job_id="EP001-SHOT001",
                confirmation=preview["confirmation"],
            )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "confirmed",
            )

    def test_changed_job_invalidates_a_previous_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root, prompt="版本一")
            preview = self.prepare_and_confirm(root, job)
            self.write_job(root, prompt="版本二")
            changed = production_tool.prepare_job(root, job)

            self.assertNotEqual(preview["confirmation"], changed["confirmation"])
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )

    def test_changed_input_requires_prepare_and_confirmation_again(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            (root / "剧集/EP001/prompts/current.md").write_text(
                "提示词来源已改\n", encoding="utf-8"
            )

            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "needs_reconfirmation",
            )
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )

    def test_fixture_executes_every_supported_media_job(self) -> None:
        signatures = {
            "image": b"\x89PNG",
            "video": b"\x00\x00\x00\x18ftypisom",
            "tts": b"RIFF",
            "music": b"RIFF",
        }
        for modality, signature in signatures.items():
            with self.subTest(modality=modality), tempfile.TemporaryDirectory() as directory:
                root = self.make_project(directory)
                job_id = f"EP001-{modality}"
                job = self.write_job(root, modality=modality, job_id=job_id)
                preview = self.prepare_and_confirm(root, job)
                result = production_tool.run_job(
                    root,
                    job_id=job_id,
                    adapter_config=self.adapter_config(directory),
                )

                target = root / preview["outputs"][0]
                self.assertTrue(target.read_bytes().startswith(signature))
                self.assertEqual(result["state"], "succeeded")
                self.assertEqual(result["outputs"][0]["path"], preview["outputs"][0])
                self.assertGreater(result["outputs"][0]["bytes"], 0)
                status = production_tool.job_status(root, job_id=job_id)
                self.assertEqual(status["state"], "succeeded")
                self.assertNotIn("command", json.dumps(status))

    def test_failed_started_adapter_consumes_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            config = self.adapter_config(directory, fail=True)

            with self.assertRaisesRegex(production_tool.AdapterError, "code 7"):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "failed",
            )
            error = production_tool.job_status(
                root, job_id="EP001-SHOT001"
            )["latest_run"]["error"]
            self.assertEqual(error["code"], "adapter_exit_7")
            self.assertNotIn("message", error)
            with self.assertRaises(production_tool.ConfirmationRequiredError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )

    def test_structured_provider_failure_is_preserved_without_response_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            failure = Path(directory) / "safe_failure.py"
            failure.write_text(
                "import json, sys\n"
                "json.dump({'error': {'provider': 'fixture', "
                "'category': 'rate_limit', 'code': 'rate_limit_exceeded', "
                "'http_status': 429, 'request_id': 'req_safe_123', "
                "'retryable': True}}, sys.stdout)\n"
                "print('provider secret body', file=sys.stderr)\n"
                "raise SystemExit(1)\n",
                encoding="utf-8",
            )
            config = Path(directory) / "structured-adapters.json"
            config.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": [sys.executable, str(failure)],
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(production_tool.AdapterError):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=config
                )
            latest = production_tool.job_status(
                root, job_id="EP001-SHOT001"
            )["latest_run"]
            self.assertEqual(
                latest["error"],
                {
                    "provider": "fixture",
                    "category": "rate_limit",
                    "code": "rate_limit_exceeded",
                    "http_status": 429,
                    "request_id": "req_safe_123",
                    "retryable": True,
                },
            )
            self.assertNotIn("secret", json.dumps(latest))

    def test_adapter_reads_a_private_confirmed_input_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            config = self.adapter_config(directory)
            original = (root / "输入/reference.png").read_bytes()
            adapter_output = Path(directory) / "adapter-output.png"
            adapter_output.write_bytes(b"fixture output")

            def inspect_snapshot(command, timeout, payload, cwd):
                snapshot_root = Path(payload["project_root"])
                self.assertNotEqual(snapshot_root, root)
                self.assertEqual(
                    (snapshot_root / "输入/reference.png").read_bytes(), original
                )
                live = root / "输入/reference.png"
                live.write_bytes(b"changed after confirmation consumption")
                self.assertEqual(
                    (snapshot_root / "输入/reference.png").read_bytes(), original
                )
                return {
                    "outputs": [
                        {
                            "target": payload["outputs"][0],
                            "source": str(adapter_output),
                        }
                    ]
                }

            with mock.patch.object(
                production_tool, "_run_adapter", side_effect=inspect_snapshot
            ):
                result = production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=config,
                )
            self.assertEqual(result["state"], "succeeded")

    def test_existing_output_requires_explicit_overwrite_without_consuming(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = self.prepare_and_confirm(root, job)
            target = root / preview["outputs"][0]
            target.parent.mkdir(parents=True)
            target.write_bytes(b"existing")

            with self.assertRaisesRegex(FileExistsError, "overwrite is false"):
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "confirmed",
            )

    def test_adapter_reads_an_immutable_confirmed_input_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            original = (root / "剧集/EP001/prompts/current.md").read_bytes()

            def inspect_snapshot(command, timeout, payload, cwd):
                snapshot = Path(payload["project_root"])
                self.assertNotEqual(snapshot, root)
                (root / "剧集/EP001/prompts/current.md").write_bytes(
                    b"CHANGED AFTER CHECK"
                )
                source = snapshot / "剧集/EP001/prompts/current.md"
                self.assertEqual(source.read_bytes(), original)
                output = Path(directory) / "snapshot-result.png"
                output.write_bytes(source.read_bytes())
                return {
                    "outputs": [
                        {"target": payload["outputs"][0], "source": str(output)}
                    ]
                }

            with mock.patch.object(
                production_tool, "_run_adapter", side_effect=inspect_snapshot
            ):
                result = production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )
            self.assertEqual(result["state"], "succeeded")
            self.assertEqual(
                (root / result["outputs"][0]["path"]).read_bytes(), original
            )

    def test_output_created_during_adapter_run_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            preview = self.prepare_and_confirm(root, job)
            target = root / preview["outputs"][0]

            def create_target_during_run(command, timeout, payload, cwd):
                source = Path(directory) / "adapter-result.png"
                source.write_bytes(b"generated")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"CONCURRENT FILE")
                return {
                    "outputs": [
                        {"target": payload["outputs"][0], "source": str(source)}
                    ]
                }

            with mock.patch.object(
                production_tool, "_run_adapter", side_effect=create_target_during_run
            ), self.assertRaisesRegex(FileExistsError, "appeared"):
                production_tool.run_job(
                    root,
                    job_id="EP001-SHOT001",
                    adapter_config=self.adapter_config(directory),
                )
            self.assertEqual(target.read_bytes(), b"CONCURRENT FILE")

    def test_job_rejects_secrets_wrong_extensions_and_unsafe_outputs(self) -> None:
        cases = (
            ({"api_key": "not-allowed"}, None, "credentials"),
            ({}, "剧集/EP001/制作成果/image/result.mp4", "extension"),
            ({}, "剧集/EP001/result.png", "production"),
            ({}, "输入/production/stolen.png", "production"),
            ({}, "交付/production/result.png", "production"),
            ({}, "../result.png", "unsafe"),
        )
        for parameters, output, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                root = self.make_project(directory)
                job = self.write_job(root, parameters=parameters, output=output)
                with self.assertRaisesRegex(ValueError, message):
                    production_tool.prepare_job(root, job)

    def test_adapter_config_must_be_external_and_use_argv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            self.prepare_and_confirm(root, job)
            inside = root / "adapter.json"
            inside.write_text(
                json.dumps(
                    {
                        "adapters": {
                            "fixture": {
                                "command": f"{sys.executable} {FIXTURE_ADAPTER}",
                                "timeout_seconds": 30,
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "outside"):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=inside
                )

            outside = Path(directory) / "bad-config.json"
            outside.write_bytes(inside.read_bytes())
            with self.assertRaisesRegex(ValueError, "string list"):
                production_tool.run_job(
                    root, job_id="EP001-SHOT001", adapter_config=outside
                )
            self.assertEqual(
                production_tool.job_status(root, job_id="EP001-SHOT001")["state"],
                "confirmed",
            )

    def test_cli_runs_prepare_confirm_execute_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_project(directory)
            job = self.write_job(root)
            config = self.adapter_config(directory)

            prepared = subprocess.run(
                [sys.executable, str(PRODUCTION_SCRIPT), "prepare", str(root), "--job", str(job)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(prepared.returncode, 0, prepared.stderr)
            preview = json.loads(prepared.stdout)
            confirmed = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "confirm",
                    str(root),
                    "--job-id",
                    preview["job_id"],
                    "--confirmation",
                    preview["confirmation"],
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(confirmed.returncode, 0, confirmed.stderr)
            executed = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "run",
                    str(root),
                    "--job-id",
                    preview["job_id"],
                    "--adapter-config",
                    str(config),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(json.loads(executed.stdout)["state"], "succeeded")
            status = subprocess.run(
                [
                    sys.executable,
                    str(PRODUCTION_SCRIPT),
                    "status",
                    str(root),
                    "--job-id",
                    preview["job_id"],
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["state"], "succeeded")


if __name__ == "__main__":
    unittest.main()
