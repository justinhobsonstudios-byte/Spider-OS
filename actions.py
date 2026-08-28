from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .db import Database
from .authority import GraduatedAuthority
from .personal_web import PersonalKnowledgeWeb


@dataclass(frozen=True)
class ActionDefinition:
    name: str
    description: str
    mode: str
    risk_level: str
    parameters: dict[str, Any]

    def as_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


ACTION_DEFINITIONS = {
    "list_items": ActionDefinition(
        name="list_items",
        description="Read tasks, notes, projects, events, or check-ins from an anchor.",
        mode="read",
        risk_level="low",
        parameters={
            "type": "object",
            "properties": {
                "space_id": {"type": "string"},
                "status": {"type": "string"},
                "kind": {"type": "string"},
            },
            "additionalProperties": False,
        },
    ),
    "search_items": ActionDefinition(
        name="search_items",
        description="Search the user's Spider OS items by words in their titles or bodies.",
        mode="read",
        risk_level="low",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    "search_knowledge": ActionDefinition(
        name="search_knowledge",
        description="Search Webbie's learned knowledge from Cory, study materials, and sourced internet research.",
        mode="read",
        risk_level="low",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    ),
    "list_research_findings": ActionDefinition(
        name="list_research_findings",
        description="Read recent sourced findings from Webbie's autonomous Research Web.",
        mode="read",
        risk_level="low",
        parameters={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    "queue_research": ActionDefinition(
        name="queue_research",
        description="Queue a research question Webbie can investigate autonomously with source provenance.",
        mode="routine",
        risk_level="low",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "rationale": {"type": "string"},
                "anchor_id": {"type": ["string", "null"]},
                "priority": {"type": "integer", "minimum": 0, "maximum": 4},
            },
            "required": ["query", "rationale"],
            "additionalProperties": False,
        },
    ),
    "remember_personal": ActionDefinition(
        name="remember_personal",
        description="Add a reviewable fact, observation, or inference to the Personal Knowledge Web.",
        mode="routine",
        risk_level="low",
        parameters={
            "type": "object",
            "properties": {
                "memory_kind": {"type": "string", "enum": ["fact", "observation", "inference"]},
                "content": {"type": "string"},
                "source": {"type": "string"},
                "title": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                "sensitivity": {"type": "string", "enum": ["standard", "private", "restricted"]},
            },
            "required": ["memory_kind", "content", "source"],
            "additionalProperties": False,
        },
    ),
    "create_item": ActionDefinition(
        name="create_item",
        description="Propose creating a task, note, event, project, or check-in.",
        mode="approval",
        risk_level="medium",
        parameters={
            "type": "object",
            "properties": {
                "space_id": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": ["task", "note", "event", "project", "checkin"],
                },
                "title": {"type": "string"},
                "body": {"type": "string"},
                "due_at": {"type": ["string", "null"]},
                "priority": {"type": "integer", "minimum": 0, "maximum": 4},
                "sensitivity": {
                    "type": "string",
                    "enum": ["standard", "private", "restricted"],
                },
            },
            "required": ["space_id", "kind", "title"],
            "additionalProperties": False,
        },
    ),
    "complete_item": ActionDefinition(
        name="complete_item",
        description="Propose marking a specific item complete.",
        mode="approval",
        risk_level="medium",
        parameters={
            "type": "object",
            "properties": {"item_id": {"type": "string"}},
            "required": ["item_id"],
            "additionalProperties": False,
        },
    ),
}


