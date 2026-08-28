from __future__ import annotations

import urllib.parse
from http import HTTPStatus
from typing import Any

from .assembly import read_assembly_state
from .constants import AI_NAME, DESKTOP_NAME, STARTUP_NAME
from .devices import DeviceWeb
from .model_router import ModelRouter
from .modes import MODES, ModeManager
from .resident import read_resident_state
from .setup import SetupStore
from .store import SpiderStore
from .studio import SpiderStudio
from .sync import SpiderSync
from .system_control import SystemControl
from .vault import SpiderVault
from .voice import VoiceRuntime

_INSTALLED = False


def platform_snapshot(*, refresh_devices: bool = False) -> dict[str, Any]:
    devices = DeviceWeb()
    mode = ModeManager()
    setup = SetupStore()
    return {
        "desktop": DESKTOP_NAME,
        "resident_ai": AI_NAME,
        "startup": STARTUP_NAME,
        "assembly": read_assembly_state(),
        "resident": read_resident_state(),
        "mode": mode.current(),
        "modes": {name: dict(settings) for name, settings in MODES.items()},
        "setup": setup.read(),
        "devices": devices.snapshot() if refresh_devices else devices.current(),
        "vault": SpiderVault().status(),
        "sync": SpiderSync().status(),
        "voice": VoiceRuntime().status(),
    }


