from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .db import Database


LEARNING_STREAMS = ("user", "study", "internet")


@dataclass(frozen=True)
class LearningPolicy:
    enabled: bool = True
    learn_from_user: bool = True
    learn_from_studies: bool = True
    learn_from_internet: bool = True
    internet_scope: str = "broad-source-scored"
    train_base_model_weights: bool = False
    provenance_required: bool = True
    confidence_required: bool = True
    reviewable_memory: bool = True
    corrections_override_inferences: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "streams": {
                "user": self.learn_from_user,
                "study": self.learn_from_studies,
                "internet": self.learn_from_internet,
            },
            "internet_scope": self.internet_scope,
            "train_base_model_weights": self.train_base_model_weights,
            "provenance_required": self.provenance_required,
            "confidence_required": self.confidence_required,
            "reviewable_memory": self.reviewable_memory,
            "corrections_override_inferences": self.corrections_override_inferences,
        }


class LearningEngine:
    """Persistent learning layer for Webbie.

    Learning means adding reviewable knowledge/memory with provenance. It does not
    mutate the model weights or Webbie's locked safety/personality configuration.
    """

    def __init__(self, database: Database, policy: LearningPolicy | None = None) -> None:
        self.database = database
        self.policy = policy or LearningPolicy()

    def ingest(
        self,
        *,
        stream: str,
        content: str,
        source: str,
        confidence: float = 0.7,
        title: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.policy.enabled:
            raise ValueError("learning is disabled")
        if stream not in LEARNING_STREAMS:
            raise ValueError("unknown learning stream")
        if not self.policy.as_dict()["streams"][stream]:
            raise ValueError(f"{stream} learning is disabled")
        clean = content.strip()
        if not clean:
            raise ValueError("learning content is required")
        clean_source = source.strip()
        if not clean_source:
            raise ValueError("a source/provenance value is required")
        confidence = max(0.0, min(float(confidence), 1.0))
        return self.database.add_knowledge(
            stream=stream,
            title=title.strip(),
            content=clean,
            source=clean_source,
            confidence=confidence,
            metadata=metadata or {},
        )

    def recent(self, *, stream: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        return self.database.list_knowledge(stream=stream, limit=limit)
