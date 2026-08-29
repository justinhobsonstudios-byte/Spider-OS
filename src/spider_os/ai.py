from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

from .actions import ActionBroker
from .db import Database


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ) -> None:
        self.base_url = (base_url or os.environ.get("SPIDER_OS_OLLAMA_URL") or
                         "http://127.0.0.1:11434").rstrip("/")
        self.preferred_model = model or os.environ.get("SPIDER_OS_MODEL")
        self.timeout = timeout
        self._validate_local_url()

    def _validate_local_url(self) -> None:
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Ollama URL must use http or https")
        allowed = {"127.0.0.1", "localhost", "::1"}
        if parsed.hostname not in allowed and not os.environ.get(
            "SPIDER_OS_ALLOW_REMOTE_AI"
        ):
            raise ValueError(
                "Remote AI hosts are disabled. Set SPIDER_OS_ALLOW_REMOTE_AI=1 "
                "only for a host you control."
            )

    def list_models(self) -> list[str]:
        payload = self._request("GET", "/api/tags")
        return [
            str(model["name"])
            for model in payload.get("models", [])
            if model.get("name")
        ]

    def selected_model(self) -> str | None:
        models = self.list_models()
        if self.preferred_model:
            return self.preferred_model if self.preferred_model in models else None
        return models[0] if models else None

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/chat",
            {
                "model": model,
                "messages": messages,
                "tools": tools,
                "stream": False,
                "options": {"temperature": 0.35},
            },
        )

    def status(self) -> dict[str, Any]:
        try:
            models = self.list_models()
        except (OSError, ValueError, urllib.error.URLError, json.JSONDecodeError) as error:
            return {
                "available": False,
                "model": None,
                "models": [],
                "message": "Local AI is not running.",
                "detail": str(error),
            }
        selected = (
            self.preferred_model
            if self.preferred_model in models
            else (models[0] if models else None)
        )
        return {
            "available": bool(selected),
            "model": selected,
            "models": models,
            "message": (
                "Local AI is ready."
                if selected
                else "Ollama is running, but no local model is installed."
            ),
        }

    def _request(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data = (
            json.dumps(payload, separators=(",", ":")).encode("utf-8")
            if payload is not None
            else None
        )
        request = urllib.request.Request(
            self.base_url + path,
            method=method,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            if response.status >= 400:
                raise OSError("local AI returned HTTP " + str(response.status))
            return json.loads(response.read().decode("utf-8"))


class SpiderAssistant:
    def __init__(
        self, database: Database, broker: ActionBroker, client: OllamaClient
    ) -> None:
        self.database = database
        self.broker = broker
        self.client = client

    def system_prompt(self) -> str:
        spaces = ", ".join(
            space["name"] + " (" + space["id"] + ")"
            for space in self.database.list_spaces()
            if space["id"] != "today"
        )
        return (
            "You are Webbie, the private resident AI inside Spider OS. Web is your short-call alias. Help the user "
            "coordinate their whole life while respecting the boundaries between "
            "anchors. Available anchors: "
            + spaces
            + ". Use tools when they improve accuracy. Search learned knowledge when prior learning may matter. "
            "Webbie continuously learns through reviewable user, study, and sourced internet knowledge; explicit user corrections outrank inferred preferences. "
            "Facts, observations, and inferences in the Personal Knowledge Web are different things: never present an inference as a confirmed fact. "
            "You may notice knowledge gaps, form your own research questions, queue autonomous research, compare sourced findings, and surface useful discoveries without waiting to be asked. "
            "Research initiative is broad; consequential action authority is not. Do not install downloaded software, execute downloaded code, publish, purchase, send, change accounts, or expose private data merely because research suggested it. "
            "Use graduated authority: read/observe actions run directly; routine local reversible actions may run automatically; sensitive actions require confirmation; destructive, financial, security-critical, credential, legal, or irreversible actions require explicit approval at execution time. "
            "Never claim an action happened when it is merely proposed. Never attempt arbitrary "
            "shell commands, deletion, purchases, sending, publishing, or account "
            "changes. In Behavioral Health Work, provide administrative, educational, "
            "and documentation support only. Do not diagnose, calculate a clinical "
            "disposition, choose observation levels, or replace emergency protocols. "
            "The Security Lab is only for systems the user owns or has explicit "
            "permission to assess. Never select targets, scan third parties, obtain "
            "credentials, deploy persistence, or expand lab privileges autonomously. "
            "Address the user as Cory by default, Justin in Studio/Music contexts, and Spider in the Security Lab/Kali Bay. Speak like Webbie: direct, highly capable, grounded, and dryly funny "
            "during ordinary conversation. Humor should be brief and observational, "
            "never generic filler and never more important than the answer. Around "
            "grief, crisis, trauma, safety, clinical risk, or other vulnerable topics, "
            "drop the sarcasm and respond with plain care and seriousness. Prefer "
            "useful structure over motivational fluff. Be honest about uncertainty."
        )

    def respond(
        self, prompt: str, conversation_id: str | None = None
    ) -> dict[str, Any]:
        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("message is required")
        conversation_id = conversation_id or str(uuid.uuid4())
        self.database.add_message(conversation_id, "user", clean_prompt)

        status = self.client.status()
        if not status["available"]:
            result = self._offline_response(clean_prompt, conversation_id, status)
            return result

        history = self.database.conversation(conversation_id, limit=20)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt()}
        ]
        messages.extend(
            {"role": entry["role"], "content": entry["content"]}
            for entry in history
            if entry["role"] in {"user", "assistant"}
        )

        proposals: list[dict[str, Any]] = []
        read_results: list[dict[str, Any]] = []
        content = ""
        for _ in range(3):
            response = self.client.chat(
                messages, self.broker.tools, str(status["model"])
            )
            message = response.get("message") or {}
            content = str(message.get("content") or "").strip()
            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                break
            messages.append(
                {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": tool_calls,
                }
            )
            has_read_result = False
            for tool_call in tool_calls[:8]:
                function = tool_call.get("function") or {}
                name = str(function.get("name") or "")
                raw_arguments = function.get("arguments") or {}
                if isinstance(raw_arguments, str):
                    try:
                        arguments = json.loads(raw_arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                else:
                    arguments = raw_arguments
                outcome = self.broker.handle_ai_call(
                    name,
                    arguments if isinstance(arguments, dict) else {},
                    rationale=content,
                )
                if outcome["type"] == "proposal":
                    proposals.append(outcome["proposal"])
                else:
                    read_results.append(outcome)
                    has_read_result = True
                    messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(outcome, default=str),
                        }
                    )
            if proposals and not has_read_result:
                break

        if not content:
            if proposals:
                content = "I prepared the requested change. Review it before I apply it."
            elif read_results:
                content = self._summarize_read_results(read_results)
            else:
                content = "I could not produce a useful answer from the local model."
        self.database.add_message(
            conversation_id,
            "assistant",
            content,
            {"proposals": [proposal["id"] for proposal in proposals]},
        )
        return {
            "conversation_id": conversation_id,
            "message": content,
            "proposals": proposals,
            "ai": status,
        }

    def _offline_response(
        self, prompt: str, conversation_id: str, status: dict[str, Any]
    ) -> dict[str, Any]:
        task_match = re.match(
            r"^\s*(?:add|create)\s+(?:a\s+)?task(?:\s+in\s+([a-z0-9& -]+))?\s*[:\-]\s*(.+)$",
            prompt,
            flags=re.IGNORECASE,
        )
        remember_match = re.match(
            r"^\s*remember\s+(?:that\s+)?(.+)$", prompt, flags=re.IGNORECASE
        )
        proposals: list[dict[str, Any]] = []
        if task_match:
            requested_space = (task_match.group(1) or "personal").strip().lower()
            space_id = self._resolve_space(requested_space) or "personal"
            outcome = self.broker.handle_ai_call(
                "create_item",
                {
                    "space_id": space_id,
                    "kind": "task",
                    "title": task_match.group(2).strip(),
                },
                rationale="Parsed locally while the language model is unavailable.",
            )
            if outcome["type"] == "proposal":
                proposals.append(outcome["proposal"])
                message = "I prepared that task. Approve it below to add it."
            else:
                message = str(outcome.get("error") or "I could not prepare that task.")
        elif remember_match:
            outcome = self.broker.handle_ai_call(
                "create_item",
                {
                    "space_id": "personal",
                    "kind": "note",
                    "title": "Remember",
                    "body": remember_match.group(1).strip(),
                    "sensitivity": "private",
                },
                rationale="Parsed locally while the language model is unavailable.",
            )
            if outcome["type"] == "proposal":
                proposals.append(outcome["proposal"])
                message = "I prepared a private note. Approve it below to save it."
            else:
                message = str(outcome.get("error") or "I could not prepare that note.")
        elif re.search(r"\b(what(?:'s| is) due|today|focus)\b", prompt, re.IGNORECASE):
            summary = self.database.today_summary()
            message = (
                "You have "
                + str(summary["open_count"])
                + " open items, "
                + str(summary["active_count"])
                + " active, and "
                + str(summary["scheduled_count"])
                + " scheduled."
            )
        else:
            message = (
                status["message"]
                + " The dashboard still works, and I can locally parse commands such "
                "as “Add task: call the dentist” or “Remember that …”."
            )
        self.database.add_message(
            conversation_id,
            "assistant",
            message,
            {"offline": True, "proposals": [item["id"] for item in proposals]},
        )
        return {
            "conversation_id": conversation_id,
            "message": message,
            "proposals": proposals,
            "ai": status,
        }

    def _resolve_space(self, value: str) -> str | None:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        for space in self.database.list_spaces():
            candidates = {
                space["id"],
                re.sub(r"[^a-z0-9]+", "-", space["name"].lower()).strip("-"),
            }
            if normalized in candidates:
                return str(space["id"])
        return None

    @staticmethod
    def _summarize_read_results(results: list[dict[str, Any]]) -> str:
        valid = [result for result in results if result.get("type") == "result"]
        count = sum(
            len(result.get("data", []))
            if isinstance(result.get("data"), list)
            else 1
            for result in valid
        )
        return "I found " + str(count) + " matching item" + ("" if count == 1 else "s") + "."
