from __future__ import annotations

import json
import os
import signal
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constants import AI_NAME, DEFAULT_ADDRESS_NAMES, DEFAULT_HOST, DEFAULT_PORT, DEFAULT_WAKE_PHRASES
from .db import Database, default_data_dir
from .proactive import ProactiveEngine
from .research import ResearchEngine


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ResidentAgent:
    """Always-on Webbie presence coordinator for Spider OS.

    The resident does not record audio itself. Voice wake-word engines and event
    adapters feed activation/events into this process later. Its job is to keep
    presence state, watch the local core, and provide a stable place for proactive
    integrations to attach without giving the model unrestricted OS privileges.
    """

    def __init__(self, interval: float = 5.0) -> None:
        self.interval = max(1.0, float(interval))
        self.data_dir = default_data_dir()
        self.runtime_dir = self.data_dir / "runtime"
        self.state_path = self.runtime_dir / "resident.json"
        self.host = os.environ.get("SPIDER_OS_HOST", DEFAULT_HOST)
        self.port = int(os.environ.get("SPIDER_OS_PORT", str(DEFAULT_PORT)))
        self.wake_phrases = tuple(phrase.strip() for phrase in os.environ.get("SPIDER_OS_WAKE_PHRASES", ",".join(DEFAULT_WAKE_PHRASES)).split(",") if phrase.strip()) or DEFAULT_WAKE_PHRASES
        self.voice_enabled = os.environ.get("SPIDER_OS_VOICE_ENABLED", "1") != "0"
        self.proactive_enabled = os.environ.get("SPIDER_OS_PROACTIVE", "1") != "0"
        self.proactive_level = os.environ.get("SPIDER_OS_PROACTIVE_LEVEL", "very-high")
        self.screen_awareness = os.environ.get("SPIDER_OS_SCREEN_AWARENESS", "1") != "0"
        self.screen_archive = os.environ.get("SPIDER_OS_SCREEN_ARCHIVE", "0") == "1"
        self.visual_presence = os.environ.get("SPIDER_OS_VISUAL_PRESENCE", "taskbar+edge-orb")
        self.attention_style = os.environ.get("SPIDER_OS_ATTENTION_STYLE", "cue-then-speak")
        self.memory_learning = os.environ.get("SPIDER_OS_MEMORY_LEARNING", "continuous-transparent")
        self.learning_user = os.environ.get("SPIDER_OS_LEARN_USER", "1") != "0"
        self.learning_studies = os.environ.get("SPIDER_OS_LEARN_STUDIES", "1") != "0"
        self.learning_internet = os.environ.get("SPIDER_OS_LEARN_INTERNET", "1") != "0"
        self.internet_learning_scope = os.environ.get("SPIDER_OS_INTERNET_LEARNING_SCOPE", "broad-source-scored")
        self.authority_model = "graduated"
        self.database = Database(self.data_dir)
        self.database.initialize()
        self.research = ResearchEngine(self.database)
        self.proactive = ProactiveEngine(self.database)
        self.last_research_error: str | None = None
        self.last_research_at: str | None = None
        self.last_proactive_at: str | None = None
        self._next_research = 0.0
        self._next_proactive = 0.0
        self.running = True

    def _stop(self, *_: object) -> None:
        self.running = False

    def core_ready(self) -> bool:
        request = urllib.request.Request(
            f"http://{self.host}:{self.port}/api/health",
            headers={"Host": f"{self.host}:{self.port}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=1.5) as response:
                return response.status == 200
        except (OSError, urllib.error.URLError, TimeoutError):
            return False

    def state(self, core_ready: bool) -> dict[str, Any]:
        return {
            "active": True,
            "mode": "resident",
            "core_ready": core_ready,
            "voice_enabled": self.voice_enabled,
            "ai_name": AI_NAME,
            "wake_phrases": list(self.wake_phrases),
            "address_names": DEFAULT_ADDRESS_NAMES,
            "proactive_enabled": self.proactive_enabled,
            "proactive_level": self.proactive_level,
            "attention_style": self.attention_style,
            "visual_presence": self.visual_presence,
            "screen_awareness": self.screen_awareness,
            "screen_processing": "local",
            "screen_frames_archived": self.screen_archive,
            "screen_exclusions_supported": True,
            "screen_indicator_required": True,
            "memory_learning": self.memory_learning,
            "learning_streams": {
                "user": self.learning_user,
                "study": self.learning_studies,
                "internet": self.learning_internet,
            },
            "internet_learning_scope": self.internet_learning_scope,
            "knowledge_provenance_required": True,
            "base_model_self_retraining": False,
            "memory_review_required": True,
            "authority_model": self.authority_model,
            "authority_tiers": ["observe", "routine-auto", "sensitive-confirm", "critical-explicit"],
            "ambient_audio_stored": False,
            "arbitrary_shell_access": False,
            "autonomous_research": self.learning_internet,
            "research_provider": "local-searxng",
            "last_research_at": self.last_research_at,
            "last_research_error": self.last_research_error,
            "last_proactive_scan": self.last_proactive_at,
            "last_heartbeat": utc_now(),
        }

    def write_state(self, payload: dict[str, Any]) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        tmp = self.state_path.with_suffix(".tmp")
        previous_umask = os.umask(0o077)
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.state_path)
        finally:
            os.umask(previous_umask)
        try:
            self.state_path.chmod(0o600)
        except OSError:
            pass

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        while self.running:
            now = time.monotonic()
            if self.proactive_enabled and now >= self._next_proactive:
                try:
                    self.proactive.scan_due_threads()
                    self.proactive.surface_research_findings()
                    self.last_proactive_at = utc_now()
                finally:
                    self._next_proactive = now + 60.0
            if self.learning_internet and now >= self._next_research:
                try:
                    self.research.derive_questions_from_threads(limit=2)
                    result = self.research.run_once()
                    if result:
                        self.last_research_at = utc_now()
                    self.last_research_error = None
                except Exception as error:
                    # Research failing must never take the resident AI down.
                    self.last_research_error = str(error)[:300]
                finally:
                    self._next_research = now + 600.0
            self.write_state(self.state(self.core_ready()))
            time.sleep(self.interval)
        final = self.state(False)
        final["active"] = False
        final["last_heartbeat"] = utc_now()
        self.write_state(final)


def read_resident_state() -> dict[str, Any]:
    path = default_data_dir() / "runtime" / "resident.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "active": False,
        "mode": "resident",
        "core_ready": False,
        "voice_enabled": False,
        "ai_name": AI_NAME,
        "wake_phrases": list(DEFAULT_WAKE_PHRASES),
        "address_names": DEFAULT_ADDRESS_NAMES,
        "proactive_enabled": False,
        "proactive_level": "very-high",
        "attention_style": "cue-then-speak",
        "visual_presence": "taskbar+edge-orb",
        "screen_awareness": False,
        "screen_processing": "local",
        "screen_frames_archived": False,
        "screen_exclusions_supported": True,
        "screen_indicator_required": True,
        "memory_learning": "continuous-transparent",
        "learning_streams": {"user": True, "study": True, "internet": True},
        "internet_learning_scope": "broad-source-scored",
        "knowledge_provenance_required": True,
        "base_model_self_retraining": False,
        "memory_review_required": True,
        "authority_model": "graduated",
        "authority_tiers": ["observe", "routine-auto", "sensitive-confirm", "critical-explicit"],
        "ambient_audio_stored": False,
        "arbitrary_shell_access": False,
        "autonomous_research": True,
        "research_provider": "local-searxng",
        "last_research_at": None,
        "last_research_error": None,
        "last_proactive_scan": None,
        "last_heartbeat": None,
    }
