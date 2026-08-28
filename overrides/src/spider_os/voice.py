from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .actions import ActionBroker
from .ai import OllamaClient, SpiderAssistant
from .constants import AI_NAME, DEFAULT_WAKE_PHRASES
from .db import Database, default_data_dir
from .setup import SetupStore


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class VoiceRuntime:
    """Local-first always-on voice presence for Webbie.

    The baseline recognizer is PocketSphinx because Fedora can ship it and its
    English acoustic model directly in the image. Audio is processed in memory.
    Ambient audio and non-addressed speech are not written to disk. Recognized
    commands addressed to Webbie become normal Spider conversation history.
    """

    name = "Webbie Voice Runtime"

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or default_data_dir()
        self.runtime_dir = self.data_dir / "runtime"
        self.state_path = self.runtime_dir / "voice.json"
        self.conversation_id: str | None = None

    def status(self) -> dict[str, Any]:
        pocketsphinx_ready = importlib.util.find_spec("pocketsphinx") is not None
        sounddevice_ready = importlib.util.find_spec("sounddevice") is not None
        tts = self._first_command("spd-say", "espeak")
        setup = SetupStore(self.data_dir).read()
        state = self.read_state()
        return {
            "name": self.name,
            "enabled": bool(setup.get("voice_enabled", True)),
            "wake_phrases": list(DEFAULT_WAKE_PHRASES),
            "audio_capture": "python-sounddevice" if sounddevice_ready else self._first_command("pw-record", "arecord"),
            "wake_engine": "pocketsphinx" if pocketsphinx_ready else None,
            "speech_to_text": {
                "baseline": "pocketsphinx" if pocketsphinx_ready else None,
                "high_accuracy": "optional-not-bundled",
            },
            "text_to_speech": tts,
            "always_on_ready": bool(pocketsphinx_ready and sounddevice_ready and tts),
            "voice_profile": {
                "presentation": "female",
                "accent": "Australian English",
                "requested_language": "en-AU",
                "requested_voice_type": "female1",
                "verified_native_voice": False,
                "provider": "speech-dispatcher-local" if tts == "spd-say" else ("espeak-local" if tts else None),
            },
            "state": state,
            "policy": self.policy(),
        }

    @staticmethod
    def policy() -> dict[str, Any]:
        return {
            "recognition": "local-only",
            "wake_detection": "local-only",
            "ambient_audio_stored": False,
            "non_addressed_speech_stored": False,
            "recognized_commands": "stored-as-conversation-history",
            "microphone_pause_supported": True,
            "screen_and_microphone_indicators_required": True,
            "cloud_voice_requires_explicit_opt_in": True,
        }

    def speak(self, text: str) -> dict[str, Any]:
        clean = " ".join(str(text).split()).strip()
        if not clean:
            raise ValueError("speech text is required")
        clean = clean[:4000]
        if shutil.which("spd-say"):
            command = [
                "spd-say",
                "--wait",
                "--language",
                "en-AU",
                "--voice-type",
                "female1",
                "--application-name",
                "Spider-OS-Webbie",
                clean,
            ]
            provider = "speech-dispatcher"
        elif shutil.which("espeak"):
            command = ["espeak", "-v", "en-au+f3", clean]
            provider = "espeak"
        else:
            raise RuntimeError("no local speech synthesizer is installed")
        result = subprocess.run(command, capture_output=True, text=True, timeout=45, check=False)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "speech synthesis failed").strip())
        return {"spoken": True, "provider": provider, "characters": len(clean)}

    def listen_forever(self, interval: float = 5.0) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._write_state({"status": "starting", "microphone_active": False})
        while True:
            setup = SetupStore(self.data_dir).read()
            if not bool(setup.get("voice_enabled", True)):
                self._write_state({"status": "paused", "microphone_active": False, "reason": "voice disabled in Spider Setup"})
                time.sleep(max(2.0, interval))
                continue
            if importlib.util.find_spec("pocketsphinx") is None or importlib.util.find_spec("sounddevice") is None:
                self._write_state({"status": "degraded", "microphone_active": False, "reason": "PocketSphinx or sounddevice unavailable"})
                time.sleep(max(5.0, interval))
                continue
            try:
                self._recognition_session()
            except KeyboardInterrupt:
                self._write_state({"status": "stopped", "microphone_active": False})
                return
            except Exception as error:
                self._write_state({"status": "degraded", "microphone_active": False, "reason": str(error)[:240]})
                time.sleep(max(2.0, interval))

    def _recognition_session(self) -> None:
        from pocketsphinx import LiveSpeech

        assistant = self._assistant()
        armed_until = 0.0
        self._write_state({"status": "listening", "microphone_active": True, "started_at": utc_now()})

        # Full local decoding lets the same stream recognize both the wake phrase
        # and the command that follows it. Speech that does not address Webbie is
        # discarded immediately and never enters Spider state.
        for phrase in LiveSpeech():
            heard = " ".join(str(phrase).lower().split()).strip()
            if not heard:
                continue
            now = time.monotonic()
            command = self._command_after_wake(heard)
            if command is not None:
                self._write_state({"status": "awake", "microphone_active": True, "last_wake_at": utc_now()})
                if command:
                    self._answer(assistant, command)
                    armed_until = 0.0
                else:
                    self._safe_speak("Yes?")
                    armed_until = now + 10.0
                continue
            if armed_until and now <= armed_until:
                self._answer(assistant, heard)
                armed_until = 0.0
            elif armed_until and now > armed_until:
                armed_until = 0.0

    def _answer(self, assistant: SpiderAssistant, command: str) -> None:
        clean = command.strip()[:4000]
        if not clean:
            return
        self._write_state({"status": "thinking", "microphone_active": True, "last_command_at": utc_now()})
        try:
            result = assistant.respond(clean, conversation_id=self.conversation_id)
            if result.get("conversation_id"):
                self.conversation_id = str(result["conversation_id"])
            message = str(result.get("message", "I couldn't form a response."))
            self._write_state({"status": "responding", "microphone_active": True, "last_response_at": utc_now()})
            self._safe_speak(message)
        except Exception as error:
            self._write_state({"status": "degraded", "microphone_active": True, "reason": str(error)[:240]})
            self._safe_speak("I can't reach the local intelligence service right now.")
        finally:
            self._write_state({"status": "listening", "microphone_active": True})

    def _assistant(self) -> SpiderAssistant:
        database = Database(self.data_dir)
        database.initialize()
        broker = ActionBroker(database)
        return SpiderAssistant(database, broker, OllamaClient())

    @staticmethod
    def _command_after_wake(heard: str) -> str | None:
        normalized = re.sub(r"[^a-z0-9 ]+", " ", heard.lower())
        normalized = " ".join(normalized.split())
        wake_forms = ("hey webbie", "webbie", "hey web", "web")
        for wake in wake_forms:
            if normalized == wake:
                return ""
            prefix = wake + " "
            if normalized.startswith(prefix):
                return normalized[len(prefix):].strip()
        return None

    def read_state(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {"status": "not-started"}
        except (OSError, json.JSONDecodeError):
            return {"status": "not-started", "microphone_active": False}

    def _write_state(self, values: dict[str, Any]) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        current = self.read_state()
        payload = {**current, **values, "name": self.name, "updated_at": utc_now()}
        tmp = self.state_path.with_suffix(".tmp")
        old_umask = os.umask(0o077)
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.state_path)
            self.state_path.chmod(0o600)
        finally:
            os.umask(old_umask)

    def _safe_speak(self, text: str) -> None:
        try:
            self.speak(text)
        except Exception:
            pass

    @staticmethod
    def _first_command(*commands: str) -> str | None:
        for command in commands:
            if shutil.which(command):
                return command
        return None
