from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .db import Database


class ProactiveEngine:
    """Creates reviewable alerts Webbie may surface or speak."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @staticmethod
    def _parse_due(value: str, now: datetime) -> datetime:
        due = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if due.tzinfo is None:
            due = due.replace(tzinfo=now.tzinfo)
        return due

    def scan_due_threads(self, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.now().astimezone()
        created: list[dict[str, Any]] = []
        for item in self.database.list_items(limit=500):
            if item["status"] in {"done", "archived"} or not item.get("due_at"):
                continue
            due = self._parse_due(str(item["due_at"]), current)
            remaining = due - current
            if remaining.total_seconds() < 0:
                alert_type, urgency, label = "overdue", "important", "Overdue"
            elif remaining <= timedelta(hours=24):
                alert_type, urgency, label = "due-24h", "important", "Due within 24 hours"
            elif remaining <= timedelta(hours=72):
                alert_type, urgency, label = "due-72h", "worth-knowing", "Due within 3 days"
            else:
                continue
            alert = self.database.add_alert(
                alert_type=alert_type,
                title=f"{label}: {item['title']}",
                body=f"Anchor: {item['space_id']}",
                urgency=urgency,
                source_kind="item",
                source_id=item["id"],
                due_at=str(item["due_at"]),
            )
            if alert:
                created.append(alert)
        return created

    def surface_research_findings(self) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        for finding in self.database.list_research_findings(limit=100):
            if finding["urgency"] == "quiet":
                continue
            alert = self.database.add_alert(
                alert_type="research-finding",
                title="Webbie found something",
                body=finding["title"],
                urgency=finding["urgency"],
                source_kind="research_finding",
                source_id=finding["id"],
                due_at=finding["created_at"],
            )
            if alert:
                created.append(alert)
        return created

    def briefing(self) -> dict[str, Any]:
        alerts = self.database.list_alerts(status="unread", limit=100)
        important = [alert for alert in alerts if alert["urgency"] == "important"]
        worth_knowing = [alert for alert in alerts if alert["urgency"] == "worth-knowing"]
        return {
            "important": important,
            "worth_knowing": worth_knowing,
            "quiet": [alert for alert in alerts if alert["urgency"] == "quiet"],
            "speak": bool(important or worth_knowing),
        }
