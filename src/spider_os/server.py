from __future__ import annotations

import json
import mimetypes
import secrets
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from typing import Any

from . import __version__
from .actions import ActionBroker
from .ai import OllamaClient, SpiderAssistant
from .constants import APP_NAME
from .db import Database
from .resident import read_resident_state
from .learning import LearningEngine, LearningPolicy
from .personal_web import PersonalKnowledgeWeb
from .proactive import ProactiveEngine
from .research import ResearchEngine
from .screen_context import ScreenContextBuffer


class SpiderApplication:
    def __init__(self, database: Database | None = None) -> None:
        self.database = database or Database()
        self.database.initialize()
        self.broker = ActionBroker(self.database)
        self.ai_client = OllamaClient()
        self.assistant = SpiderAssistant(self.database, self.broker, self.ai_client)
        self.learning = LearningEngine(self.database)
        self.personal_web = PersonalKnowledgeWeb(self.database)
        self.research = ResearchEngine(self.database)
        self.proactive = ProactiveEngine(self.database)
        self.screen_context = ScreenContextBuffer()
        self.csrf_token = secrets.token_urlsafe(32)
        self.web_root = Path(str(files("spider_os").joinpath("web")))

    def bootstrap(self) -> dict[str, Any]:
        return {
            "app": {"name": APP_NAME, "version": __version__},
            "csrf_token": self.csrf_token,
            "spaces": self.database.list_spaces(),
            "today": self.database.today_summary(),
            "proposals": self.database.list_proposals(status="pending"),
            "ai": self.ai_client.status(),
            "resident": read_resident_state(),
            "learning": self.learning.policy.as_dict(),
            "personal_knowledge_web": {
                "policy": self.personal_web.policy.as_dict(),
                "recent": self.personal_web.recent(limit=12),
            },
            "research": {
                "queued": self.database.list_research_questions(status="queued", limit=20),
                "findings": self.database.list_research_findings(limit=12),
            },
            "proactive": self.proactive.briefing(),
            "screen_context": self.screen_context.current(),
            "guardrails": {
                "authority_model": "graduated",
                "routine_reversible_actions_may_auto_execute": True,
                "sensitive_actions_require_confirmation": True,
                "critical_actions_require_explicit_approval": True,
                "arbitrary_shell_access": False,
                "clinical_decision_automation": False,
            },
        }


