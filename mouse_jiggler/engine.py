"""Mouse jiggling algorithm, isolated from the graphical interface."""

from __future__ import annotations

from collections.abc import Callable
import random
import threading
import time
from typing import Any

from .cursor import CursorController, Point, ScreenBounds
from .model import SettingsStore


def choose_target(
    origin: Point,
    distance: int,
    bounds: ScreenBounds,
    choice: Callable[[list[str]], str] = random.choice,
) -> Point:
    """Choose a feasible cardinal move without clamping its distance."""

    candidates = {
        "left": Point(origin.x - distance, origin.y),
        "right": Point(origin.x + distance, origin.y),
        "up": Point(origin.x, origin.y - distance),
        "down": Point(origin.x, origin.y + distance),
    }
    feasible = [
        direction
        for direction, point in candidates.items()
        if bounds.left <= point.x < bounds.right
        and bounds.top <= point.y < bounds.bottom
    ]
    if not feasible:
        return origin
    return candidates[choice(feasible)]


class JiggleEngine:
    def __init__(
        self,
        settings: SettingsStore,
        cursor: CursorController,
        on_error: Callable[[Exception], Any] | None = None,
    ) -> None:
        self._settings = settings
        self._cursor = cursor
        self._on_error = on_error
        self._random = random.Random()
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._wake_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="mouse-jiggler",
            daemon=True,
        )
        self._thread.start()

    def wake(self) -> None:
        """Apply changed settings without waiting for the old timeout."""

        self._wake_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        thread = self._thread
        if (
            thread
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=3)
        if self._thread and not self._thread.is_alive():
            self._thread = None

    def _wait_for(self, milliseconds: int) -> bool:
        """Wait for a full interval; return False when settings changed."""

        deadline = time.monotonic() + milliseconds / 1000
        while not self._stop_event.is_set():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return True
            if self._wake_event.wait(remaining):
                self._wake_event.clear()
                return False
        return False

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                settings = self._settings.snapshot()
                if not self._wait_for(settings.move_interval_ms):
                    continue

                settings = self._settings.snapshot()
                origin = self._cursor.get_position()
                target = choose_target(
                    origin,
                    settings.distance,
                    self._cursor.get_bounds(),
                    self._random.choice,
                )
                if target == origin:
                    continue

                self._cursor.move_to(target)

                while not self._stop_event.is_set():
                    settings = self._settings.snapshot()
                    if not settings.return_cursor:
                        break
                    if not self._wait_for(settings.return_interval_ms):
                        continue

                    # A user-initiated move cancels this particular return.
                    if (
                        self._settings.snapshot().return_cursor
                        and self._cursor.get_position() == target
                    ):
                        self._cursor.move_to(origin)
                    break
        except Exception as error:
            if not self._stop_event.is_set() and self._on_error:
                self._on_error(error)
