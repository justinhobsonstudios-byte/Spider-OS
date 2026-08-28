from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any


def _run(command: list[str], timeout: float = 4.0) -> tuple[int, str, str]:
    if not shutil.which(command[0]):
        return 127, "", f"{command[0]} not installed"
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class SystemControl:
    """Read-mostly system/recovery/update backend for Spider Control Center.

    Mutating operations are intentionally returned as approval plans. Webbie or the
    UI can present them to the Action Broker instead of getting a magical root shell.
    """

    def snapshot(self) -> dict[str, Any]:
        return {
            "name": "Spider Control Center",
            "deployment": self.deployment_status(),
            "flatpak": self.flatpak_status(),
            "recovery": self.recovery_capabilities(),
            "updates": self.update_capabilities(),
        }

    def deployment_status(self) -> dict[str, Any]:
        code, out, err = _run(["bootc", "status", "--json"])
        if code == 0 and out:
            try:
                return {"provider": "bootc", "ready": True, "data": json.loads(out)}
            except json.JSONDecodeError:
                return {"provider": "bootc", "ready": True, "text": out}
        code, out, err2 = _run(["rpm-ostree", "status", "--json"])
        if code == 0 and out:
            try:
                return {"provider": "rpm-ostree", "ready": True, "data": json.loads(out)}
            except json.JSONDecodeError:
                return {"provider": "rpm-ostree", "ready": True, "text": out}
        return {"provider": None, "ready": False, "error": err2 or err}

    def flatpak_status(self) -> dict[str, Any]:
        code, remotes, _ = _run(["flatpak", "remotes", "--columns=name,url"])
        code2, installed, _ = _run(["flatpak", "list", "--app", "--columns=application,name"])
        return {
            "available": code != 127,
            "remotes": remotes.splitlines() if code == 0 else [],
            "installed": installed.splitlines() if code2 == 0 else [],
        }

    @staticmethod
    def recovery_capabilities() -> dict[str, Any]:
        return {
            "atomic_rollback": True,
            "last_known_good": True,
            "factory_reset": "planned",
            "operations_require_confirmation": True,
        }

    @staticmethod
    def update_capabilities() -> dict[str, Any]:
        return {
            "channels": ["stable", "preview", "developer"],
            "default_channel": "stable",
            "automatic_downloads": True,
            "automatic_reboot": False,
            "rollback_available": True,
        }

    @staticmethod
    def action_plan(action: str) -> dict[str, Any]:
        plans = {
            "update": {"tier": "sensitive", "reversible": True, "command": ["bootc", "upgrade"]},
            "rollback": {"tier": "critical", "reversible": True, "command": ["bootc", "rollback"]},
            "reboot": {"tier": "sensitive", "reversible": False, "command": ["systemctl", "reboot"]},
        }
        if action not in plans:
            raise ValueError(f"unknown system action: {action}")
        return {"action": action, "requires_approval": True, **plans[action]}