def install_server_extensions() -> None:
    """Attach Spider platform endpoints to the existing loopback-only server.

    This deliberately extends the existing handler instead of creating a second
    HTTP service. The Web therefore keeps one origin, one CSRF token and one local
    security boundary for command-center and platform state.
    """

    global _INSTALLED
    if _INSTALLED:
        return

    from . import server as server_module

    original_bootstrap = server_module.SpiderApplication.bootstrap
    original_make_handler = server_module.make_handler

    def bootstrap(application: Any) -> dict[str, Any]:
        payload = original_bootstrap(application)
        platform = platform_snapshot(refresh_devices=False)
        payload["platform"] = {
            "desktop": platform["desktop"],
            "resident_ai": platform["resident_ai"],
            "startup": platform["startup"],
            "assembly": platform["assembly"],
            "mode": platform["mode"],
            "setup": platform["setup"],
            "devices": platform["devices"],
            "vault": platform["vault"],
            "sync": platform["sync"],
            "voice": platform["voice"],
        }
        return payload

    def make_handler(application: Any) -> type:
        BaseHandler = original_make_handler(application)

        class PlatformHandler(BaseHandler):
            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                platform_paths = {
                    "/api/platform",
                    "/api/devices",
                    "/api/system",
                    "/api/mode",
                    "/api/setup",
                    "/api/store",
                    "/api/vault",
                    "/api/sync",
                    "/api/models",
                    "/api/voice",
                    "/api/studio",
                }
                if parsed.path not in platform_paths:
                    super().do_GET()
                    return
                if not self._valid_host():
                    self._json_error(HTTPStatus.BAD_REQUEST, "invalid host")
                    return
                try:
                    query = urllib.parse.parse_qs(parsed.query)
                    if parsed.path == "/api/platform":
                        self._json(HTTPStatus.OK, {"platform": platform_snapshot()})
                    elif parsed.path == "/api/devices":
                        refresh = self._first(query, "refresh") in {"1", "true", "yes"}
                        devices = DeviceWeb()
                        self._json(
                            HTTPStatus.OK,
                            {"devices": devices.snapshot() if refresh else devices.current()},
                        )
                    elif parsed.path == "/api/system":
                        self._json(HTTPStatus.OK, {"system": SystemControl().snapshot()})
                    elif parsed.path == "/api/mode":
                        manager = ModeManager()
                        self._json(
                            HTTPStatus.OK,
                            {"mode": manager.current(), "available": list(MODES)},
                        )
                    elif parsed.path == "/api/setup":
                        self._json(HTTPStatus.OK, {"setup": SetupStore().read()})
                    elif parsed.path == "/api/store":
                        store = SpiderStore()
                        search = (self._first(query, "q") or "").strip()
                        payload = store.search(search) if search else store.snapshot()
                        self._json(HTTPStatus.OK, {"store": payload})
                    elif parsed.path == "/api/vault":
                        self._json(HTTPStatus.OK, {"vault": SpiderVault().status()})
                    elif parsed.path == "/api/sync":
                        self._json(HTTPStatus.OK, {"sync": SpiderSync().status()})
                    elif parsed.path == "/api/models":
                        self._json(HTTPStatus.OK, {"models": ModelRouter().status()})
                    elif parsed.path == "/api/voice":
                        self._json(HTTPStatus.OK, {"voice": VoiceRuntime().status()})
                    else:
                        self._json(HTTPStatus.OK, {"studio": SpiderStudio().status()})
                except ValueError as error:
                    self._json_error(HTTPStatus.BAD_REQUEST, str(error))
                except Exception as error:
                    self._server_error(error)

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                platform_paths = {
                    "/api/mode",
                    "/api/system/plan",
                    "/api/store/plan",
                    "/api/vault/plan",
                    "/api/sync/configure",
                    "/api/sync/plan",
                    "/api/models/route",
                    "/api/studio/plan",
                }
                if parsed.path not in platform_paths:
                    super().do_POST()
                    return
                if not self._valid_host():
                    self._json_error(HTTPStatus.BAD_REQUEST, "invalid host")
                    return
                if not self._valid_origin() or not self._valid_token():
                    self._json_error(HTTPStatus.FORBIDDEN, "request verification failed")
                    return
                try:
                    payload = self._read_json()
                    if parsed.path == "/api/mode":
                        self._json(
                            HTTPStatus.OK,
                            {"mode": ModeManager().set(str(payload.get("mode", "")))},
                        )
                    elif parsed.path == "/api/system/plan":
                        self._json(
                            HTTPStatus.OK,
                            {"plan": SystemControl().action_plan(str(payload.get("action", "")))},
                        )
                    elif parsed.path == "/api/store/plan":
                        self._json(
                            HTTPStatus.OK,
                            {"plan": SpiderStore().action_plan(
                                str(payload.get("action", "")),
                                str(payload.get("app_id", "")),
                                str(payload.get("remote", "flathub")),
                            )},
                        )
                    elif parsed.path == "/api/vault/plan":
                        self._json(
                            HTTPStatus.OK,
                            {"plan": SpiderVault().action_plan(str(payload.get("action", "")))},
                        )
                    elif parsed.path == "/api/sync/configure":
                        scopes = payload.get("scopes")
                        if scopes is not None and not isinstance(scopes, list):
                            raise ValueError("sync scopes must be a list")
                        self._json(
                            HTTPStatus.OK,
                            {"sync": SpiderSync().configure(
                                enabled=bool(payload.get("enabled", False)),
                                provider=str(payload.get("provider", "none")),
                                scopes=[str(value) for value in scopes] if scopes else None,
                                endpoint=(str(payload["endpoint"]) if payload.get("endpoint") else None),
                            )},
                        )
                    elif parsed.path == "/api/sync/plan":
                        self._json(
                            HTTPStatus.OK,
                            {"plan": SpiderSync().action_plan(str(payload.get("action", "")))},
                        )
                    elif parsed.path == "/api/models/route":
                        self._json(
                            HTTPStatus.OK,
                            {"route": ModelRouter().choose(
                                sensitivity=str(payload.get("sensitivity", "standard")),
                                cloud_explicitly_allowed=bool(payload.get("cloud_explicitly_allowed", False)),
                                offline=bool(payload.get("offline", False)),
                            )},
                        )
                    else:
                        self._json(
                            HTTPStatus.OK,
                            {"plan": SpiderStudio().action_plan(
                                str(payload.get("action", "")),
                                (str(payload["command"]) if payload.get("command") else None),
                            )},
                        )
                except (TypeError, ValueError) as error:
                    self._json_error(HTTPStatus.BAD_REQUEST, str(error))
                except Exception as error:
                    self._server_error(error)

        return PlatformHandler

    server_module.SpiderApplication.bootstrap = bootstrap
    server_module.make_handler = make_handler
    _INSTALLED = True
