from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import AI_NAME, APP_NAME, MEMORY_NAME, STARTUP_NAME
from .db import Database, default_data_dir
from .devices import DeviceWeb
from .modes import MODES, ModeManager
from .setup import SetupStore
from .system_control import SystemControl


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class AssemblyPhase:
    name: str
    status: str
    detail: str
    elapsed_ms: int


class WebAssembly:
    """Initialize the user-owned Spider OS runtime without privileged mutation.

    Web Assembly is deliberately a user-session coordinator. It prepares private
    runtime state, verifies Spider Core dependencies, snapshots hardware and update
    state, and records enough information for The Web/Webbie to explain what is ready.
    It does not silently change firmware, partitions, networking, or system images.
    """

    def __init__(self) -> None:
        self.data_dir = default_data_dir()
        self.runtime_dir = self.data_dir / "runtime"
        self.state_path = self.runtime_dir / "web-assembly.json"
        self.phases: list[AssemblyPhase] = []

    def _phase(self, name: str, func: Any) -> Any:
        started = time.monotonic()
        try:
            result = func()
            detail = result if isinstance(result, str) else "ready"
            status = "ready"
            return result
        except Exception as error:  # startup should degrade, not strand the session
            detail = str(error)[:240]
            status = "degraded"
            return None
        finally:
            elapsed = int((time.monotonic() - started) * 1000)
            self.phases.append(AssemblyPhase(name, status, detail, elapsed))

    def run(self) -> dict[str, Any]:
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.runtime_dir, 0o700)

        db = Database(self.data_dir)
        self._phase("Personal Knowledge Web", lambda: (db.initialize(), MEMORY_NAME)[1])

        setup_store = SetupStore(self.data_dir)
        setup = self._phase("Spider Setup", setup_store.read) or {"complete": False}

        modes = ModeManager(self.data_dir)
        active_mode = self._phase("Workspace mode", lambda: self._resolve_mode(modes, setup)) or {"mode": "default"}

        devices = DeviceWeb(self.data_dir)
        device_snapshot = self._phase("Device Web", devices.snapshot) or {}

        system = SystemControl()
        system_snapshot = self._phase("System state", system.snapshot) or {}

        network = self._phase("Network", self._network_state) or {"online": False}

        payload: dict[str, Any] = {
            "name": STARTUP_NAME,
            "os": APP_NAME,
            "resident_ai": AI_NAME,
            "status": "ready" if all(p.status == "ready" for p in self.phases) else "degraded",
            "assembled_at": utc_now(),
            "phases": [asdict(p) for p in self.phases],
            "devices": device_snapshot,
            "system": system_snapshot,
            "mode": active_mode,
            "network": network,
            "setup": setup,
        }
        self._write(payload)
        return payload

    @staticmethod
    def _resolve_mode(modes: ModeManager, setup: dict[str, Any]) -> dict[str, Any]:
        # Preserve deliberate runtime changes. Only seed the mode from Setup when
        # no mode state exists yet, including migration from older Spider builds.
        if modes.path.exists():
            return modes.current()
        default_mode = str(setup.get("default_mode", "default"))
        if bool(setup.get("complete")) and default_mode in MODES:
            return modes.set(default_mode, actor="setup")
        return modes.current()

    def _network_state(self) -> dict[str, Any]:
        result = {"online": False, "hostname": socket.gethostname()}
        try:
            with socket.create_connection(("1.1.1.1", 443), timeout=0.6):
                result["online"] = True
        except OSError:
            pass
        return result

    def _write(self, payload: dict[str, Any]) -> None:
        tmp = self.state_path.with_suffix(".tmp")
        old_umask = os.umask(0o077)
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.state_path)
            self.state_path.chmod(0o600)
        finally:
            os.umask(old_umask)


def read_assembly_state() -> dict[str, Any]:
    path = default_data_dir() / "runtime" / "web-assembly.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {"name": STARTUP_NAME, "status": "not-run", "phases": []}
