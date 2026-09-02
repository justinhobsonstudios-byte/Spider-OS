from __future__ import annotations

import html
import json
import os
import threading
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .constants import AI_NAME, DEFAULT_WAKE_PHRASES
from .db import default_data_dir


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


DEFAULTS = {
    "authority": "graduated",
    "voice_enabled": True,
    "screen_awareness": True,
    "screen_archive": False,
    "learn_user": True,
    "learn_studies": True,
    "learn_internet": True,
    "proactive_level": "very-high",
    "default_mode": "default",
    "wake_phrases": list(DEFAULT_WAKE_PHRASES),
}


class SetupStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.path = self.data_dir / "setup.json"

    def read(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {**DEFAULTS, "complete": False}
        except (OSError, json.JSONDecodeError):
            return {**DEFAULTS, "complete": False}

    def write(self, values: dict[str, Any]) -> dict[str, Any]:
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {
            **DEFAULTS,
            **values,
            "complete": True,
            "version": 1,
            "completed_at": utc_now(),
        }
        if payload["authority"] not in {"graduated", "confirm-sensitive", "confirm-all-writes"}:
            raise ValueError("invalid authority level")
        if payload["default_mode"] not in {"default", "studio", "security-lab"}:
            raise ValueError("invalid default mode")
        tmp = self.path.with_suffix(".tmp")
        old_umask = os.umask(0o077)
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
            self.path.chmod(0o600)
        finally:
            os.umask(old_umask)
        return payload


def _page(current: dict[str, Any]) -> bytes:
    checked = lambda key: "checked" if current.get(key) else ""
    option = lambda value: "selected" if current.get("default_mode") == value else ""
    doc = f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Spider Setup</title><style>
:root{{color-scheme:dark}}body{{margin:0;background:#08090b;color:#e8e1d7;font:16px system-ui;padding:28px}}main{{max-width:760px;margin:auto}}h1{{font-size:42px;margin-bottom:4px}}.red{{color:#b3132b}}.card{{background:#111318;border:1px solid #2a2d33;border-radius:14px;padding:20px;margin:18px 0}}label{{display:block;margin:12px 0}}select,button{{font:inherit;padding:10px 14px;background:#191c22;color:#eee;border:1px solid #444;border-radius:8px}}button{{background:#8e1024;border-color:#b3132b;font-weight:700;cursor:pointer}}small{{color:#aaa}}code{{color:#d6a5ad}}</style></head>
<body><main><div class='red'>SPIDER OS · WEB ASSEMBLY</div><h1>Meet {html.escape(AI_NAME)}.</h1><p>Your life. One web. This configures the resident AI and first-session privacy boundaries. You can change these later.</p>
<form method='post' action='/complete'>
<div class='card'><h2>Webbie</h2><label><input type='checkbox' name='voice_enabled' {checked('voice_enabled')}> Voice presence enabled</label><label><input type='checkbox' name='proactive' checked> Very proactive assistance</label><small>Wake phrases: <code>{html.escape(', '.join(DEFAULT_WAKE_PHRASES))}</code>. Wake-word processing is designed to remain local.</small></div>
<div class='card'><h2>Awareness</h2><label><input type='checkbox' name='screen_awareness' {checked('screen_awareness')}> Allow local derived screen context</label><label><input type='checkbox' name='learn_user' {checked('learn_user')}> Learn from my corrections and preferences</label><label><input type='checkbox' name='learn_studies' {checked('learn_studies')}> Learn from study material I provide</label><label><input type='checkbox' name='learn_internet' {checked('learn_internet')}> Permit sourced internet research</label><small>Raw screen frames and ambient audio are not archived by default.</small></div>
<div class='card'><h2>Authority</h2><label>Approval policy <select name='authority'><option value='graduated'>Graduated: routine automatic, sensitive confirm</option><option value='confirm-sensitive'>Confirm sensitive and significant changes</option><option value='confirm-all-writes'>Confirm every write</option></select></label></div>
<div class='card'><h2>Default workspace</h2><select name='default_mode'><option value='default' {option('default')}>The Web</option><option value='studio' {option('studio')}>Studio</option><option value='security-lab' {option('security-lab')}>Kali Bay</option></select></div>
<button type='submit'>Complete Web Assembly</button></form></main></body></html>"""
    return doc.encode("utf-8")


def run_setup(host: str = "127.0.0.1", port: int = 8766, open_browser: bool = True) -> None:
    store = SetupStore()
    server: ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path.split("?", 1)[0] != "/":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            data = _page(store.read())
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:
            if self.path != "/complete":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            length = min(int(self.headers.get("Content-Length", "0")), 16384)
            form = urllib.parse.parse_qs(self.rfile.read(length).decode("utf-8"))
            values = {
                "voice_enabled": "voice_enabled" in form,
                "screen_awareness": "screen_awareness" in form,
                "learn_user": "learn_user" in form,
                "learn_studies": "learn_studies" in form,
                "learn_internet": "learn_internet" in form,
                "authority": form.get("authority", ["graduated"])[0],
                "default_mode": form.get("default_mode", ["default"])[0],
                "proactive_level": "very-high" if "proactive" in form else "normal",
            }
            store.write(values)
            data = b"<html><body style='background:#08090b;color:#eee;font-family:system-ui;padding:40px'><h1>Web Assembly complete.</h1><p>Webbie is configured. You can close this window.</p></body></html>"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            threading.Thread(target=server.shutdown, daemon=True).start()

        def log_message(self, *_: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(f"http://{host}:{port}/")).start()
    server.serve_forever()
