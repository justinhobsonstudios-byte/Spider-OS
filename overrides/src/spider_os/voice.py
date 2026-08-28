from __future__ import annotations

import importlib.util
import shutil
from typing import Any

from .constants import DEFAULT_WAKE_PHRASES


class VoiceRuntime:
    """Discover Webbie's local wake/STT/TTS capabilities and privacy policy."""

    name = "Webbie Voice Runtime"

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "wake_phrases": list(DEFAULT_WAKE_PHRASES),
            "audio_capture": self._first_command("pw-record", "arecord"),
            "wake_engine": self._wake_engine(),
            "speech_to_text": self._first_command(
                "whisper-cli",
                "whisper-cpp",
                "whisper",
                "vosk-transcriber",
            ),
            "text_to_speech": self._first_command("piper", "spd-say"),
            "voice_profile": {
                "presentation": "female",
                "accent": "Australian English",
                "provider": "local-preferred",
            },
            "policy": self.policy(),
        }

    @staticmethod
    def policy() -> dict[str, Any]:
        return {
            "wake_detection": "local-only",
            "ambient_audio_stored": False,
            "transcript_storage": "explicit-only",
            "microphone_pause_supported": True,
            "screen_and_microphone_indicators_required": True,
            "cloud_voice_requires_explicit_opt_in": True,
        }

    @staticmethod
    def _first_command(*commands: str) -> str | None:
        for command in commands:
            if shutil.which(command):
                return command
        return None

    def _wake_engine(self) -> str | None:
        if importlib.util.find_spec("openwakeword") is not None:
            return "openwakeword"
        return self._first_command("openwakeword", "precise-engine")
