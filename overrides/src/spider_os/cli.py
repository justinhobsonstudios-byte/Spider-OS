from __future__ import annotations

import argparse
import json
import platform
import sys
import threading
import webbrowser

from . import __version__
from .ai import OllamaClient
from .assembly import WebAssembly, read_assembly_state
from .constants import DEFAULT_HOST, DEFAULT_PORT
from .db import Database
from .devices import DeviceWeb
from .modes import MODES, ModeManager
from .platform import install_server_extensions
from .resident import ResidentAgent
from .server import run_server
from .setup import SetupStore, run_setup
from .system_control import SystemControl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spider-os", description="Spider OS local AI command center")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="start the local command center")
    serve.add_argument("--host", default=DEFAULT_HOST)
    serve.add_argument("--port", default=DEFAULT_PORT, type=int)
    serve.add_argument("--open", action="store_true")

    subparsers.add_parser("init", help="initialize the private local database")
    subparsers.add_parser("doctor", help="check local Spider OS services")
    resident = subparsers.add_parser("resident", help="run the always-on Webbie resident service")
    resident.add_argument("--interval", default=5.0, type=float)

    assembly = subparsers.add_parser("assembly", help="run or inspect Web Assembly")
    assembly.add_argument("operation", choices=["run", "status"], nargs="?", default="run")

    setup = subparsers.add_parser("setup", help="run Spider Setup")
    setup.add_argument("--no-open", action="store_true")
    setup.add_argument("--status", action="store_true")

    devices = subparsers.add_parser("devices", help="inspect the Device Web")
    devices.add_argument("operation", choices=["scan"], nargs="?", default="scan")

    mode = subparsers.add_parser("mode", help="read or change Spider OS workspace mode")
    mode.add_argument("name", choices=["status", *MODES.keys()], nargs="?", default="status")

    system = subparsers.add_parser("system", help="Spider Control Center backend")
    system.add_argument("operation", choices=["status", "plan"], nargs="?", default="status")
    system.add_argument("action", choices=["update", "rollback", "reboot"], nargs="?")
    return parser


def doctor(database: Database) -> dict[str, object]:
    database.initialize()
    ai_status = OllamaClient(timeout=3).status()
    return {
        "spider_os": __version__,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "database": {"ready": database.path.exists(), "path": str(database.path)},
        "local_ai": ai_status,
        "web_assembly": read_assembly_state(),
        "setup": SetupStore().read(),
    }


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "serve"
    database = Database()
    if command == "init":
        database.initialize()
        print("Spider OS initialized at " + str(database.path))
        return 0
    if command == "doctor":
        _print(doctor(database))
        return 0
    if command == "resident":
        ResidentAgent(interval=getattr(args, "interval", 5.0)).run()
        return 0
    if command == "assembly":
        _print(WebAssembly().run() if args.operation == "run" else read_assembly_state())
        return 0
    if command == "setup":
        if args.status:
            _print(SetupStore().read())
        else:
            run_setup(open_browser=not args.no_open)
        return 0
    if command == "devices":
        _print(DeviceWeb().snapshot())
        return 0
    if command == "mode":
        manager = ModeManager()
        _print(manager.current() if args.name == "status" else manager.set(args.name))
        return 0
    if command == "system":
        control = SystemControl()
        if args.operation == "status":
            _print(control.snapshot())
        elif not args.action:
            raise SystemExit("system plan requires update, rollback, or reboot")
        else:
            _print(control.action_plan(args.action))
        return 0
    if command == "serve":
        install_server_extensions()
        if getattr(args, "open", False):
            url = "http://" + args.host + ":" + str(args.port)
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        run_server(args.host, args.port, database)
        return 0
    return 2
