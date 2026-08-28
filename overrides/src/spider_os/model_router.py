from __future__ import annotations

import os
from typing import Any

from .ai import OllamaClient


class ModelRouter:
    """Choose local versus cloud inference without leaking restricted context."""

    name = "Webbie Model Router"

    def __init__(self) -> None:
        self.local = OllamaClient(timeout=2)

    def status(self) -> dict[str, Any]:
        local = self.local.status()
        cloud_provider = os.environ.get("SPIDER_OS_CLOUD_MODEL_PROVIDER", "").strip() or None
        cloud_enabled = os.environ.get("SPIDER_OS_CLOUD_MODEL_ENABLED", "0") == "1"
        return {
            "name": self.name,
            "local": local,
            "cloud": {
                "enabled": cloud_enabled,
                "provider": cloud_provider,
                "configured": bool(cloud_enabled and cloud_provider),
            },
            "policy": self.policy(),
        }

    @staticmethod
    def policy() -> dict[str, Any]:
        return {
            "standard": "local-preferred-cloud-allowed",
            "private": "local-preferred-cloud-explicit",
            "restricted": "local-only",
            "offline": "local-only",
            "cloud_memory_write": False,
            "cloud_restricted_context": False,
        }

    def choose(
        self,
        *,
        sensitivity: str = "standard",
        cloud_explicitly_allowed: bool = False,
        offline: bool = False,
    ) -> dict[str, Any]:
        if sensitivity not in {"standard", "private", "restricted"}:
            raise ValueError("unknown model-routing sensitivity")
        status = self.status()
        local_ready = bool(status["local"].get("available"))
        cloud_ready = bool(status["cloud"]["configured"])

        if offline or sensitivity == "restricted":
            route = "local" if local_ready else "unavailable"
            reason = "restricted/offline context stays on-device"
        elif sensitivity == "private":
            if local_ready:
                route, reason = "local", "private context prefers on-device inference"
            elif cloud_ready and cloud_explicitly_allowed:
                route, reason = "cloud", "private cloud use was explicitly allowed"
            else:
                route, reason = "unavailable", "private cloud fallback requires explicit approval"
        elif local_ready:
            route, reason = "local", "local model is available"
        elif cloud_ready:
            route, reason = "cloud", "local model unavailable and standard cloud fallback is configured"
        else:
            route, reason = "unavailable", "no eligible model provider is available"

        return {
            "route": route,
            "reason": reason,
            "sensitivity": sensitivity,
            "cloud_explicitly_allowed": cloud_explicitly_allowed,
        }
