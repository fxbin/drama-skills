import base64
import io
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SUITE = Path(__file__).resolve().parents[1]
SCRIPT = SUITE / "skills/short-drama-produce/scripts/provider_adapters.py"
SPEC = importlib.util.spec_from_file_location("short_drama_provider_adapters", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
provider_adapters = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provider_adapters)


class ProviderCompilerTests(unittest.TestCase):
    def image_job(self, **parameters: object) -> dict[str, object]:
        return {
            "modality": "image",
            "prompt": "vertical character portrait",
            "references": [],
            "outputs": ["剧集/EP001/制作成果/images/portrait.png"],
            "parameters": parameters,
        }

    def video_job(self, **parameters: object) -> dict[str, object]:
        return {
            "modality": "video",
            "prompt": "slow push in as the evidence is revealed",
            "references": [],
            "outputs": ["剧集/EP001/制作成果/video/shot.mp4"],
            "parameters": parameters,
        }

    def music_job(self, **parameters: object) -> dict[str, object]:
        return {
            "modality": "music",
            "prompt": "restrained urban drama score",
            "references": [],
            "outputs": ["剧集/EP001/制作成果/music/cue.mp3"],
            "parameters": parameters,
        }

    def test_seedance_payload_is_explicit_and_contains_only_proven_fields(self) -> None:
        payload = provider_adapters.compile_seedance_payload(
            self.video_job(duration=5, ratio="9:16"),
            model="account-enabled-endpoint",
        )
        self.assertEqual(
            payload,
            {
                "model": "account-enabled-endpoint",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "slow push in as the evidence is revealed "
                            "--ratio 9:16 --dur 5"
                        ),
                    }
                ],
            },
        )
        self.assertNotIn("duration", payload)
        self.assertNotIn("ratio", payload)

    def test_seedance_fails_closed_on_unproven_or_unsafe_inputs(self) -> None:
        with self.assertRaisesRegex(ValueError, "explicitly configured"):
            provider_adapters.compile_seedance_payload(self.video_job(), model="")
        with self.assertRaisesRegex(ValueError, "supported profile"):
            provider_adapters.compile_seedance_payload(
                self.video_job(ratio="9:16 --seed 4"), model="configured"
            )

        referenced = self.video_job()
        referenced["references"] = ["输入/reference.png"]
        with self.assertRaisesRegex(ValueError, "HTTPS or asset"):
            provider_adapters.compile_seedance_payload(
                referenced,
                model="configured",
                reference_urls=["data:image/png;base64,AAAA"],
            )
        payload = provider_adapters.compile_seedance_payload(
            referenced,
            model="configured",
            reference_urls=["asset://asset-202608160001-example"],
        )
        self.assertEqual(payload["content"][1]["role"], "reference_image")
        adaptive = provider_adapters.compile_seedance_payload(
            self.video_job(ratio="adaptive"), model="configured"
        )
        self.assertTrue(adaptive["content"][0]["text"].endswith("--ratio adaptive"))

    def test_gpt_image_2_payload_matches_the_current_contract(self) -> None:
        payload = provider_adapters.compile_gpt_image_2_payload(
            self.image_job(size="1152x2048", quality="medium")
        )
        self.assertEqual(
            payload,
            {
                "model": "gpt-image-2",
                "prompt": "vertical character portrait",
                "n": 1,
                "output_format": "png",
                "size": "1152x2048",
                "quality": "medium",
            },
        )

    def test_gpt_image_2_rejects_unsupported_and_invalid_geometry(self) -> None:
        for parameters in (
            {"background": "transparent"},
            {"input_fidelity": "high"},
            {"size": "1023x1024"},
            {"size": "512x512"},
            {"size": "3840x3840"},
        ):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                provider_adapters.compile_gpt_image_2_payload(
                    self.image_job(**parameters)
                )

    def test_minimax_music_payload_is_music_3_and_never_invents_duration(self) -> None:
        payload = provider_adapters.compile_minimax_music_payload(
            self.music_job(is_instrumental=True)
        )
        self.assertEqual(
            payload,
            {
                "model": "music-3.0",
                "prompt": "restrained urban drama score",
                "stream": False,
                "output_format": "hex",
                "audio_setting": {
                    "sample_rate": 44100,
                    "bitrate": 256000,
                    "format": "mp3",
                },
                "lyrics_optimizer": False,
                "is_instrumental": True,
            },
        )
        self.assertNotIn("duration", payload)

    def test_minimax_rejects_tts_missing_lyrics_and_instrumental_lyrics(self) -> None:
        tts = self.music_job(is_instrumental=True)
        tts["modality"] = "tts"
        with self.assertRaisesRegex(ValueError, "music job"):
            provider_adapters.compile_minimax_music_payload(tts)
        with self.assertRaisesRegex(ValueError, "requires confirmed lyrics"):
            provider_adapters.compile_minimax_music_payload(self.music_job())
        with self.assertRaisesRegex(ValueError, "must not carry lyrics"):
            provider_adapters.compile_minimax_music_payload(
                self.music_job(is_instrumental=True, lyrics="not allowed")
            )
        with self.assertRaisesRegex(ValueError, "optimizer is forbidden"):
            provider_adapters.compile_minimax_music_payload(
                self.music_job(lyrics_optimizer=True)
            )


