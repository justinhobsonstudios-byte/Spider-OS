from __future__ import annotations

import unittest
from pathlib import Path

from spider_os.cli import build_parser
from spider_os.privileged import ACTIONS, PrivilegedExecutor
from spider_os.system_control import SystemControl


class PrivilegedActionPolicyTests(unittest.TestCase):
    def test_only_fixed_system_actions_exist(self) -> None:
        self.assertEqual(set(ACTIONS), {"update", "rollback", "reboot"})
        self.assertEqual(
            PrivilegedExecutor.command("update"),
            ["pkexec", "/usr/libexec/spider-os-privileged-control", "update"],
        )
        with self.assertRaises(ValueError):
            PrivilegedExecutor.command("shell")

    def test_plans_never_execute_implicitly(self) -> None:
        for action in ACTIONS:
            plan = SystemControl.action_plan(action)
            self.assertTrue(plan["requires_approval"])
            self.assertFalse(plan["executes"])
            self.assertEqual(plan["authorization"], "polkit-admin-at-execution")
            self.assertFalse(plan["arbitrary_shell"])

    def test_cli_requires_explicit_execute_verb(self) -> None:
        parser = build_parser()
        planned = parser.parse_args(["system", "plan", "update"])
        executing = parser.parse_args(["system", "execute", "update"])
        self.assertEqual(planned.operation, "plan")
        self.assertEqual(executing.operation, "execute")
        self.assertEqual(executing.action, "update")

    def test_root_helper_has_no_arbitrary_command_surface(self) -> None:
        helper = Path("system_files/usr/libexec/spider-os-privileged-control").read_text(encoding="utf-8")
        self.assertIn("exec /usr/bin/bootc upgrade", helper)
        self.assertIn("exec /usr/bin/bootc rollback", helper)
        self.assertIn("exec /usr/bin/systemctl reboot", helper)
        self.assertIn("PKEXEC_UID", helper)
        self.assertNotIn("eval ", helper)
        self.assertNotIn("bash -c", helper)
        self.assertNotIn("sh -c", helper)

    def test_polkit_policy_is_per_action_and_not_cached(self) -> None:
        policy = Path("system_files/usr/share/polkit-1/actions/com.spideros.control.policy").read_text(
            encoding="utf-8"
        )
        for action in ACTIONS:
            self.assertIn(f'id="com.spideros.control.{action}"', policy)
            self.assertIn(
                f'<annotate key="org.freedesktop.policykit.exec.argv1">{action}</annotate>',
                policy,
            )
        self.assertEqual(policy.count("<allow_active>auth_admin</allow_active>"), 3)
        self.assertNotIn("auth_admin_keep", policy)
        self.assertNotIn("allow_gui", policy)


if __name__ == "__main__":
    unittest.main()
