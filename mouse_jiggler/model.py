"""Application settings and input normalization."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import threading


INT32_MAX = 2**31 - 1


@dataclass(frozen=True, slots=True)
class JigglerSettings:
    move_interval_ms: int = 1000
    return_interval_ms: int = 1000
    distance: int = 10
    return_cursor: bool = True


class SettingsStore:
    """Thread-safe settings shared by the UI and the worker thread."""

    def __init__(self, initial: JigglerSettings | None = None) -> None:
        self._settings = initial or JigglerSettings()
        self._lock = threading.Lock()

    def snapshot(self) -> JigglerSettings:
        with self._lock:
            return self._settings

    def update(self, **changes: int | bool) -> JigglerSettings:
        with self._lock:
            self._settings = JigglerSettings(
                move_interval_ms=changes.get(
                    "move_interval_ms", self._settings.move_interval_ms
                ),
                return_interval_ms=changes.get(
                    "return_interval_ms", self._settings.return_interval_ms
                ),
                distance=changes.get("distance", self._settings.distance),
                return_cursor=changes.get(
                    "return_cursor", self._settings.return_cursor
                ),
            )
            return self._settings


def normalize_int32(raw_value: str, fallback: int) -> int:
    """Normalize a number to 1..INT32_MAX, truncating its fractional part."""

    fallback = min(INT32_MAX, max(1, int(fallback)))
    text = raw_value.strip().replace(",", ".")
    if not text:
        return fallback

    try:
        value = Decimal(text)
    except InvalidOperation:
        return fallback

    if not value.is_finite():
        return fallback
    if value < 0:
        value = -value

    return min(INT32_MAX, max(1, int(value)))