class ProviderRuntimeTests(unittest.TestCase):
    def test_http_failures_expose_only_stable_whitelisted_evidence(self) -> None:
        cases = (
            (401, "authentication", False),
            (429, "rate_limit", True),
            (503, "server", True),
        )
        for status, category, retryable in cases:
            with self.subTest(status=status):
                error = urllib.error.HTTPError(
                    "https://api.openai.com/v1/images/generations",
                    status,
                    "secret provider message",
                    {
                        "x-request-id": f"req_{status}",
                        "authorization": "Bearer credential-must-not-appear",
                    },
                    io.BytesIO(
                        json.dumps(
                            {
                                "error": {
                                    "code": "rate_limit_exceeded",
                                    "message": "credential-must-not-appear",
                                }
                            }
                        ).encode()
                    ),
                )
                public = provider_adapters._http_failure(
                    "gpt-image-2", error
                ).public("gpt-image-2")
                error.close()
                self.assertEqual(public["http_status"], status)
                self.assertEqual(public["category"], category)
                self.assertEqual(public["retryable"], retryable)
                self.assertEqual(public["code"], "rate_limit_exceeded")
                self.assertEqual(public["request_id"], f"req_{status}")
                self.assertNotIn("message", public)
                self.assertNotIn("credential", json.dumps(public))

    def test_each_runtime_maps_a_successful_offline_response(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            common_env = {
                "ARK_API_KEY": "ark-secret",
                "SEEDANCE_MODEL": "configured-endpoint",
                "OPENAI_API_KEY": "openai-secret",
                "MINIMAX_API_KEY": "minimax-secret",
            }
            with mock.patch.dict(os.environ, common_env, clear=False):
                with mock.patch.object(
                    provider_adapters,
                    "_request_json",
                    side_effect=[
                        ({"id": "seedance-task"}, {}),
                        (
                            {
                                "status": "succeeded",
                                "content": {"video_url": "https://cdn.example/shot.mp4"},
                            },
                            {},
                        ),
                    ],
                ), mock.patch.object(
                    provider_adapters,
                    "_download",
                    return_value=root / "shot.mp4",
                ):
                    path, task_id = provider_adapters._run_seedance(
                        {
                            "modality": "video",
                            "prompt": "camera holds",
                            "references": [],
                            "outputs": ["制作成果/shot.mp4"],
                            "parameters": {},
                            "project_root": str(root),
                        }
                    )
                    self.assertEqual((path, task_id), (root / "shot.mp4", "seedance-task"))

                with mock.patch.object(
                    provider_adapters,
                    "_request_json",
                    return_value=(
                        {
                            "data": [
                                {
                                    "b64_json": base64.b64encode(
                                        b"\x89PNG\r\n\x1a\ncontent"
                                    ).decode()
                                }
                            ]
                        },
                        {"x-request-id": "openai-request"},
                    ),
                ):
                    path, request_id = provider_adapters._run_openai(
                        {
                            "modality": "image",
                            "prompt": "portrait",
                            "references": [],
                            "outputs": ["制作成果/portrait.png"],
                            "parameters": {},
                            "project_root": str(root),
                        }
                    )
                    self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))
                    self.assertEqual(request_id, "openai-request")

                with mock.patch.object(
                    provider_adapters,
                    "_request_json",
                    return_value=(
                        {
                            "data": {"audio": b"ID3music".hex(), "status": 2},
                            "trace_id": "minimax-trace",
                            "base_resp": {"status_code": 0},
                        },
                        {},
                    ),
                ):
                    path, trace_id = provider_adapters._run_minimax(
                        {
                            "modality": "music",
                            "prompt": "score",
                            "references": [],
                            "outputs": ["制作成果/cue.mp3"],
                            "parameters": {"is_instrumental": True},
                            "project_root": str(root),
                        }
                    )
                    self.assertEqual(path.read_bytes(), b"ID3music")
                    self.assertEqual(trace_id, "minimax-trace")

    def test_seedance_runtime_refuses_unhosted_local_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "reference.png").write_bytes(b"PNG")
            with mock.patch.dict(
                os.environ,
                {"ARK_API_KEY": "secret", "SEEDANCE_MODEL": "configured"},
                clear=False,
            ):
                with self.assertRaisesRegex(
                    provider_adapters.AdapterFailure, "trusted HTTPS upload"
                ):
                    provider_adapters._run_seedance(
                        {
                            "modality": "video",
                            "prompt": "camera holds",
                            "references": ["reference.png"],
                            "outputs": ["制作成果/shot.mp4"],
                            "parameters": {},
                            "project_root": str(root),
                        }
                    )

    def test_provider_output_must_match_the_confirmed_media_type(self) -> None:
        with self.assertRaisesRegex(
            provider_adapters.AdapterFailure, "target media type"
        ):
            provider_adapters._temporary_output("制作成果/frame.png", b"not-a-png")

    def test_multipart_references_are_bounded_and_read_from_pinned_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reference.png"
            path.write_bytes(b"small-image")
            encoded, content_type = provider_adapters._multipart(
                {"model": "gpt-image-2"}, [path]
            )
            self.assertIn(b"small-image", encoded)
            self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
            with mock.patch.object(provider_adapters, "MAX_REFERENCE_BYTES", 4):
                with self.assertRaisesRegex(ValueError, "size limit"):
                    provider_adapters._multipart({}, [path])

    def test_cli_selftest_and_safe_failure_do_not_expose_credentials(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--selftest"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

        secret = "credential-must-not-appear"
        env = os.environ.copy()
        env["OPENAI_API_KEY"] = secret
        failed = subprocess.run(
            [sys.executable, str(SCRIPT), "gpt-image-2"],
            input=json.dumps({"modality": "video"}),
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(failed.returncode, 1)
        public = json.loads(failed.stdout)
        self.assertEqual(
            public,
            {
                "error": {
                    "provider": "gpt-image-2",
                    "category": "invalid_request",
                    "code": "invalid_job",
                    "retryable": False,
                }
            },
        )
        self.assertEqual(failed.stderr.strip(), "provider adapter failed safely")
        self.assertNotIn(secret, failed.stdout)
        self.assertNotIn(secret, failed.stderr)


if __name__ == "__main__":
    unittest.main()
