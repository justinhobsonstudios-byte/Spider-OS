from __future__ import annotations

import os
import shutil
from typing import Any


class SpiderVault:
    """Credential-store capability layer without home-grown cryptography.

    Spider Vault intentionally delegates secret storage to a desktop secret-service
    implementation such as KWallet/Secret Service. Secret values are never stored in
    Spider Core's SQLite database, platform JSON state, logs, or Webbie memory.
    """

    name = "Spider Vault"

    def status(self) -> dict[str, Any]:
        provider = self._provider()
        return {
            "name": self.name,
            "available": provider is not None,
            "provider": provider,
            "session_bus": bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS")),
            "policy": self.policy(),
        }

    @staticmethod
    def policy() -> dict[str, Any]:
        return {
            "secret_values_in_spider_database": False,
            "secret_values_in_webbie_memory": False,
            "secret_values_in_logs": False,
            "secret_values_in_platform_api": False,
            "credential_actions": "critical-explicit",
            "desktop_secret_service_required": True,
        }

    def action_plan(self, action: str) -> dict[str, Any]:
        provider = self._provider()
        if action != "open-manager":
            raise ValueError("unknown vault action")
        if provider == "kwalletmanager6":
            command = ["kwalletmanager6"]
        elif provider == "kwalletmanager5":
            command = ["kwalletmanager5"]
        else:
            command = []
        return {
            "action": action,
            "provider": provider,
            "available": bool(command),
            "tier": "sensitive",
            "requires_approval": True,
            "command": command,
            "executes": False,
        }

    @staticmethod
    def _provider() -> str | None:
        for command in ("kwalletmanager6", "kwalletmanager5", "secret-tool"):
            if shutil.which(command):
                return command
        return None
