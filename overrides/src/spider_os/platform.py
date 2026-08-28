from __future__ import annotations

import urllib.parse
from http import HTTPStatus
from typing import Any

from .assembly import read_assembly_state
from .constants import AI_NAME, DESKTOP_NAME, STARTUP_NAME
from .devices import DeviceWeb
from .modes import MODES, ModeManager
from .resident import read_resident_state
from .setup import SetupStore
from .system_control import SystemControl

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
        }
        return payload

    def make_handler(application: Any) -> type:
        BaseHandler = original_make_handler(application)

        class PlatformHandler(BaseHandler):
            def do_GET(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path not in {
                    "/api/platform",
                    "/api/devices",
                    "/api/system",
                    "/api/mode",
                    "/api/setup",
                }:
                    super().do_GET()
                    return
                if not self._valid_host():
                    self._json_error(HTTPStatus.BAD_REQUEST, "invalid host")
                    return
                try:
                    if parsed.path == "/api/platform":
                        self._json(HTTPStatus.OK, {"platform": platform_snapshot()})
                    elif parsed.path == "/api/devices":
                        query = urllib.parse.parse_qs(parsed.query)
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
                    else:
                        self._json(HTTPStatus.OK, {"setup": SetupStore().read()})
                except ValueError as error:
                    self._json_error(HTTPStatus.BAD_REQUEST, str(error))
                except Exception as error:
                    self._server_error(error)

            def do_POST(self) -> None:
                parsed = urllib.parse.urlparse(self.path)
                if parsed.path not in {"/api/mode", "/api/system/plan"}:
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
                        mode_name = str(payload.get("mode", ""))
                        self._json(HTTPStatus.OK, {"mode": ModeManager().set(mode_name)})
                    else:
                        action = str(payload.get("action", ""))
                        self._json(
                            HTTPStatus.OK,
                            {"plan": SystemControl().action_plan(action)},
                        )
                except (TypeError, ValueError) as error:
                    self._json_error(HTTPStatus.BAD_REQUEST, str(error))
                except Exception as error:
                    self._server_error(error)

        return PlatformHandler

    server_module.SpiderApplication.bootstrap = bootstrap
    server_module.make_handler = make_handler
    _INSTALLED = True
