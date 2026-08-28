from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from spider_os.db import Database
from spider_os.platform import install_server_extensions
from spider_os.server import create_server


class PlatformServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.previous_data_dir = os.environ.get("SPIDER_OS_DATA_DIR")
        os.environ["SPIDER_OS_DATA_DIR"] = self.temp.name
        install_server_extensions()
        database = Database(Path(self.temp.name))
        self.server, self.application = create_server("127.0.0.1", 0, database)
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

    def test_bootstrap_exposes_canonical_platform_identity(self) -> None:
        bootstrap = self.get_json("/api/bootstrap")
        platform = bootstrap["platform"]
        self.assertEqual(platform["desktop"], "The Web")
        self.assertEqual(platform["resident_ai"], "Webbie")
        self.assertEqual(platform["startup"], "Web Assembly")
        self.assertEqual(platform["devices"]["name"], "Device Web")

    def test_mode_switch_is_token_protected_and_persistent(self) -> None:
        bootstrap = self.get_json("/api/bootstrap")
        with self.assertRaises(urllib.error.HTTPError) as context:
            request = urllib.request.Request(
                self.base + "/api/mode",
                data=b'{"mode":"studio"}',
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(context.exception.code, 403)

        changed = self.post_json(
            "/api/mode",
            {"mode": "studio"},
            bootstrap["csrf_token"],
        )
        self.assertEqual(changed["mode"]["mode"], "studio")
        self.assertEqual(changed["mode"]["address_name"], "Justin")
        current = self.get_json("/api/mode")
        self.assertEqual(current["mode"]["mode"], "studio")

    def test_system_actions_only_return_approval_plans(self) -> None:
        bootstrap = self.get_json("/api/bootstrap")
        plan = self.post_json(
            "/api/system/plan",
            {"action": "rollback"},
            bootstrap["csrf_token"],
        )["plan"]
        self.assertTrue(plan["requires_approval"])
        self.assertEqual(plan["tier"], "critical")
        self.assertEqual(plan["command"], ["bootc", "rollback"])

    def test_cached_device_endpoint_does_not_require_hardware_tools(self) -> None:
        devices = self.get_json("/api/devices")["devices"]
        self.assertEqual(devices["name"], "Device Web")
        self.assertIn("network", devices)
        self.assertIn("audio", devices)


if __name__ == "__main__":
    unittest.main()
