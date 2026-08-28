from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from spider_os.db import Database
from spider_os.model_router import ModelRouter
from spider_os.modes import ModeManager
from spider_os.platform import install_server_extensions
from spider_os.server import create_server
from spider_os.setup import SetupStore
from spider_os.store import SpiderStore
from spider_os.studio import SpiderStudio
from spider_os.sync import SpiderSync
from spider_os.vault import SpiderVault
from spider_os.voice import VoiceRuntime


class SpiderServicePolicyTests(unittest.TestCase):
    def test_store_mutations_are_plans(self) -> None:
        plan = SpiderStore.action_plan("install", "org.example.App")
        self.assertTrue(plan["requires_approval"])
        self.assertFalse(plan["executes"])
        self.assertEqual(plan["command"][:3], ["flatpak", "install", "flathub"])

    def test_vault_never_places_secret_values_in_spider_state(self) -> None:
        policy = SpiderVault.policy()
        self.assertFalse(policy["secret_values_in_spider_database"])
        self.assertFalse(policy["secret_values_in_webbie_memory"])
        self.assertFalse(policy["secret_values_in_logs"])
        self.assertFalse(policy["secret_values_in_platform_api"])

    def test_sync_is_off_by_default_and_does_not_fake_encryption(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            sync = SpiderSync(Path(root))
            status = sync.status()
            self.assertFalse(status["enabled"])
            self.assertEqual(status["provider"], "none")
            self.assertTrue(status["security"]["encryption_required"])
            self.assertFalse(status["security"]["encryption_verified"])
            changed = sync.configure(
                enabled=True,
                provider="local-folder",
                endpoint=str(Path(root) / "mirror"),
            )
            self.assertTrue(changed["enabled"])
            self.assertEqual(changed["credentials"], "Spider Vault")
            plan = sync.action_plan("sync-now")
            self.assertFalse(plan["ready"])
            self.assertFalse(plan["security"]["encryption_verified"])

    def test_webdav_rejects_plain_http(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            sync = SpiderSync(Path(root))
            with self.assertRaises(ValueError):
                sync.configure(
                    enabled=True,
                    provider="webdav",
                    endpoint="http://example.test/dav",
                )

    def test_setup_applies_selected_default_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            data_dir = Path(root)
            saved = SetupStore(data_dir).write(
                {
                    "default_mode": "studio",
                    "authority": "graduated",
                    "voice_enabled": True,
                    "screen_awareness": True,
                    "learn_user": True,
                    "learn_studies": True,
                    "learn_internet": True,
                    "proactive_level": "very-high",
                }
            )
            self.assertEqual(saved["active_mode"], "studio")
            active = ModeManager(data_dir).current()
            self.assertEqual(active["mode"], "studio")
            self.assertEqual(active["address_name"], "Justin")
            self.assertEqual(active["actor"], "setup")

    def test_model_router_keeps_restricted_context_local(self) -> None:
        self.assertEqual(ModelRouter.policy()["restricted"], "local-only")
        self.assertFalse(ModelRouter.policy()["cloud_restricted_context"])

    def test_voice_wake_detection_is_local_only(self) -> None:
        policy = VoiceRuntime.policy()
        self.assertEqual(policy["wake_detection"], "local-only")
        self.assertFalse(policy["ambient_audio_stored"])
        self.assertFalse(policy["non_addressed_speech_stored"])

    def test_voice_wake_phrase_extracts_only_addressed_commands(self) -> None:
        self.assertEqual(VoiceRuntime._command_after_wake("hey webbie open studio"), "open studio")
        self.assertEqual(VoiceRuntime._command_after_wake("Webbie"), "")
        self.assertEqual(VoiceRuntime._command_after_wake("web show my anchors"), "show my anchors")
        self.assertIsNone(VoiceRuntime._command_after_wake("the web is open"))

    def test_studio_low_latency_changes_need_approval(self) -> None:
        plan = SpiderStudio.action_plan("low-latency-profile")
        self.assertTrue(plan["requires_approval"])
        self.assertFalse(plan["executes"])


class SpiderServiceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.previous_data_dir = os.environ.get("SPIDER_OS_DATA_DIR")
        os.environ["SPIDER_OS_DATA_DIR"] = self.temp.name
        install_server_extensions()
        database = Database(Path(self.temp.name))
        self.server, _ = create_server("127.0.0.1", 0, database)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = "http://" + host + ":" + str(port)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.previous_data_dir is None:
            os.environ.pop("SPIDER_OS_DATA_DIR", None)
        else:
            os.environ["SPIDER_OS_DATA_DIR"] = self.previous_data_dir
        self.temp.cleanup()

    def get_json(self, path: str) -> dict:
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return json.load(response)

    def post_json(self, path: str, body: dict, token: str) -> dict:
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Spider-Token": token,
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_service_status_endpoints(self) -> None:
        self.assertEqual(self.get_json("/api/vault")["vault"]["name"], "Spider Vault")
        self.assertEqual(self.get_json("/api/sync")["sync"]["name"], "Spider Sync")
        self.assertEqual(self.get_json("/api/voice")["voice"]["name"], "Webbie Voice Runtime")
        self.assertEqual(self.get_json("/api/studio")["studio"]["name"], "Spider Studio")
        self.assertEqual(self.get_json("/api/store")["store"]["name"], "Spider Store")

    def test_store_install_endpoint_returns_plan_only(self) -> None:
        token = self.get_json("/api/bootstrap")["csrf_token"]
        result = self.post_json(
            "/api/store/plan",
            {"action": "install", "app_id": "org.example.App"},
            token,
        )["plan"]
        self.assertTrue(result["requires_approval"])
        self.assertFalse(result["executes"])

    def test_sync_configuration_endpoint_requires_verified_encryption(self) -> None:
        token = self.get_json("/api/bootstrap")["csrf_token"]
        result = self.post_json(
            "/api/sync/configure",
            {"enabled": False, "provider": "none"},
            token,
        )["sync"]
        self.assertFalse(result["enabled"])
        self.assertTrue(result["security"]["encryption_required"])
        self.assertFalse(result["security"]["encryption_verified"])
        self.assertEqual(result["credentials"], "Spider Vault")


if __name__ == "__main__":
    unittest.main()
