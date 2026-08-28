from __future__ import annotations

import shutil
import subprocess
from typing import Any


def _run(command: list[str], timeout: float = 3.0) -> tuple[int, str, str]:
    if not shutil.which(command[0]):
        return 127, "", f"{command[0]} not installed"
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class SpiderStudio:
    """Creative-workstation capability view for Studio mode.

    Ubuntu Studio is a workflow reference only. Runtime detection and plans here
    target Spider OS's Fedora/Aurora + PipeWire foundation.
    """

    name = "Spider Studio"

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "audio": self._audio(),
            "midi": self._midi(),
            "creative_apps": self._apps(),
            "policy": {
                "foundation": "PipeWire",
                "jack_compatibility": True,
                "base_distribution": "Aurora/Fedora",
                "ubuntu_studio_role": "workflow-reference-only",
                "automatic_device_reconfiguration": False,
            },
        }

    def _audio(self) -> dict[str, Any]:
        code, output, _ = _run(["pw-metadata", "-n", "settings", "0"])
        return {
            "pipewire": bool(shutil.which("pipewire")) or bool(shutil.which("pw-cli")),
            "pipewire_tools": bool(shutil.which("pw-cli")),
            "jack_compat": bool(shutil.which("pw-jack")),
            "rtkit": bool(shutil.which("rtkitctl")) or bool(shutil.which("rtkit-daemon")),
            "settings": output.splitlines() if code == 0 else [],
        }

    def _midi(self) -> dict[str, Any]:
        code, output, _ = _run(["aconnect", "-l"])
        return {
            "available": code == 0,
            "ports": output.splitlines() if code == 0 else [],
        }

    @staticmethod
    def _apps() -> list[dict[str, Any]]:
        candidates = [
            ("Ardour", "ardour8", "ardour"),
            ("REAPER", "reaper"),
            ("Audacity", "audacity"),
            ("OBS Studio", "obs"),
            ("Kdenlive", "kdenlive"),
            ("GIMP", "gimp"),
            ("Inkscape", "inkscape"),
        ]
        apps: list[dict[str, Any]] = []
        for candidate in candidates:
            name, *commands = candidate
            command = next((item for item in commands if shutil.which(item)), None)
            apps.append({"name": name, "installed": command is not None, "command": command})
        return apps

    @staticmethod
    def action_plan(action: str, command: str | None = None) -> dict[str, Any]:
        if action == "open-app":
            if not command or not shutil.which(command):
                raise ValueError("studio application is not installed")
            return {
                "action": action,
                "tier": "routine",
                "requires_approval": False,
                "command": [command],
                "executes": False,
            }
        if action == "low-latency-profile":
            return {
                "action": action,
                "tier": "sensitive",
                "requires_approval": True,
                "description": "Tune PipeWire quantum and scheduling for a Studio session, then restore defaults when Studio mode exits.",
                "executes": False,
            }
        raise ValueError("unknown studio action")
