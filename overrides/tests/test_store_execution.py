from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from spider_os.cli import build_parser
from spider_os.db import Database
from spider_os.platform import install_server_extensions
from spider_os.server import create_server
from spider_os.store import FLATHUB_URL, SpiderStore


class SpiderStoreExecutionTests(unittest.TestCase):
    def test_plan_is_per_user_and_noninteractive(self) -> None:
        plan = SpiderStore.action_plan("install", "org.example.App")
        self.assertEqual(
            plan["command"],
            [
                "flatpak", "install", "--user", "--noninteractive", "--assumeyes",
                "flathub", "org.example.App",
            ],
        )
        self.assertEqual(plan["scope"], "user")
        self.assertFalse(plan["executes"])

    def test_app_id_and_remote_cannot_become_options(self) -> None:
        bad_app_ids = [
            "--system",
            "org.example.App --system",
            "org.example.App\n--system",
            "org.example",
            "-org.example.App",
        ]
        for value in bad_app_ids:
            with self.subTest(value=value), self.assertRaises(ValueError):
                SpiderStore.action_plan("install", value)
        for remote in ["--system", "flathub other", "flathub\n--system"]:
            with self.subTest(remote=remote), self.assertRaises(ValueError):
                SpiderStore.action_plan("install", "org.example.App", remote)

    @patch("spider_os.store.shutil.which", return_value="/usr/bin/flatpak")
    @patch("spider_os.store._run")
    def test_snapshot_reads_only_the_user_installation(self, run, _which) -> None:
        run.side_effect = [
            (0, "org.example.App\tExample\t1.0\tstable", ""),
            (0, "flathub\thttps://dl.flathub.org/repo/\t", ""),
        ]

        snapshot = SpiderStore().snapshot()

        self.assertTrue(snapshot["available"])
        self.assertEqual(
            run.call_args_list[0].args[0],
            [
                "flatpak", "list", "--user", "--app",
                "--columns=application,name,version,branch",
            ],
        )
        self.assertEqual(
            run.call_args_list[1].args[0],
            ["flatpak", "remotes", "--user", "--columns=name,url,filter"],
        )

    @patch("spider_os.store.shutil.which", return_value="/usr/bin/flatpak")
    @patch("spider_os.store._run")
    def test_install_configures_user_flathub_then_executes_exact_plan(self, run, _which) -> None:
        run.side_effect = [(0, "", ""), (0, "installed", "")]
        result = SpiderStore.execute("install", "org.example.App")
        self.assertTrue(result["executed"])
        self.assertEqual(result["scope"], "user")
        self.assertEqual(run.call_count, 2)
        self.assertEqual(
            run.call_args_list[0].args[0],
            [
                "flatpak", "remote-add", "--user", "--if-not-exists",
                "flathub", FLATHUB_URL,
            ],
        )
        self.assertEqual(
            run.call_args_list[1].args[0],
            [
                "flatpak", "install", "--user", "--noninteractive", "--assumeyes",
                "flathub", "org.example.App",
            ],
        )

    @patch("spider_os.store.shutil.which", return_value="/usr/bin/flatpak")
    def test_execute_rejects_automatic_non_flathub_install(self, _which) -> None:
        with self.assertRaises(ValueError):
            SpiderStore.execute("install", "org.example.App", "otherremote")

    def test_cli_separates_plan_from_execute(self) -> None:
        parser = build_parser()
        planned = parser.parse_args(["store", "plan", "org.example.App", "--action", "install"])
        executing = parser.parse_args(["store", "execute", "org.example.App", "--action", "install"])
        self.assertEqual(planned.operation, "plan")
        self.assertEqual(executing.operation, "execute")
        self.assertEqual(executing.value, "org.example.App")


class SpiderStoreApiExecutionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.previous_data_dir = os.environ.get("SPIDER_OS_DATA_DIR")
        os.environ["SPIDER_OS_DATA_DIR"] = self.temp.name
        install_server_extensions()
        self.server, _ = create_server("127.0.0.1", 0, Database(Path(self.temp.name)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base = f"http://{host}:{port}"
        with urllib.request.urlopen(self.base + "/api/bootstrap", timeout=5) as response:
            self.token = json.load(response)["csrf_token"]

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.previous_data_dir is None:
            os.environ.pop("SPIDER_OS_DATA_DIR", None)
        else:
            os.environ["SPIDER_OS_DATA_DIR"] = self.previous_data_dir
        self.temp.cleanup()

    def post(self, body: dict) -> dict:
        request = urllib.request.Request(
            self.base + "/api/store/execute",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Spider-Token": self.token},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    @patch("spider_os.platform.SpiderStore.execute")
    def test_execute_endpoint_requires_exact_app_id_confirmation(self, execute) -> None:
        request = urllib.request.Request(
            self.base + "/api/store/execute",
            data=json.dumps({
                "action": "install",
                "app_id": "org.example.App",
                "confirmation": "org.example.Other",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Spider-Token": self.token},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(request, timeout=5)
        self.assertEqual(caught.exception.code, 400)
        execute.assert_not_called()

    @patch("spider_os.platform.SpiderStore.execute")
    def test_execute_endpoint_calls_store_only_after_confirmation(self, execute) -> None:
        execute.return_value = {
            "action": "install",
            "app_id": "org.example.App",
            "scope": "user",
            "executed": True,
        }
        payload = self.post({
            "action": "install",
            "app_id": "org.example.App",
            "remote": "flathub",
            "confirmation": "org.example.App",
        })
        self.assertTrue(payload["result"]["executed"])
        execute.assert_called_once_with("install", "org.example.App", "flathub")


if __name__ == "__main__":
    unittest.main()
