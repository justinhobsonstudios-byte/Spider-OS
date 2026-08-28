from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


SCRIPT = Path("system_files/usr/bin/spider-security-lab")


class KaliBayPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = SCRIPT.read_text(encoding="utf-8")

    def test_uses_official_kali_rolling_image(self) -> None:
        self.assertIn("image_name=docker.io/kalilinux/kali-rolling", self.script)

    def test_default_profile_has_no_added_capabilities(self) -> None:
        self.assertIn("local net_raw=false", self.script)
        self.assertIn("--cap-drop all", self.script)
        self.assertIn('if [ "$net_raw" = true ]; then', self.script)
        self.assertIn("create_args+=(--cap-add NET_RAW)", self.script)

    def test_net_raw_requires_explicit_interactive_phrase(self) -> None:
        self.assertIn("NET_RAW enablement requires an interactive terminal", self.script)
        self.assertIn("Type ENABLE NET_RAW to continue", self.script)
        self.assertIn("ENABLE NET_RAW", self.script)

    def test_launcher_requires_rootless_podman(self) -> None:
        self.assertIn("Kali Bay refuses to run as root", self.script)
        self.assertIn("Kali Bay requires rootless Podman", self.script)
        self.assertIn("{{.Host.Security.Rootless}}", self.script)

    def test_container_creation_has_no_host_escape_options(self) -> None:
        create_block = self.script.split("local -a create_args=(", 1)[1].split("podman create", 1)[0]
        self.assertNotIn("--privileged", create_block)
        self.assertNotIn("--network host", create_block)
        self.assertNotIn("--device", create_block)
        self.assertNotIn("--volume", create_block)
        self.assertNotIn(" -v ", create_block)

    def test_help_is_available_without_starting_podman(self) -> None:
        result = subprocess.run(
            ["bash", str(SCRIPT), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Kali Bay", result.stdout)
        self.assertIn("--net-raw", result.stdout)


if __name__ == "__main__":
    unittest.main()
