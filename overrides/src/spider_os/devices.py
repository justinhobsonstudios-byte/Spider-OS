from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .db import default_data_dir


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(command: list[str], timeout: float = 2.0) -> str:
    if not shutil.which(command[0]):
        return ""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip()


class DeviceWeb:
    """Read-only hardware awareness for Webbie and Spider Control Center."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.runtime_dir = self.data_dir / "runtime"
        self.path = self.runtime_dir / "device-web.json"

    def current(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except (OSError, json.JSONDecodeError):
            pass
        return {
            "name": "Device Web",
            "captured_at": None,
            "pci": [],
            "usb": [],
            "network": [],
            "audio": {"pipewire": False, "default": "", "sinks": [], "sources": []},
            "bluetooth": {"available": False, "controllers": [], "devices": []},
            "displays": [],
            "storage": [],
        }

    def snapshot(self) -> dict[str, Any]:
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {
            "name": "Device Web",
            "captured_at": utc_now(),
            "pci": self._lines(_run(["lspci", "-mm"])),
            "usb": self._lines(_run(["lsusb"])),
            "network": self._network(),
            "audio": self._audio(),
            "bluetooth": self._bluetooth(),
            "displays": self._displays(),
            "storage": self._storage(),
        }
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self.path.chmod(0o600)
        return payload

    @staticmethod
    def _lines(value: str) -> list[str]:
        return [line for line in value.splitlines() if line.strip()]

    def _network(self) -> list[dict[str, Any]]:
        interfaces: list[dict[str, Any]] = []
        root = Path("/sys/class/net")
        if not root.exists():
            return interfaces
        for entry in sorted(root.iterdir()):
            if entry.name == "lo":
                continue
            wireless = (entry / "wireless").exists()
            try:
                state = (entry / "operstate").read_text().strip()
            except OSError:
                state = "unknown"
            interfaces.append({"name": entry.name, "kind": "wifi" if wireless else "ethernet", "state": state})
        return interfaces

    def _audio(self) -> dict[str, Any]:
        return {
            "pipewire": bool(shutil.which("pw-cli")),
            "default": _run(["pactl", "info"]),
            "sinks": self._lines(_run(["pactl", "list", "short", "sinks"])),
            "sources": self._lines(_run(["pactl", "list", "short", "sources"])),
        }

    def _bluetooth(self) -> dict[str, Any]:
        return {
            "available": bool(shutil.which("bluetoothctl")),
            "controllers": self._lines(_run(["bluetoothctl", "list"])),
            "devices": self._lines(_run(["bluetoothctl", "devices", "Connected"])),
        }

    def _displays(self) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        root = Path("/sys/class/drm")
        if not root.exists():
            return result
        for status in sorted(root.glob("card*-*/status")):
            try:
                value = status.read_text().strip()
            except OSError:
                continue
            result.append({"connector": status.parent.name, "status": value})
        return result

    def _storage(self) -> list[str]:
        return self._lines(_run(["lsblk", "-J", "-o", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS,MODEL"]))
