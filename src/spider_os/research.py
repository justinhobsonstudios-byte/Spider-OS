from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .db import Database


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    quality: float = 0.5


class SearchProvider(Protocol):
    def search(self, query: str, limit: int = 8) -> list[SearchResult]: ...


class SearXNGProvider:
    """Local metasearch adapter used by Webbie's Research Web."""

    def __init__(self, base_url: str | None = None, timeout: float = 12.0) -> None:
        self.base_url = (base_url or os.environ.get("SPIDER_OS_SEARXNG_URL") or "http://127.0.0.1:8888").rstrip("/")
        self.timeout = timeout

    def search(self, query: str, limit: int = 8) -> list[SearchResult]:
        params = urllib.parse.urlencode({"q": query, "format": "json", "language": "all", "safesearch": 1})
        request = urllib.request.Request(
            f"{self.base_url}/search?{params}",
            headers={"Accept": "application/json", "User-Agent": "SpiderOS-Webbie/0.7"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        results: list[SearchResult] = []
        for item in payload.get("results", [])[: max(1, min(limit, 20))]:
            url = str(item.get("url", "")).strip()
            if not url:
                continue
            results.append(
                SearchResult(
                    title=str(item.get("title", "")).strip(),
                    url=url,
                    snippet=str(item.get("content", "")).strip(),
                    quality=self._quality(url),
                )
            )
        return results

    @staticmethod
    def _quality(url: str) -> float:
        host = urllib.parse.urlparse(url).hostname or ""
        if host.endswith(".gov") or host.endswith(".edu"):
            return 0.9
        if any(token in host for token in ("who.int", "apa.org", "nih.gov", "nasa.gov", "github.com")):
            return 0.9
        return 0.6


class ResearchEngine:
    """Autonomous, provenance-preserving research queue for Webbie."""

    def __init__(self, database: Database, provider: SearchProvider | None = None) -> None:
        self.database = database
        self.provider = provider or SearXNGProvider()

    def queue(
        self,
        *,
        query: str,
        rationale: str,
        anchor_id: str | None = None,
        priority: int = 2,
        generated_by: str = "webbie",
    ) -> dict[str, Any]:
        return self.database.create_research_question(
            query=query,
            rationale=rationale,
            anchor_id=anchor_id,
            priority=priority,
            generated_by=generated_by,
        )

    def derive_questions_from_threads(self, limit: int = 3) -> list[dict[str, Any]]:
        """Create research questions from active high-value Threads.

        This intentionally stays conservative. The language model can queue more
        specific questions through the action broker; this fallback ensures the
        resident can still notice obvious research gaps when the model is offline.
        """
        existing = {row["query"].casefold() for row in self.database.list_research_questions(limit=500)}
        candidates = [
            item for item in self.database.list_items(limit=500)
            if item["status"] in {"open", "active"}
            and item["kind"] in {"project", "task"}
            and int(item.get("priority", 0)) >= 3
        ]
        queued: list[dict[str, Any]] = []
        for item in candidates:
            query = f"Current reliable information that could materially help with: {item['title']}"
            if query.casefold() in existing:
                continue
            queued.append(
                self.queue(
                    query=query,
                    rationale="Webbie noticed a high-priority active Thread with a potential knowledge gap.",
                    anchor_id=item["space_id"],
                    priority=min(4, int(item.get("priority", 2))),
                )
            )
            existing.add(query.casefold())
            if len(queued) >= limit:
                break
        return queued

    def run_once(self) -> dict[str, Any] | None:
        queued = self.database.list_research_questions(status="queued", limit=1)
        if not queued:
            return None
        question = queued[0]
        self.database.set_research_status(question["id"], "running")
        try:
            results = self.provider.search(question["query"], limit=8)
            if not results:
                self.database.set_research_status(question["id"], "failed")
                return {"question": question, "status": "failed", "reason": "no sources returned"}
            sources = [
                self.database.add_research_source(
                    question_id=question["id"],
                    url=result.url,
                    title=result.title,
                    snippet=result.snippet,
                    quality=result.quality,
                )
                for result in results
            ]
            best = sorted(results, key=lambda result: result.quality, reverse=True)[:3]
            summary_parts = [result.snippet or result.title for result in best if result.snippet or result.title]
            summary = " ".join(summary_parts)[:2400]
            confidence = sum(result.quality for result in best) / max(1, len(best))
            urgency = "worth-knowing" if question["priority"] >= 3 else "quiet"
            finding = self.database.add_research_finding(
                question_id=question["id"],
                title=question["query"][:180],
                summary=summary or "Sources collected; synthesis is waiting for the local model.",
                confidence=confidence,
                urgency=urgency,
                metadata={"source_count": len(sources), "synthesis": "extractive"},
            )
            self.database.set_research_status(question["id"], "completed")
            return {"question": question, "status": "completed", "finding": finding, "sources": sources}
        except Exception:
            self.database.set_research_status(question["id"], "failed")
            raise
