from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .db import Database
from .learning import LearningEngine

MEMORY_KINDS = {"fact", "observation", "inference", "correction"}


@dataclass(frozen=True)
class PersonalMemoryPolicy:
    inference_is_not_fact: bool = True
    provenance_required: bool = True
    corrections_override_inferences: bool = True
    reviewable: bool = True
    forgettable: bool = True

    def as_dict(self) -> dict[str, bool]:
        return {
            "inference_is_not_fact": self.inference_is_not_fact,
            "provenance_required": self.provenance_required,
            "corrections_override_inferences": self.corrections_override_inferences,
            "reviewable": self.reviewable,
            "forgettable": self.forgettable,
        }


class PersonalKnowledgeWeb:
    """Reviewable personal memory for Webbie.

    Facts, observations and inferences remain distinguishable in metadata. A
    correction is appended as a new sourced memory instead of silently rewriting
    history, which preserves provenance and makes changing context inspectable.
    """

    def __init__(self, database: Database) -> None:
        self.database = database
        self.learning = LearningEngine(database)
        self.policy = PersonalMemoryPolicy()

    def remember(
        self,
        *,
        kind: str,
        content: str,
        source: str,
        title: str = "",
        confidence: float | None = None,
        evidence_ids: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if kind not in MEMORY_KINDS:
            raise ValueError("unknown personal memory kind")
        if kind == "inference" and not evidence_ids:
            raise ValueError("an inference requires evidence ids")
        default_confidence = {
            "fact": 0.98,
            "observation": 0.82,
            "inference": 0.65,
            "correction": 1.0,
        }[kind]
        memory_metadata = dict(metadata or {})
        memory_metadata.update(
            {
                "personal_knowledge": True,
                "memory_kind": kind,
                "evidence_ids": list(evidence_ids or []),
            }
        )
        return self.learning.ingest(
            stream="user",
            title=title,
            content=content,
            source=source,
            confidence=default_confidence if confidence is None else confidence,
            metadata=memory_metadata,
        )

    def correct(
        self,
        *,
        content: str,
        source: str,
        supersedes_ids: list[str],
        title: str = "Correction",
    ) -> dict[str, Any]:
        if not supersedes_ids:
            raise ValueError("a correction must identify what it supersedes")
        return self.remember(
            kind="correction",
            content=content,
            source=source,
            title=title,
            confidence=1.0,
            metadata={"supersedes_ids": supersedes_ids},
        )

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            row
            for row in self.database.list_knowledge(stream="user", limit=limit)
            if row.get("metadata", {}).get("personal_knowledge")
        ]
