from __future__ import annotations

import unittest
from unittest.mock import patch

from spider_os.cli import build_parser
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


if __name__ == "__main__":
    unittest.main()
