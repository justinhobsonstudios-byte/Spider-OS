from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any


FLATHUB_URL = "https://dl.flathub.org/repo/flathub.flatpakrepo"
APP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*(?:\.[A-Za-z0-9][A-Za-z0-9_-]*){2,}$")
REMOTE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


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
    """Flatpak-first application catalog and user-scoped installer.

    Spider Store never mutates the atomic host package set. Explicit execution uses
    Flatpak's per-user installation so applications live under the user's Flatpak
    installation rather than modifying the Spider OS bootc image.
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
            ["flatpak", "list", "--user", "--app", "--columns=application,name,version,branch"]
        )
        _, remotes, _ = _run(["flatpak", "remotes", "--user", "--columns=name,url,filter"])
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
        if len(query) > 200 or any(ord(char) < 32 for char in query):
            raise ValueError("invalid store search query")
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
            "flatpak_scope": "user",
            "automatic_install": False,
            "approval_required": True,
            "arbitrary_command": False,
        }

    @classmethod
    def action_plan(cls, action: str, app_id: str = "", remote: str = "flathub") -> dict[str, Any]:
        app_id = cls._validate_app_id(app_id)
        remote = cls._validate_remote(remote)
        plans = {
            "install": [
                "flatpak", "install", "--user", "--noninteractive", "--assumeyes", remote, app_id,
            ],
            "remove": [
                "flatpak", "uninstall", "--user", "--noninteractive", "--assumeyes", app_id,
            ],
            "update": [
                "flatpak", "update", "--user", "--noninteractive", "--assumeyes", app_id,
            ],
        }
        if action not in plans:
            raise ValueError("unknown store action")
        return {
            "action": action,
            "app_id": app_id,
            "remote": remote,
            "tier": "sensitive",
            "requires_approval": True,
            "command": plans[action],
            "scope": "user",
            "executes": False,
            "arbitrary_command": False,
        }

    @classmethod
    def execute(cls, action: str, app_id: str, remote: str = "flathub") -> dict[str, Any]:
        plan = cls.action_plan(action, app_id, remote)
        if not shutil.which("flatpak"):
            raise RuntimeError("Flatpak is not installed")

        # Spider Store's execution surface is intentionally limited to the stable
        # Flathub remote. Other remotes may be searched/read but require manual setup.
        if action == "install" and plan["remote"] != "flathub":
            raise ValueError("automatic Store installs currently support only Flathub")
        if action == "install":
            code, _, error = _run(
                [
                    "flatpak", "remote-add", "--user", "--if-not-exists",
                    "flathub", FLATHUB_URL,
                ],
                timeout=60.0,
            )
            if code != 0:
                raise RuntimeError(error or "could not configure the user Flathub remote")

        code, output, error = _run(plan["command"], timeout=1800.0)
        if code != 0:
            raise RuntimeError((error or output or "Flatpak action failed")[:1000])
        return {
            "action": action,
            "app_id": plan["app_id"],
            "scope": "user",
            "executed": True,
            "exit_code": code,
            "output": output[:4000],
        }

    @staticmethod
    def _validate_app_id(value: str) -> str:
        app_id = value.strip()
        if len(app_id) > 255 or not APP_ID_RE.fullmatch(app_id):
            raise ValueError("invalid Flatpak application id")
        return app_id

    @staticmethod
    def _validate_remote(value: str) -> str:
        remote = (value or "flathub").strip()
        if not REMOTE_RE.fullmatch(remote):
            raise ValueError("invalid Flatpak remote name")
        return remote

    @staticmethod
    def _rows(output: str) -> list[list[str]]:
        return [line.split("\t") for line in output.splitlines() if line.strip()]
