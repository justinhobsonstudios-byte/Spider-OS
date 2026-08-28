from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .db import default_data_dir


class SpiderSync:
    """Provider-neutral sync configuration for Spider OS.

    Sync is off by default. This module stores policy and provider selection only,
    never provider passwords or tokens. Credentials belong in Spider Vault.

    Encryption is a hard requirement for remote sync, but this layer does not claim
    that a provider is encrypted until provider-specific verification exists.
    """

    name = "Spider Sync"
    providers = {"none", "local-folder", "syncthing", "webdav"}
    scopes = {
        "settings",
        "anchors",
        "threads",
        "knowledge",
        "studio",
    }

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.path = self.data_dir / "sync.json"

    def status(self) -> dict[str, Any]:
        config = self.read()
        return {
            "name": self.name,
            **config,
            "credentials": "Spider Vault",
            "security": self._security(config),
        }

    def read(self) -> dict[str, Any]:
        defaults = {
            "enabled": False,
            "provider": "none",
            "scopes": ["settings", "anchors", "threads"],
            "endpoint": None,
            "conflict_policy": "keep-both",
        }
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                # Ignore the legacy boolean `encrypted` field. Earlier builds used
                # it as an intention flag, which was too easy to misread as proof.
                payload.pop("encrypted", None)
                defaults.update(payload)
        except (OSError, json.JSONDecodeError):
            pass
        return defaults

    def configure(
        self,
        *,
        enabled: bool,
        provider: str,
        scopes: list[str] | None = None,
        endpoint: str | None = None,
    ) -> dict[str, Any]:
        if provider not in self.providers:
            raise ValueError("unsupported sync provider")
        requested_scopes = scopes or ["settings", "anchors", "threads"]
        unknown = set(requested_scopes).difference(self.scopes)
        if unknown:
            raise ValueError("unknown sync scope: " + ", ".join(sorted(unknown)))
        if enabled and provider == "none":
            raise ValueError("sync cannot be enabled without a provider")
        if provider == "local-folder" and enabled and not endpoint:
            raise ValueError("local-folder sync requires a destination")
        if provider == "webdav" and enabled and endpoint and not endpoint.lower().startswith("https://"):
            raise ValueError("WebDAV sync requires an HTTPS endpoint")
        payload = {
            "enabled": bool(enabled),
            "provider": provider,
            "scopes": sorted(set(requested_scopes)),
            "endpoint": endpoint if endpoint else None,
            "conflict_policy": "keep-both",
        }
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        old_umask = os.umask(0o077)
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
            self.path.chmod(0o600)
        finally:
            os.umask(old_umask)
        return self.status()

    def action_plan(self, action: str) -> dict[str, Any]:
        if action not in {"sync-now", "pause"}:
            raise ValueError("unknown sync action")
        config = self.read()
        security = self._security(config)
        ready = bool(config["enabled"] and config["provider"] != "none")
        if action == "sync-now" and not security["encryption_verified"]:
            ready = False
        return {
            "action": action,
            "provider": config["provider"],
            "enabled": config["enabled"],
            "tier": "sensitive" if action == "sync-now" else "routine",
            "requires_approval": action == "sync-now",
            "executes": False,
            "ready": ready,
            "security": security,
            "reason": (
                None
                if ready or action == "pause"
                else "sync remains blocked until provider encryption is verified"
            ),
        }

    @staticmethod
    def _security(config: dict[str, Any]) -> dict[str, Any]:
        provider = str(config.get("provider", "none"))
        if provider == "none":
            verification = "not-configured"
        else:
            verification = "provider-verification-pending"
        return {
            "encryption_required": True,
            "encryption_verified": False,
            "verification": verification,
            "credential_store": "Spider Vault",
            "secrets_in_sync_config": False,
        }
