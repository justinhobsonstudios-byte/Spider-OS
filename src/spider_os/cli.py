from __future__ import annotations

import argparse
import json
import platform
import sys
import threading
import webbrowser

from . import __version__
from .ai import OllamaClient
from .constants import DEFAULT_HOST, DEFAULT_PORT
from .db import Database
from .resident import ResidentAgent
from .server import run_server


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spider-os",
        description="Spider OS local AI command center",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    serve = subparsers.add_parser("serve", help="start the local command center")
    serve.add_argument("--host", default=DEFAULT_HOST)
    serve.add_argument("--port", default=DEFAULT_PORT, type=int)
    serve.add_argument(
        "--open",
        action="store_true",
        help="open the command center in the default browser",
    )

    subparsers.add_parser("init", help="initialize the private local database")
    subparsers.add_parser("doctor", help="check the local Spider OS services")
    resident = subparsers.add_parser("resident", help="run the always-on Web presence service")
    resident.add_argument("--interval", default=5.0, type=float)
    return parser


def doctor(database: Database) -> dict[str, object]:
    database.initialize()
    ai_status = OllamaClient(timeout=3).status()
    return {
        "spider_os": __version__,
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "database": {
            "ready": database.path.exists(),
            "path": str(database.path),
        },
        "local_ai": ai_status,
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "serve"
    database = Database()
    if command == "init":
        database.initialize()
        print("Spider OS initialized at " + str(database.path))
        return 0
    if command == "doctor":
        print(json.dumps(doctor(database), indent=2))
        return 0
    if command == "resident":
        ResidentAgent(interval=getattr(args, "interval", 5.0)).run()
        return 0
    if command == "serve":
        if getattr(args, "open", False):
            url = "http://" + args.host + ":" + str(args.port)
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        run_server(args.host, args.port, database)
        return 0
    return 2

