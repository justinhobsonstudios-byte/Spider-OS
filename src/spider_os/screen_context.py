from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

SENSITIVE_MARKERS = (
    "password",
    "passcode",
    "one-time code",
    "2fa",
    "authentication",
    "private browsing",
    "incognito",
    "secret key",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ScreenContextBuffer:
    """Holds only the latest derived screen context in memory.

    No screenshots or pixel frames are written to disk. The buffer vanishes when
    Spider Core restarts.
    """

    enabled: bool = True
    _current: dict[str, Any] = field(default_factory=dict)

    def update(
        self,
        *,
        app_name: str,
        window_title: str = "",
        text_summary: str = "",
        anchor_id: str | None = None,
        sensitive: bool = False,
    ) -> dict[str, Any]:
        joined = f"{app_name} {window_title} {text_summary}".casefold()
        excluded = sensitive or any(marker in joined for marker in SENSITIVE_MARKERS)
        self._current = {
            "enabled": self.enabled,
            "active": self.enabled and not excluded,
            "excluded": excluded,
            "app_name": app_name[:160] if not excluded else "excluded",
            "window_title": window_title[:240] if not excluded else "",
            "text_summary": text_summary[:2000] if not excluded else "",
            "anchor_id": anchor_id if not excluded else None,
            "raw_pixels_retained": False,
            "persisted": False,
            "updated_at": utc_now(),
        }
        return dict(self._current)

    def current(self) -> dict[str, Any]:
        if self._current:
            return dict(self._current)
        return {
            "enabled": self.enabled,
            "active": False,
            "excluded": False,
            "raw_pixels_retained": False,
            "persisted": False,
            "updated_at": None,
        }

    def clear(self) -> None:
        self._current.clear()
