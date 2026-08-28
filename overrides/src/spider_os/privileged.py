from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PrivilegedAction:
    name: str
    helper_verb: str
    description: str
    reversible: bool


ACTIONS: dict[str, PrivilegedAction] = {
    "update": PrivilegedAction(
        name="update",
        helper_verb="update",
        description="Stage the latest signed Spider OS bootc image for the next boot.",
        reversible=True,
    ),
    "rollback": PrivilegedAction(
        name="rollback",
        helper_verb="rollback",
        description="Queue the previous bootc deployment as the next boot target.",
        reversible=True,
    ),
    "reboot": PrivilegedAction(
        name="reboot",
        helper_verb="reboot",
        description="Restart the computer.",
        reversible=False,
    ),
}


class PrivilegedExecutor:
    """Cross the root boundary only through the Spider OS Polkit helper.

    The resident AI and local HTTP service remain unprivileged. Execution always
    goes through pkexec, where the desktop Polkit agent performs the final human
    authorization. No caller-supplied command, path, environment, or shell text is
    accepted here.
    """

    helper_path = "/usr/libexec/spider-os-privileged-control"

    @classmethod
    def action(cls, name: str) -> PrivilegedAction:
        try:
            return ACTIONS[name]
        except KeyError as error:
            raise ValueError(f"unknown privileged action: {name}") from error

    @classmethod
    def command(cls, name: str) -> list[str]:
        action = cls.action(name)
        return ["pkexec", cls.helper_path, action.helper_verb]

    @classmethod
    def status(cls) -> dict[str, Any]:
        return {
            "name": "Spider Privileged Action Broker",
            "available": bool(shutil.which("pkexec")) and shutil.which(cls.helper_path) is not None,
            "helper": cls.helper_path,
            "transport": "polkit/pkexec",
            "arbitrary_shell": False,
            "accepted_actions": list(ACTIONS),
            "human_authorization_at_execution": True,
        }

    @classmethod
    def execute(cls, name: str, timeout: float = 1800.0) -> dict[str, Any]:
        command = cls.command(name)
        if not shutil.which("pkexec"):
            raise RuntimeError("pkexec is not installed")
        if not shutil.which(cls.helper_path):
            raise RuntimeError("Spider OS privileged helper is not installed")
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("privileged action timed out") from error
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "authorization or action failed").strip()
            raise RuntimeError(detail[:500])
        return {
            "action": name,
            "executed": True,
            "exit_code": result.returncode,
            "output": result.stdout.strip()[:2000],
        }