def make_handler(application: SpiderApplication) -> type[BaseHTTPRequestHandler]:
    class SpiderRequestHandler(BaseHTTPRequestHandler):
        server_version = "SpiderOS/" + __version__

        def do_GET(self) -> None:
            if not self._valid_host():
                self._json_error(HTTPStatus.BAD_REQUEST, "invalid host")
                return
            parsed = urllib.parse.urlparse(self.path)
            try:
                if parsed.path == "/api/health":
                    self._json(
                        HTTPStatus.OK,
                        {
                            "status": "ok",
                            "name": APP_NAME,
                            "version": __version__,
                        },
                    )
                elif parsed.path == "/api/resident":
                    self._json(HTTPStatus.OK, {"resident": read_resident_state()})
                elif parsed.path == "/api/bootstrap":
                    self._json(HTTPStatus.OK, application.bootstrap())
                elif parsed.path == "/api/items":
                    query = urllib.parse.parse_qs(parsed.query)
                    self._json(
                        HTTPStatus.OK,
                        {
                            "items": application.database.list_items(
                                space_id=self._first(query, "space_id"),
                                status=self._first(query, "status"),
                                kind=self._first(query, "kind"),
                                limit=self._int_query(query, "limit", 200),
                            )
                        },
                    )
                elif parsed.path == "/api/search":
                    query = urllib.parse.parse_qs(parsed.query)
                    self._json(
                        HTTPStatus.OK,
                        {
                            "items": application.database.search_items(
                                self._first(query, "q") or "", limit=100
                            )
                        },
                    )
                elif parsed.path == "/api/knowledge":
                    query = urllib.parse.parse_qs(parsed.query)
                    self._json(
                        HTTPStatus.OK,
                        {"knowledge": application.learning.recent(
                            stream=self._first(query, "stream"),
                            limit=self._int_query(query, "limit", 100),
                        )},
                    )
                elif parsed.path == "/api/research/questions":
                    query = urllib.parse.parse_qs(parsed.query)
                    self._json(
                        HTTPStatus.OK,
                        {"questions": application.database.list_research_questions(
                            status=self._first(query, "status"),
                            limit=self._int_query(query, "limit", 100),
                        )},
                    )
                elif parsed.path == "/api/research/findings":
                    query = urllib.parse.parse_qs(parsed.query)
                    self._json(
                        HTTPStatus.OK,
                        {"findings": application.database.list_research_findings(
                            limit=self._int_query(query, "limit", 50)
                        )},
                    )
                elif parsed.path == "/api/alerts":
                    query = urllib.parse.parse_qs(parsed.query)
                    self._json(
                        HTTPStatus.OK,
                        {"alerts": application.database.list_alerts(
                            status=self._first(query, "status") or "unread",
                            limit=self._int_query(query, "limit", 100),
                        )},
                    )
                elif parsed.path == "/api/screen/context":
                    self._json(HTTPStatus.OK, {"screen_context": application.screen_context.current()})
                elif parsed.path == "/api/proposals":
                    query = urllib.parse.parse_qs(parsed.query)
                    self._json(
                        HTTPStatus.OK,
                        {
                            "proposals": application.database.list_proposals(
                                status=self._first(query, "status")
                            )
                        },
                    )
                elif parsed.path == "/api/audit":
                    self._json(
                        HTTPStatus.OK,
                        {"entries": application.database.audit_log(limit=100)},
                    )
                elif parsed.path == "/api/doctor":
                    self._json(
                        HTTPStatus.OK,
                        {
                            "database": {
                                "ready": application.database.path.exists(),
                                "path": str(application.database.path),
                            },
                            "ai": application.ai_client.status(),
                        },
                    )
                else:
                    self._serve_static(parsed.path)
            except ValueError as error:
                self._json_error(HTTPStatus.BAD_REQUEST, str(error))
            except Exception as error:
                self._server_error(error)

        def do_POST(self) -> None:
            if not self._valid_host():
                self._json_error(HTTPStatus.BAD_REQUEST, "invalid host")
                return
            if not self._valid_origin() or not self._valid_token():
                self._json_error(HTTPStatus.FORBIDDEN, "request verification failed")
                return
            parsed = urllib.parse.urlparse(self.path)
            try:
                payload = self._read_json()
                if parsed.path == "/api/items":
                    item = application.database.create_item(
                        space_id=str(payload.get("space_id", "")),
                        kind=str(payload.get("kind", "task")),
                        title=str(payload.get("title", "")),
                        body=str(payload.get("body", "")),
                        status=str(payload.get("status", "open")),
                        due_at=payload.get("due_at"),
                        priority=int(payload.get("priority", 2)),
                        sensitivity=str(payload.get("sensitivity", "standard")),
                        actor="user",
                    )
                    self._json(HTTPStatus.CREATED, {"item": item})
                elif parsed.path == "/api/knowledge":
                    learned = application.learning.ingest(
                        stream=str(payload.get("stream", "user")),
                        content=str(payload.get("content", "")),
                        source=str(payload.get("source", "")),
                        confidence=float(payload.get("confidence", 0.7)),
                        title=str(payload.get("title", "")),
                        metadata=(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
                    )
                    self._json(HTTPStatus.CREATED, {"knowledge": learned})
                elif parsed.path == "/api/personal-memory":
                    memory = application.personal_web.remember(
                        kind=str(payload.get("memory_kind", "fact")),
                        content=str(payload.get("content", "")),
                        source=str(payload.get("source", "user")),
                        confidence=(float(payload["confidence"]) if "confidence" in payload else None),
                        title=str(payload.get("title", "")),
                        evidence_ids=[str(value) for value in payload.get("evidence_ids", [])],
                        metadata=(payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}),
                    )
                    self._json(HTTPStatus.CREATED, {"memory": memory})
                elif parsed.path == "/api/research/questions":
                    question = application.research.queue(
                        query=str(payload.get("query", "")),
                        rationale=str(payload.get("rationale", "")),
                        anchor_id=(str(payload["anchor_id"]) if payload.get("anchor_id") else None),
                        priority=int(payload.get("priority", 2)),
                        generated_by=str(payload.get("generated_by", "user")),
                    )
                    self._json(HTTPStatus.CREATED, {"question": question})
                elif parsed.path == "/api/research/run":
                    result = application.research.run_once()
                    application.proactive.surface_research_findings()
                    self._json(HTTPStatus.OK, {"result": result})
                elif parsed.path == "/api/proactive/scan":
                    due = application.proactive.scan_due_threads()
                    research = application.proactive.surface_research_findings()
                    self._json(HTTPStatus.OK, {"created": due + research, "briefing": application.proactive.briefing()})
                elif parsed.path == "/api/screen/context":
                    context = application.screen_context.update(
                        app_name=str(payload.get("app_name", "")),
                        window_title=str(payload.get("window_title", "")),
                        text_summary=str(payload.get("text_summary", "")),
                        anchor_id=(str(payload["anchor_id"]) if payload.get("anchor_id") else None),
                        sensitive=bool(payload.get("sensitive", False)),
                    )
                    self._json(HTTPStatus.OK, {"screen_context": context})
                elif parsed.path == "/api/chat":
                    result = application.assistant.respond(
                        str(payload.get("message", "")),
                        conversation_id=(
                            str(payload["conversation_id"])
                            if payload.get("conversation_id")
                            else None
                        ),
                    )
                    self._json(HTTPStatus.OK, result)
                elif parsed.path.startswith("/api/proposals/"):
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) != 4:
                        self._json_error(HTTPStatus.NOT_FOUND, "route not found")
                        return
                    proposal_id, decision = parts[2], parts[3]
                    if decision == "approve":
                        proposal = application.broker.approve(proposal_id)
                    elif decision == "reject":
                        proposal = application.broker.reject(proposal_id)
                    else:
                        self._json_error(HTTPStatus.NOT_FOUND, "route not found")
                        return
                    self._json(HTTPStatus.OK, {"proposal": proposal})
                elif parsed.path.startswith("/api/items/") and parsed.path.endswith(
                    "/status"
                ):
                    parts = parsed.path.strip("/").split("/")
                    if len(parts) != 4:
                        self._json_error(HTTPStatus.NOT_FOUND, "route not found")
                        return
                    item = application.database.set_item_status(
                        parts[2], str(payload.get("status", "")), actor="user"
                    )
                    self._json(HTTPStatus.OK, {"item": item})
                else:
                    self._json_error(HTTPStatus.NOT_FOUND, "route not found")
            except (TypeError, ValueError, json.JSONDecodeError) as error:
                self._json_error(HTTPStatus.BAD_REQUEST, str(error))
            except Exception as error:
                self._server_error(error)

        def do_OPTIONS(self) -> None:
            self.send_response(HTTPStatus.NO_CONTENT)
            self._security_headers()
            self.end_headers()

        def _serve_static(self, request_path: str) -> None:
            relative = request_path.lstrip("/") or "index.html"
            if relative in {"app", "today"} or relative.startswith("space/"):
                relative = "index.html"
            candidate = (application.web_root / relative).resolve()
            try:
                candidate.relative_to(application.web_root.resolve())
            except ValueError:
                self._json_error(HTTPStatus.FORBIDDEN, "invalid path")
                return
            if not candidate.is_file():
                candidate = application.web_root / "index.html"
            data = candidate.read_bytes()
            content_type, _ = mimetypes.guess_type(candidate.name)
            self.send_response(HTTPStatus.OK)
            self._security_headers()
            self.send_header("Content-Type", content_type or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            if candidate.name == "index.html":
                self.send_header("Cache-Control", "no-store")
            else:
                self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(data)

        def _read_json(self) -> dict[str, Any]:
            raw_length = self.headers.get("Content-Length", "0")
            try:
                length = int(raw_length)
            except ValueError as error:
                raise ValueError("invalid content length") from error
            if length <= 0:
                return {}
            if length > 1_048_576:
                raise ValueError("request is too large")
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request body must be an object")
            return payload

        def _valid_host(self) -> bool:
            host = self.headers.get("Host", "").split(":", 1)[0].strip("[]").lower()
            return host in {"127.0.0.1", "localhost", "::1"}

        def _valid_origin(self) -> bool:
            origin = self.headers.get("Origin")
            if not origin:
                return True
            parsed = urllib.parse.urlparse(origin)
            return parsed.hostname in {"127.0.0.1", "localhost", "::1"}

        def _valid_token(self) -> bool:
            supplied = self.headers.get("X-Spider-Token", "")
            return secrets.compare_digest(supplied, application.csrf_token)

        def _json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(status)
            self._security_headers()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _json_error(self, status: HTTPStatus, message: str) -> None:
            self._json(status, {"error": message})

        def _server_error(self, error: Exception) -> None:
            traceback.print_exc()
            self._json_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Spider OS hit an internal error: " + str(error),
            )

        def _security_headers(self) -> None:
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
                "style-src 'self'; script-src 'self'; font-src 'self'; "
                "frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
            )
            self.send_header(
                "Permissions-Policy",
                "camera=(), microphone=(), geolocation=(), payment=()",
            )

        @staticmethod
        def _first(query: dict[str, list[str]], key: str) -> str | None:
            values = query.get(key)
            return values[0] if values else None

        @classmethod
        def _int_query(
            cls, query: dict[str, list[str]], key: str, default: int
        ) -> int:
            value = cls._first(query, key)
            try:
                return int(value) if value is not None else default
            except ValueError:
                return default

        def log_message(self, message_format: str, *args: Any) -> None:
            print(
                self.address_string()
                + " - "
                + (message_format % args),
                flush=True,
            )

    return SpiderRequestHandler


class LocalSpiderServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(
    host: str,
    port: int,
    database: Database | None = None,
) -> tuple[LocalSpiderServer, SpiderApplication]:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Spider OS binds only to the local machine")
    application = SpiderApplication(database)
    server = LocalSpiderServer((host, port), make_handler(application))
    return server, application


def run_server(host: str, port: int, database: Database | None = None) -> None:
    server, _ = create_server(host, port, database)
    print("Spider OS is running at http://" + host + ":" + str(port), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

