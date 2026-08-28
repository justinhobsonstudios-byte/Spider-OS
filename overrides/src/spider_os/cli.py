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
from .hardware import HardwareValidator
from .model_router import ModelRouter
from .modes import MODES, ModeManager
from .platform import install_server_extensions
from .resident import ResidentAgent
from .server import run_server
from .setup import SetupStore, run_setup
from .store import SpiderStore
from .studio import SpiderStudio
from .sync import SpiderSync
from .system_control import SystemControl
from .vault import SpiderVault
from .voice import VoiceRuntime


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spider-os", description="Spider OS local AI command center")
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="start The Web local command center")
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
    subparsers.add_parser("hardware", help="run privacy-safe Spider hardware validation")

    mode = subparsers.add_parser("mode", help="read or change Spider OS workspace mode")
    mode.add_argument("name", choices=["status", *MODES.keys()], nargs="?", default="status")

    system = subparsers.add_parser("system", help="Spider Control Center backend")
    system.add_argument("operation", choices=["status", "plan", "execute"], nargs="?", default="status")
    system.add_argument("action", choices=["update", "rollback", "reboot"], nargs="?")

    store = subparsers.add_parser("store", help="inspect Spider Store or create an app action plan")
    store.add_argument("operation", choices=["status", "search", "plan"], nargs="?", default="status")
    store.add_argument("value", nargs="?", help="search text or application id")
    store.add_argument("--action", choices=["install", "remove", "update"])
    store.add_argument("--remote", default="flathub")

    vault = subparsers.add_parser("vault", help="inspect Spider Vault")
    vault.add_argument("operation", choices=["status", "plan"], nargs="?", default="status")
    vault.add_argument("--action", choices=["open-manager"], default="open-manager")

    sync = subparsers.add_parser("sync", help="inspect or configure Spider Sync")
    sync.add_argument("operation", choices=["status", "configure", "plan"], nargs="?", default="status")
    sync.add_argument("--enabled", choices=["true", "false"], default="false")
    sync.add_argument("--provider", choices=sorted(SpiderSync.providers), default="none")
    sync.add_argument("--scope", action="append", choices=sorted(SpiderSync.scopes))
    sync.add_argument("--endpoint")
    sync.add_argument("--action", choices=["sync-now", "pause"], default="sync-now")

    models = subparsers.add_parser("models", help="inspect Webbie model routing")
    models.add_argument("operation", choices=["status", "route"], nargs="?", default="status")
    models.add_argument("--sensitivity", choices=["standard", "private", "restricted"], default="standard")
    models.add_argument("--allow-cloud", action="store_true")
    models.add_argument("--offline", action="store_true")

    voice = subparsers.add_parser("voice", help="inspect or run Webbie's local voice presence")
    voice.add_argument("operation", choices=["status", "listen", "say"], nargs="?", default="status")
    voice.add_argument("text", nargs="*")
    voice.add_argument("--interval", type=float, default=5.0)

    studio = subparsers.add_parser("studio", help="inspect Spider Studio or create a session plan")
    studio.add_argument("operation", choices=["status", "plan"], nargs="?", default="status")
    studio.add_argument("--action", choices=["open-app", "low-latency-profile"], default="low-latency-profile")
    studio.add_argument("--command", dest="studio_command")
    return parser


def doctor(database: Database) -> dict[str, object]:
    database.initialize()
    ai_status = OllamaClient(timeout=3).status()
    return {
        "spider_os": __version__,
        "desktop": "The Web",
        "resident_ai": "Webbie",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "database": {"ready": database.path.exists(), "path": str(database.path)},
        "local_ai": ai_status,
        "web_assembly": read_assembly_state(),
        "setup": SetupStore().read(),
        "hardware": HardwareValidator().snapshot(),
        "vault": SpiderVault().status(),
        "sync": SpiderSync().status(),
        "voice": VoiceRuntime().status(),
        "studio": SpiderStudio().status(),
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
    if command == "hardware":
        _print(HardwareValidator().snapshot())
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
            raise SystemExit("system plan/execute requires update, rollback, or reboot")
        elif args.operation == "execute":
            _print(control.execute(args.action))
        else:
            _print(control.action_plan(args.action))
        return 0
    if command == "store":
        store = SpiderStore()
        if args.operation == "status":
            _print(store.snapshot())
        elif args.operation == "search":
            if not args.value:
                raise SystemExit("store search requires search text")
            _print(store.search(args.value))
        else:
            if not args.action or not args.value:
                raise SystemExit("store plan requires --action and an application id")
            _print(store.action_plan(args.action, args.value, args.remote))
        return 0
    if command == "vault":
        vault = SpiderVault()
        _print(vault.status() if args.operation == "status" else vault.action_plan(args.action))
        return 0
    if command == "sync":
        sync = SpiderSync()
        if args.operation == "status":
            _print(sync.status())
        elif args.operation == "configure":
            _print(sync.configure(
                enabled=args.enabled == "true",
                provider=args.provider,
                scopes=args.scope,
                endpoint=args.endpoint,
            ))
        else:
            _print(sync.action_plan(args.action))
        return 0
    if command == "models":
        router = ModelRouter()
        _print(
            router.status()
            if args.operation == "status"
            else router.choose(
                sensitivity=args.sensitivity,
                cloud_explicitly_allowed=args.allow_cloud,
                offline=args.offline,
            )
        )
        return 0
    if command == "voice":
        runtime = VoiceRuntime()
        if args.operation == "status":
            _print(runtime.status())
        elif args.operation == "say":
            text = " ".join(args.text).strip()
            if not text:
                raise SystemExit("voice say requires text")
            _print(runtime.speak(text))
        else:
            runtime.listen_forever(interval=max(2.0, args.interval))
        return 0
    if command == "studio":
        studio = SpiderStudio()
        _print(
            studio.status()
            if args.operation == "status"
            else studio.action_plan(args.action, args.studio_command)
        )
        return 0
    if command == "serve":
        install_server_extensions()
        if getattr(args, "open", False):
            url = "http://" + args.host + ":" + str(args.port)
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        run_server(args.host, args.port, database)
        return 0
    return 2