class ActionBroker:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.authority = GraduatedAuthority()
        self.personal_web = PersonalKnowledgeWeb(database)

    @property
    def tools(self) -> list[dict[str, Any]]:
        return [definition.as_tool() for definition in ACTION_DEFINITIONS.values()]

    def handle_ai_call(
        self, name: str, arguments: dict[str, Any], rationale: str = ""
    ) -> dict[str, Any]:
        definition = ACTION_DEFINITIONS.get(name)
        if not definition:
            return {"type": "error", "error": "That action is not available."}
        try:
            self._validate_shape(name, arguments)
            authority = self.authority.classify(name, arguments)
            if definition.mode == "read" or not authority.requires_confirmation:
                return {
                    "type": "result",
                    "action": name,
                    "authority_tier": authority.tier,
                    "data": self._execute(name, arguments, actor="web-auto" if definition.mode != "read" else "ai"),
                }
            proposal = self.database.create_proposal(
                action_name=name,
                arguments=arguments,
                rationale=rationale,
                risk_level=definition.risk_level,
            )
            return {"type": "proposal", "proposal": proposal}
        except (TypeError, ValueError) as error:
            return {"type": "error", "error": str(error)}

    def approve(self, proposal_id: str) -> dict[str, Any]:
        proposal = self.database.claim_proposal(proposal_id)
        try:
            result = self._execute(
                proposal["action_name"], proposal["arguments"], actor="approved_ai"
            )
        except Exception as error:
            self.database.decide_proposal(
                proposal_id, status="failed", result={"error": str(error)}
            )
            raise
        decided = self.database.decide_proposal(
            proposal_id, status="approved", result={"data": result}
        )
        return decided

    def reject(self, proposal_id: str) -> dict[str, Any]:
        return self.database.decide_proposal(proposal_id, status="rejected")

    def _execute(
        self, name: str, arguments: dict[str, Any], *, actor: str
    ) -> Any:
        operations: dict[str, Callable[[], Any]] = {
            "list_items": lambda: self.database.list_items(
                space_id=arguments.get("space_id"),
                status=arguments.get("status"),
                kind=arguments.get("kind"),
                limit=100,
            ),
            "search_items": lambda: self.database.search_items(
                str(arguments.get("query", "")), limit=50
            ),
            "search_knowledge": lambda: self.database.search_knowledge(
                str(arguments.get("query", "")), limit=50
            ),
            "list_research_findings": lambda: self.database.list_research_findings(limit=50),
            "queue_research": lambda: self.database.create_research_question(
                query=str(arguments["query"]),
                rationale=str(arguments.get("rationale", "")),
                anchor_id=arguments.get("anchor_id"),
                priority=int(arguments.get("priority", 2)),
                generated_by="webbie",
            ),
            "remember_personal": lambda: self.personal_web.remember(
                kind=str(arguments["memory_kind"]),
                content=str(arguments["content"]),
                source=str(arguments["source"]),
                title=str(arguments.get("title", "")),
                confidence=(float(arguments["confidence"]) if "confidence" in arguments else None),
                evidence_ids=[str(value) for value in arguments.get("evidence_ids", [])],
                metadata={"sensitivity": str(arguments.get("sensitivity", "standard"))},
            ),
            "create_item": lambda: self.database.create_item(
                space_id=str(arguments["space_id"]),
                kind=str(arguments["kind"]),
                title=str(arguments["title"]),
                body=str(arguments.get("body", "")),
                due_at=arguments.get("due_at"),
                priority=int(arguments.get("priority", 2)),
                sensitivity=str(arguments.get("sensitivity", "standard")),
                actor=actor,
            ),
            "complete_item": lambda: self.database.set_item_status(
                str(arguments["item_id"]), "done", actor=actor
            ),
        }
        operation = operations.get(name)
        if not operation:
            raise ValueError("action is not executable")
        return operation()

    def _validate_shape(self, name: str, arguments: dict[str, Any]) -> None:
        if not isinstance(arguments, dict):
            raise TypeError("action arguments must be an object")
        if name in {"search_items", "search_knowledge"} and not str(arguments.get("query", "")).strip():
            raise ValueError("a search query is required")
        if name == "queue_research" and not str(arguments.get("query", "")).strip():
            raise ValueError("a research query is required")
        if name == "remember_personal":
            if not str(arguments.get("content", "")).strip() or not str(arguments.get("source", "")).strip():
                raise ValueError("personal memory requires content and provenance")
            if str(arguments.get("memory_kind", "")) == "inference" and not arguments.get("evidence_ids"):
                raise ValueError("personal inferences require evidence ids")
        if name == "create_item":
            required = {"space_id", "kind", "title"}
            missing = required.difference(arguments)
            if missing:
                raise ValueError("missing " + ", ".join(sorted(missing)))
            if not self.database.get_space(str(arguments["space_id"])):
                raise ValueError("unknown anchor")
        if name == "complete_item" and not str(arguments.get("item_id", "")).strip():
            raise ValueError("an item id is required")
