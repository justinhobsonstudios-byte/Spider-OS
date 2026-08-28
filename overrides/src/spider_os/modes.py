from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import default_data_dir

MODES = {
    "default": {"address_name": "Cory", "anchor": "today", "profile": "balanced"},
    "studio": {"address_name": "Justin", "anchor": "music", "profile": "creative"},
    "security-lab": {"address_name": "Spider", "anchor": "security-lab", "profile": "isolated"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ModeManager:
    """Track the active Spider OS context without pretending context is privilege."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.runtime_dir = self.data_dir / "runtime"
        self.path = self.runtime_dir / "mode.json"

    def current(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and payload.get("mode") in MODES:
                return payload
        except (OSError, json.JSONDecodeError):
            pass
        return self.set("default", actor="system")

    def set(self, mode: str, actor: str = "user") -> dict[str, Any]:
        if mode not in MODES:
            raise ValueError(f"unknown Spider OS mode: {mode}")
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {
            "mode": mode,
            **MODES[mode],
            "actor": actor,
            "changed_at": utc_now(),
            "security_boundary": mode == "security-lab",
        }
        tmp = self.path.with_suffix(".tmp")
        old_umask = os.umask(0o077)
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
            self.path.chmod(0o600)
        finally:
            os.umask(old_umask)
        return payload
