from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from spider_os.db import Database
from spider_os.server import create_server


class ServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
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
        self.temp.cleanup()

    def get_json(self, path: str) -> dict:
        with urllib.request.urlopen(self.base + path, timeout=3) as response:
            return json.load(response)

    def test_health_and_bootstrap(self) -> None:
        health = self.get_json("/api/health")
        self.assertEqual(health["status"], "ok")
        bootstrap = self.get_json("/api/bootstrap")
        self.assertEqual(bootstrap["guardrails"]["authority_model"], "graduated")
        self.assertTrue(bootstrap["guardrails"]["routine_reversible_actions_may_auto_execute"])
        self.assertTrue(bootstrap["guardrails"]["sensitive_actions_require_confirmation"])
        self.assertTrue(bootstrap["guardrails"]["critical_actions_require_explicit_approval"])
        self.assertEqual(bootstrap["learning"]["streams"], {"user": True, "study": True, "internet": True})
        self.assertFalse(bootstrap["guardrails"]["arbitrary_shell_access"])

    def test_mutation_requires_token(self) -> None:
        request = urllib.request.Request(
            self.base + "/api/items",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(context.exception.code, 403)

    def test_create_item_with_token(self) -> None:
        bootstrap = self.get_json("/api/bootstrap")
        request = urllib.request.Request(
            self.base + "/api/items",
            data=json.dumps(
                {
                    "space_id": "social-work",
                    "kind": "task",
                    "title": "Review field placement requirements",
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Spider-Token": bootstrap["csrf_token"],
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=3) as response:
            created = json.load(response)
        self.assertEqual(created["item"]["space_id"], "social-work")


if __name__ == "__main__":
    unittest.main()

