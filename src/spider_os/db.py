from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .preload import SEED_VERSION, load_seed

from .constants import (
    DEFAULT_SPACES,
    ITEM_KINDS,
    ITEM_STATUSES,
    SENSITIVITY_LEVELS,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def default_data_dir() -> Path:
    override = os.environ.get("SPIDER_OS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    xdg = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return (root / "spider-os").resolve()


class Database:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = (data_dir or default_data_dir()).resolve()
        self.path = self.data_dir / "spider.db"

    def _secure_directory(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.data_dir.chmod(0o700)
        except OSError:
            pass

    def connect(self) -> sqlite3.Connection:
        self._secure_directory()
        previous_umask = os.umask(0o077)
        try:
            connection = sqlite3.connect(self.path, timeout=15)
        finally:
            os.umask(previous_umask)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 15000")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.transaction() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS spaces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    icon TEXT NOT NULL DEFAULT 'circle',
                    color TEXT NOT NULL DEFAULT '#888888',
                    parent_id TEXT REFERENCES spaces(id) ON DELETE SET NULL,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    enabled INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY,
                    space_id TEXT NOT NULL REFERENCES spaces(id) ON DELETE RESTRICT,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    due_at TEXT,
                    priority INTEGER NOT NULL DEFAULT 2,
                    sensitivity TEXT NOT NULL DEFAULT 'standard',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_items_space_status
                    ON items(space_id, status);
                CREATE INDEX IF NOT EXISTS idx_items_due
                    ON items(due_at);

                CREATE TABLE IF NOT EXISTS action_proposals (
                    id TEXT PRIMARY KEY,
                    action_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    rationale TEXT NOT NULL DEFAULT '',
                    risk_level TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                );

                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id TEXT,
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_messages_conversation
                    ON messages(conversation_id, id);

                CREATE TABLE IF NOT EXISTS knowledge (
                    id TEXT PRIMARY KEY,
                    stream TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.7,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_stream_created
                    ON knowledge(stream, created_at DESC);

                CREATE TABLE IF NOT EXISTS research_questions (
                    id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    rationale TEXT NOT NULL DEFAULT '',
                    anchor_id TEXT REFERENCES spaces(id) ON DELETE SET NULL,
                    priority INTEGER NOT NULL DEFAULT 2,
                    status TEXT NOT NULL DEFAULT 'queued',
                    generated_by TEXT NOT NULL DEFAULT 'webbie',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_research_questions_status_priority
                    ON research_questions(status, priority DESC, created_at);

                CREATE TABLE IF NOT EXISTS research_sources (
                    id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL DEFAULT '',
                    snippet TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL DEFAULT 'web',
                    quality REAL NOT NULL DEFAULT 0.5,
                    retrieved_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_research_sources_question
                    ON research_sources(question_id, retrieved_at DESC);

                CREATE TABLE IF NOT EXISTS research_findings (
                    id TEXT PRIMARY KEY,
                    question_id TEXT NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.5,
                    urgency TEXT NOT NULL DEFAULT 'quiet',
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    surfaced_at TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_research_findings_created
                    ON research_findings(created_at DESC);

                CREATE TABLE IF NOT EXISTS proactive_alerts (
                    id TEXT PRIMARY KEY,
                    alert_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL DEFAULT '',
                    urgency TEXT NOT NULL DEFAULT 'quiet',
                    source_kind TEXT,
                    source_id TEXT,
                    status TEXT NOT NULL DEFAULT 'unread',
                    due_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_alert_dedupe
                    ON proactive_alerts(alert_type, source_kind, source_id, due_at);
                """
            )
            for space in DEFAULT_SPACES:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO spaces
                    (id, name, description, icon, color, parent_id, sort_order, enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        space["id"],
                        space["name"],
                        space["description"],
                        space["icon"],
                        space["color"],
                        space["parent_id"],
                        space["sort_order"],
                    ),
                )
            connection.execute(
                """
                INSERT OR IGNORE INTO settings(key, value, updated_at)
                VALUES ('setup_complete', 'false', ?)
                """,
                (utc_now(),),
            )
            self._seed_preloaded_knowledge(connection)

    def _seed_preloaded_knowledge(self, connection: sqlite3.Connection) -> None:
        row = connection.execute(
            "SELECT value FROM settings WHERE key = 'preload_seed_version'"
        ).fetchone()
        current = int(row["value"]) if row and str(row["value"]).isdigit() else 0
        if current >= SEED_VERSION:
            return
        now = utc_now()
        for entry in load_seed():
            metadata = dict(entry.get("metadata", {}))
            metadata["preloaded"] = True
            metadata["seed_version"] = SEED_VERSION
            connection.execute(
                """
                INSERT INTO knowledge
                (id, stream, title, content, source, confidence, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    entry["stream"],
                    entry.get("title", ""),
                    entry["content"],
                    entry["source"],
                    float(entry.get("confidence", 0.9)),
                    json.dumps(metadata, sort_keys=True),
                    now,
                    now,
                ),
            )
        connection.execute(
            """
            INSERT INTO settings(key, value, updated_at) VALUES ('preload_seed_version', ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
            """,
            (str(SEED_VERSION), now),
        )

    def list_spaces(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, description, icon, color, parent_id, sort_order
                FROM spaces
                WHERE enabled = 1
                ORDER BY sort_order, name
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_space(self, space_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM spaces WHERE id = ? AND enabled = 1", (space_id,)
            ).fetchone()
        return dict(row) if row else None

    def list_items(
        self,
        *,
        space_id: str | None = None,
        status: str | None = None,
        kind: str | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if space_id and space_id != "today":
            clauses.append("space_id = ?")
            values.append(space_id)
        if status:
            clauses.append("status = ?")
            values.append(status)
        if kind:
            clauses.append("kind = ?")
            values.append(kind)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        values.append(max(1, min(limit, 500)))
        query = (
            "SELECT * FROM items"
            + where
            + """
              ORDER BY
                CASE status WHEN 'active' THEN 0 WHEN 'open' THEN 1
                  WHEN 'waiting' THEN 2 ELSE 3 END,
                CASE WHEN due_at IS NULL THEN 1 ELSE 0 END,
                due_at,
                priority DESC,
                updated_at DESC
              LIMIT ?
            """
        )
        with self.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._decode_item(row) for row in rows]

    def search_items(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        clean = query.strip()
        if not clean:
            return []
        escaped = clean.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = "%" + escaped + "%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM items
                WHERE (title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\')
                  AND status != 'archived'
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (pattern, pattern, max(1, min(limit, 200))),
            ).fetchall()
        return [self._decode_item(row) for row in rows]

    def create_item(
        self,
        *,
        space_id: str,
        kind: str,
        title: str,
        body: str = "",
        status: str = "open",
        due_at: str | None = None,
        priority: int = 2,
        sensitivity: str = "standard",
        metadata: dict[str, Any] | None = None,
        actor: str = "user",
    ) -> dict[str, Any]:
        title = title.strip()
        if not title:
            raise ValueError("title is required")
        if kind not in ITEM_KINDS:
            raise ValueError("unsupported item kind")
        if status not in ITEM_STATUSES:
            raise ValueError("unsupported item status")
        if sensitivity not in SENSITIVITY_LEVELS:
            raise ValueError("unsupported sensitivity level")
        if not self.get_space(space_id):
            raise ValueError("unknown space")
        item_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO items
                (id, space_id, kind, title, body, status, due_at, priority,
                 sensitivity, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    space_id,
                    kind,
                    title,
                    body.strip(),
                    status,
                    due_at,
                    max(0, min(int(priority), 4)),
                    sensitivity,
                    json.dumps(metadata or {}, separators=(",", ":")),
                    timestamp,
                    timestamp,
                ),
            )
            self._audit(
                connection,
                actor=actor,
                action="item.create",
                target_type="item",
                target_id=item_id,
                details={"space_id": space_id, "kind": kind},
            )
            row = connection.execute(
                "SELECT * FROM items WHERE id = ?", (item_id,)
            ).fetchone()
        return self._decode_item(row)

    def set_item_status(
        self, item_id: str, status: str, *, actor: str = "user"
    ) -> dict[str, Any]:
        if status not in ITEM_STATUSES:
            raise ValueError("unsupported item status")
        timestamp = utc_now()
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE items SET status = ?, updated_at = ? WHERE id = ?",
                (status, timestamp, item_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("item not found")
            self._audit(
                connection,
                actor=actor,
                action="item.status",
                target_type="item",
                target_id=item_id,
                details={"status": status},
            )
            row = connection.execute(
                "SELECT * FROM items WHERE id = ?", (item_id,)
            ).fetchone()
        return self._decode_item(row)

    def today_summary(self) -> dict[str, Any]:
        items = self.list_items(limit=500)
        open_items = [
            item for item in items if item["status"] in {"open", "active", "waiting"}
        ]
        active = [item for item in open_items if item["status"] == "active"]
        due = [item for item in open_items if item["due_at"]]
        pending = self.list_proposals(status="pending")
        return {
            "open_count": len(open_items),
            "active_count": len(active),
            "scheduled_count": len(due),
            "pending_approval_count": len(pending),
            "focus": active[:3] or open_items[:3],
            "upcoming": due[:6],
        }

    def create_proposal(
        self,
        *,
        action_name: str,
        arguments: dict[str, Any],
        rationale: str,
        risk_level: str,
    ) -> dict[str, Any]:
        proposal_id = str(uuid.uuid4())
        timestamp = utc_now()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO action_proposals
                (id, action_name, arguments_json, rationale, risk_level, status,
                 created_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?)
                """,
                (
                    proposal_id,
                    action_name,
                    json.dumps(arguments, separators=(",", ":")),
                    rationale,
                    risk_level,
                    timestamp,
                ),
            )
            self._audit(
                connection,
                actor="ai",
                action="proposal.create",
                target_type="proposal",
                target_id=proposal_id,
                details={"action_name": action_name, "risk_level": risk_level},
            )
            row = connection.execute(
                "SELECT * FROM action_proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        return self._decode_proposal(row)

    def get_proposal(self, proposal_id: str) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM action_proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        return self._decode_proposal(row) if row else None

    def claim_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE action_proposals
                SET status = 'executing'
                WHERE id = ? AND status = 'pending'
                """,
                (proposal_id,),
            )
            if cursor.rowcount != 1:
                raise ValueError("proposal is no longer pending")
            row = connection.execute(
                "SELECT * FROM action_proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        return self._decode_proposal(row)

    def list_proposals(self, status: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM action_proposals"
        values: tuple[Any, ...] = ()
        if status:
            query += " WHERE status = ?"
            values = (status,)
        query += " ORDER BY created_at DESC LIMIT 100"
        with self.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._decode_proposal(row) for row in rows]

    def decide_proposal(
        self,
        proposal_id: str,
        *,
        status: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if status not in {"approved", "rejected", "failed"}:
            raise ValueError("invalid proposal decision")
        expected_status = "pending" if status == "rejected" else "executing"
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT status FROM action_proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
            if not row:
                raise ValueError("proposal not found")
            if row["status"] != expected_status:
                raise ValueError("proposal cannot be decided from its current state")
            connection.execute(
                """
                UPDATE action_proposals
                SET status = ?, result_json = ?, decided_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    json.dumps(result or {}, separators=(",", ":")),
                    utc_now(),
                    proposal_id,
                ),
            )
            self._audit(
                connection,
                actor="user",
                action="proposal." + status,
                target_type="proposal",
                target_id=proposal_id,
                details=result or {},
            )
            updated = connection.execute(
                "SELECT * FROM action_proposals WHERE id = ?", (proposal_id,)
            ).fetchone()
        return self._decode_proposal(updated)

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO messages
                (conversation_id, role, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    role,
                    content,
                    json.dumps(metadata or {}, separators=(",", ":")),
                    utc_now(),
                ),
            )

    def conversation(self, conversation_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT role, content, metadata_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (conversation_id, max(1, min(limit, 100))),
            ).fetchall()
        result = []
        for row in reversed(rows):
            entry = dict(row)
            entry["metadata"] = json.loads(entry.pop("metadata_json"))
            result.append(entry)
        return result

    def add_knowledge(
        self,
        *,
        stream: str,
        title: str,
        content: str,
        source: str,
        confidence: float,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        knowledge_id = str(uuid.uuid4())
        now = utc_now()
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO knowledge
                (id, stream, title, content, source, confidence, metadata_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    knowledge_id,
                    stream,
                    title,
                    content,
                    source,
                    float(confidence),
                    json.dumps(metadata or {}, separators=(",", ":")),
                    now,
                    now,
                ),
            )
            self._audit(
                connection,
                actor="web-learning",
                action="knowledge.learned",
                target_type="knowledge",
                target_id=knowledge_id,
                details={"stream": stream, "source": source, "confidence": confidence},
            )
            row = connection.execute("SELECT * FROM knowledge WHERE id = ?", (knowledge_id,)).fetchone()
        return self._decode_knowledge(row)

    def list_knowledge(self, *, stream: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = "SELECT * FROM knowledge"
        values: list[Any] = []
        if stream:
            query += " WHERE stream = ?"
            values.append(stream)
        query += " ORDER BY created_at DESC LIMIT ?"
        values.append(max(1, min(limit, 500)))
        with self.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._decode_knowledge(row) for row in rows]

    def search_knowledge(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        clean = query.strip()
        if not clean:
            return []
        escaped = clean.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = "%" + escaped + "%"
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM knowledge
                WHERE title LIKE ? ESCAPE '\\'
                   OR content LIKE ? ESCAPE '\\'
                   OR source LIKE ? ESCAPE '\\'
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, max(1, min(limit, 200))),
            ).fetchall()
        return [self._decode_knowledge(row) for row in rows]

    def create_research_question(
        self,
        *,
        query: str,
        rationale: str = "",
        anchor_id: str | None = None,
        priority: int = 2,
        generated_by: str = "webbie",
    ) -> dict[str, Any]:
        clean = query.strip()
        if not clean:
            raise ValueError("research query is required")
        if anchor_id and not self.get_space(anchor_id):
            raise ValueError("unknown anchor")
        now = utc_now()
        question_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO research_questions
                (id, query, rationale, anchor_id, priority, status, generated_by, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?)
                """,
                (
                    question_id,
                    clean,
                    rationale.strip(),
                    anchor_id,
                    max(0, min(int(priority), 4)),
                    generated_by,
                    now,
                    now,
                ),
            )
            self._audit(
                connection,
                actor=generated_by,
                action="research.queued",
                target_type="research_question",
                target_id=question_id,
                details={"query": clean, "anchor_id": anchor_id},
            )
            row = connection.execute(
                "SELECT * FROM research_questions WHERE id = ?", (question_id,)
            ).fetchone()
        return dict(row)

    def list_research_questions(
        self, *, status: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM research_questions"
        values: list[Any] = []
        if status:
            query += " WHERE status = ?"
            values.append(status)
        query += " ORDER BY priority DESC, created_at ASC LIMIT ?"
        values.append(max(1, min(limit, 500)))
        with self.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def set_research_status(self, question_id: str, status: str) -> dict[str, Any]:
        if status not in {"queued", "running", "completed", "failed"}:
            raise ValueError("invalid research status")
        with self.transaction() as connection:
            cursor = connection.execute(
                "UPDATE research_questions SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now(), question_id),
            )
            if cursor.rowcount != 1:
                raise ValueError("research question not found")
            row = connection.execute(
                "SELECT * FROM research_questions WHERE id = ?", (question_id,)
            ).fetchone()
        return dict(row)

    def add_research_source(
        self,
        *,
        question_id: str,
        url: str,
        title: str = "",
        snippet: str = "",
        source_type: str = "web",
        quality: float = 0.5,
    ) -> dict[str, Any]:
        source_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO research_sources
                (id, question_id, url, title, snippet, source_type, quality, retrieved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source_id,
                    question_id,
                    url.strip(),
                    title.strip(),
                    snippet.strip(),
                    source_type,
                    max(0.0, min(float(quality), 1.0)),
                    utc_now(),
                ),
            )
            row = connection.execute(
                "SELECT * FROM research_sources WHERE id = ?", (source_id,)
            ).fetchone()
        return dict(row)

    def add_research_finding(
        self,
        *,
        question_id: str,
        title: str,
        summary: str,
        confidence: float = 0.5,
        urgency: str = "quiet",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if urgency not in {"quiet", "worth-knowing", "important"}:
            raise ValueError("invalid finding urgency")
        finding_id = str(uuid.uuid4())
        with self.transaction() as connection:
            connection.execute(
                """
                INSERT INTO research_findings
                (id, question_id, title, summary, confidence, urgency, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    finding_id,
                    question_id,
                    title.strip(),
                    summary.strip(),
                    max(0.0, min(float(confidence), 1.0)),
                    urgency,
                    json.dumps(metadata or {}, separators=(",", ":")),
                    utc_now(),
                ),
            )
            self._audit(
                connection,
                actor="web-research",
                action="research.finding",
                target_type="research_finding",
                target_id=finding_id,
                details={"question_id": question_id, "urgency": urgency},
            )
            row = connection.execute(
                "SELECT * FROM research_findings WHERE id = ?", (finding_id,)
            ).fetchone()
        return self._decode_research_finding(row)

    def list_research_findings(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM research_findings ORDER BY created_at DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [self._decode_research_finding(row) for row in rows]

    def add_alert(
        self,
        *,
        alert_type: str,
        title: str,
        body: str = "",
        urgency: str = "quiet",
        source_kind: str | None = None,
        source_id: str | None = None,
        due_at: str | None = None,
    ) -> dict[str, Any] | None:
        if urgency not in {"quiet", "worth-knowing", "important"}:
            raise ValueError("invalid alert urgency")
        alert_id = str(uuid.uuid4())
        with self.transaction() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO proactive_alerts
                    (id, alert_type, title, body, urgency, source_kind, source_id, status, due_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'unread', ?, ?)
                    """,
                    (
                        alert_id,
                        alert_type,
                        title.strip(),
                        body.strip(),
                        urgency,
                        source_kind,
                        source_id,
                        due_at,
                        utc_now(),
                    ),
                )
            except sqlite3.IntegrityError:
                return None
            row = connection.execute(
                "SELECT * FROM proactive_alerts WHERE id = ?", (alert_id,)
            ).fetchone()
        return dict(row)

    def list_alerts(
        self, *, status: str | None = "unread", limit: int = 100
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM proactive_alerts"
        values: list[Any] = []
        if status:
            query += " WHERE status = ?"
            values.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        values.append(max(1, min(limit, 500)))
        with self.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [dict(row) for row in rows]

    def audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM audit_log ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        result = []
        for row in rows:
            entry = dict(row)
            entry["details"] = json.loads(entry.pop("details_json"))
            result.append(entry)
        return result

    @staticmethod
    def _audit(
        connection: sqlite3.Connection,
        *,
        actor: str,
        action: str,
        target_type: str | None,
        target_id: str | None,
        details: dict[str, Any],
    ) -> None:
        connection.execute(
            """
            INSERT INTO audit_log
            (actor, action, target_type, target_id, details_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                actor,
                action,
                target_type,
                target_id,
                json.dumps(details, separators=(",", ":")),
                utc_now(),
            ),
        )

    @staticmethod
    def _decode_item(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        return item

    @staticmethod
    def _decode_knowledge(row: sqlite3.Row) -> dict[str, Any]:
        entry = dict(row)
        entry["metadata"] = json.loads(entry.pop("metadata_json"))
        return entry

    @staticmethod
    def _decode_research_finding(row: sqlite3.Row) -> dict[str, Any]:
        entry = dict(row)
        entry["metadata"] = json.loads(entry.pop("metadata_json"))
        return entry

    @staticmethod
    def _decode_proposal(row: sqlite3.Row) -> dict[str, Any]:
        proposal = dict(row)
        proposal["arguments"] = json.loads(proposal.pop("arguments_json"))
        raw_result = proposal.pop("result_json")
        proposal["result"] = json.loads(raw_result) if raw_result else None
        return proposal
