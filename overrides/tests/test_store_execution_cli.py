from __future__ import annotations

import unittest

from spider_os.cli import build_parser
from spider_os.store import SpiderStore


class SpiderStoreExecutionCliTests(unittest.TestCase):
    def test_execute_is_explicit_cli_operation(self) -> None:
        args = build_parser().parse_args([
            "store", "execute", "org.example.App", "--action", "install"
        ])
        self.assertEqual(args.command, "store")
        self.assertEqual(args.operation, "execute")
        self.assertEqual(args.value, "org.example.App")
        self.assertEqual(args.action, "install")

    def test_plan_remains_non_executing(self) -> None:
        plan = SpiderStore.action_plan("install", "org.example.App")
        self.assertFalse(plan["executes"])
        self.assertTrue(plan["requires_approval"])


if __name__ == "__main__":
    unittest.main()
