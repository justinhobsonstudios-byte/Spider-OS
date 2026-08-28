from __future__ import annotations

import json
import platform
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any


SENSITIVE_DMI_FIELDS = {
    "product_serial",
    "board_serial",
    "chassis_serial",
    "product_uuid",
}


def _read(path: str) -> str | None:
    try:
        value = Path(path).read_text(encoding="utf-8", errors="replace").strip()
        return value or None
    except OSError:
        return None


def _run(command: list[str], timeout: float = 3.0) -> str:
    if not shutil.which(command[0]):
        return ""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


class HardwareValidator:
    """Build a privacy-safe host profile for Spider OS hardware testing.

    The validator deliberately excludes service tags, serial numbers, UUIDs and
    network hardware addresses. Its job is compatibility and driver planning, not
    identifying the machine or its owner.
    """

    name = "Spider Hardware Validation"

    def snapshot(self) -> dict[str, Any]:
        cpu = self._cpu()
        memory = self._memory()
        graphics = self._graphics()
        storage = self._storage()
        firmware = self._firmware()
        identity = self._identity()
        flags = {
            "x86_64": cpu["architecture"] in {"x86_64", "amd64"},
            "uefi": firmware["uefi"],
            "memory_8gib_or_more": memory["total_bytes"] >= 8 * 1024**3,
            "storage_device_present": bool(storage),
            "nvidia_detected": any(device["vendor"] == "NVIDIA" for device in graphics),
        }
        return {
            "name": self.name,
            "identity": identity,
            "cpu": cpu,
            "memory": memory,
            "graphics": graphics,
            "storage": storage,
            "firmware": firmware,
            "flags": flags,
            "image_guidance": {
                "default": "aurora-stable",
                "nvidia_variant_recommended": flags["nvidia_detected"],
                "reason": (
                    "NVIDIA display hardware detected; validate the supported NVIDIA image on this exact machine."
                    if flags["nvidia_detected"]
                    else "No NVIDIA display controller detected; use the standard Intel/AMD Spider OS image."
                ),
            },
            "privacy": {
                "serial_numbers_collected": False,
                "service_tags_collected": False,
                "hardware_uuids_collected": False,
                "mac_addresses_collected": False,
            },
        }

    @staticmethod
    def _identity() -> dict[str, Any]:
        return {
            "vendor": _read("/sys/class/dmi/id/sys_vendor"),
            "product": _read("/sys/class/dmi/id/product_name"),
            "version": _read("/sys/class/dmi/id/product_version"),
            "board_vendor": _read("/sys/class/dmi/id/board_vendor"),
            "board_name": _read("/sys/class/dmi/id/board_name"),
            "virtualized": Path("/sys/class/dmi/id/product_name").exists()
            and any(
                token in ((_read("/sys/class/dmi/id/product_name") or "").lower())
                for token in ("virtual", "qemu", "vmware", "kvm")
            ),
        }

    @staticmethod
    def _cpu() -> dict[str, Any]:
        architecture = platform.machine().lower()
        model = ""
        cores = 0
        threads = 0
        raw = _run(["lscpu", "-J"])
        if raw:
            try:
                payload = json.loads(raw)
                fields = {
                    str(row.get("field", "")).rstrip(":"): str(row.get("data", ""))
                    for row in payload.get("lscpu", [])
                    if isinstance(row, dict)
                }
                model = fields.get("Model name", "")
                cores = int(fields.get("Core(s) per socket", "0") or 0) * int(fields.get("Socket(s)", "1") or 1)
                threads = int(fields.get("CPU(s)", "0") or 0)
            except (ValueError, TypeError, json.JSONDecodeError):
                pass
        return {
            "architecture": architecture,
            "model": model,
            "physical_cores": cores,
            "logical_threads": threads,
        }

    @staticmethod
    def _memory() -> dict[str, Any]:
        total_kib = 0
        try:
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal:"):
                    total_kib = int(re.findall(r"\d+", line)[0])
                    break
        except (OSError, IndexError, ValueError):
            pass
        return {
            "total_bytes": total_kib * 1024,
            "total_gib": round((total_kib * 1024) / (1024**3), 1) if total_kib else 0.0,
        }

    @staticmethod
    def _graphics() -> list[dict[str, str]]:
        raw = _run(["lspci", "-mm"])
        devices: list[dict[str, str]] = []
        for line in raw.splitlines():
            lower = line.lower()
            if not any(kind in lower for kind in ("vga compatible controller", "3d controller", "display controller")):
                continue
            vendor = "Unknown"
            if "nvidia" in lower:
                vendor = "NVIDIA"
            elif "advanced micro devices" in lower or " amd " in f" {lower} ":
                vendor = "AMD"
            elif "intel" in lower:
                vendor = "Intel"
            devices.append({"vendor": vendor, "description": line[:500]})
        return devices

    @staticmethod
    def _storage() -> list[dict[str, Any]]:
        raw = _run(["lsblk", "-J", "-b", "-d", "-o", "NAME,SIZE,TYPE,TRAN,ROTA,MODEL"])
        if not raw:
            return []
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return []
        result: list[dict[str, Any]] = []
        for item in payload.get("blockdevices", []):
            if not isinstance(item, dict) or item.get("type") != "disk":
                continue
            result.append(
                {
                    "name": item.get("name"),
                    "size_bytes": int(item.get("size") or 0),
                    "transport": item.get("tran"),
                    "rotational": bool(item.get("rota")),
                    "model": str(item.get("model") or "").strip() or None,
                }
            )
        return result

    @staticmethod
    def _firmware() -> dict[str, Any]:
        return {
            "uefi": Path("/sys/firmware/efi").exists(),
            "secure_boot_state": "not-read",
            "secure_boot_reason": "Hardware validation does not read EFI variables without an explicit need.",
        }
