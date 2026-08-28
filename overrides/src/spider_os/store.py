from __future__ import annotations

import shutil
import subprocess
from typing import Any


def _run(command: list[str], timeout: float = 8.0) -> tuple[int, str, str]:
    if not shutil.which(command[0]):
        return 127, "", f"{command[0]} not installed"
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, "", str(error)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


class SpiderStore:
    """Flatpak-first application catalog for Spider OS.

    Discovery is read-only. Install, remove and update requests are emitted as
    approval plans so The Web never turns a store click into an invisible root or
    package-manager mutation.
    """

    name = "Spider Store"

    def snapshot(self) -> dict[str, Any]:
        available = bool(shutil.which("flatpak"))
        if not available:
            return {
                "name": self.name,
                "available": False,
                "installed": [],
                "remotes": [],
                "policy": self.policy(),
            }
        _, installed, _ = _run(
            ["flatpak", "list", "--app", "--columns=application,name,version,branch"]
        )
        _, remotes, _ = _run(["flatpak", "remotes", "--columns=name,url,filter"])
        return {
            "name": self.name,
            "available": True,
            "installed": self._rows(installed),
            "remotes": self._rows(remotes),
            "policy": self.policy(),
        }

    def search(self, query: str, limit: int = 25) -> dict[str, Any]:
        query = query.strip()
        if not query:
            raise ValueError("store search requires a query")
        if not shutil.which("flatpak"):
            return {"name": self.name, "query": query, "results": [], "available": False}
        code, output, error = _run(
            [
                "flatpak",
                "search",
                "--columns=application,name,description,version,branch,remotes",
                query,
            ],
            timeout=15.0,
        )
        if code != 0:
            return {
                "name": self.name,
                "query": query,
                "results": [],
                "available": True,
                "error": error or "Flatpak search failed",
            }
        return {
            "name": self.name,
            "query": query,
            "results": self._rows(output)[: max(1, min(limit, 100))],
            "available": True,
        }

    @staticmethod
    def policy() -> dict[str, Any]:
        return {
            "format_priority": ["flatpak", "web-app", "container"],
            "host_packages": "image-build-only",
            "automatic_install": False,
            "approval_required": True,
        }

    @staticmethod
    def action_plan(action: str, app_id: str = "", remote: str = "flathub") -> dict[str, Any]:
        app_id = app_id.strip()
        plans = {
            "install": ["flatpak", "install", remote or "flathub", app_id],
            "remove": ["flatpak", "uninstall", app_id],
            "update": ["flatpak", "update", app_id],
        }
        if action not in plans:
            raise ValueError("unknown store action")
        if not app_id:
            raise ValueError("an application id is required")
        return {
            "action": action,
            "app_id": app_id,
            "tier": "sensitive",
            "requires_approval": True,
            "command": plans[action],
            "executes": False,
        }

    @staticmethod
    def _rows(output: str) -> list[list[str]]:
        return [line.split("\t") for line in output.splitlines() if line.strip()]
