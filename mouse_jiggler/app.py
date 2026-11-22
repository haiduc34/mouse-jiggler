"""Tkinter user interface for the mouse jiggler."""

from __future__ import annotations

import queue
import re
import tkinter as tk
from tkinter import messagebox
from collections.abc import Callable

from .cursor import CursorController, create_cursor_controller
from .engine import JiggleEngine
from .model import JigglerSettings, SettingsStore, normalize_int32


BACKGROUND = "#d4d0c8"
GREEN = "#2e8b57"
RED = "#c43c35"
NUMBER_PATTERN = re.compile(r"[+-]?(?:[0-9]*(?:[.,][0-9]*)?)?")


class MouseJigglerApp:
    def __init__(
        self,
        root: tk.Tk,
        cursor_factory: Callable[[], CursorController] = create_cursor_controller,
    ) -> None:
        self.root = root
        self.settings = SettingsStore()
        self._cursor_factory = cursor_factory
        self._cursor: CursorController | None = None
        self._engine: JiggleEngine | None = None
        self._errors: queue.Queue[Exception] = queue.Queue()
        self._pending_commits: dict[str, str] = {}
        self._setting_variable = False
        self._closing = False
        self._poll_after_id: str | None = None

        root.title("Mouse Jiggler")
        root.geometry("450x140")
        root.resizable(False, False)
        root.overrideredirect(True)
        root.configure(bg=BACKGROUND, padx=6, pady=6)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._drag_offset: tuple[int, int] | None = None

        self.title_bar = tk.Frame(root, bg="#bdb9b2", height=24, cursor="fleur")
        self.title_bar.grid(
            row=0, column=0, columnspan=3, sticky="ew", pady=(0, 4)
        )
        self.title_bar.grid_propagate(False)
        self.title_label = tk.Label(
            self.title_bar,
            text="Mouse Jiggler",
            bg="#bdb9b2",
            font=("TkDefaultFont", 9, "bold"),
            cursor="fleur",
        )
        self.title_label.pack(
            fill="x", expand=True, padx=4, pady=2, anchor="center"
        )
        for widget in (self.title_bar, self.title_label):
            widget.bind("<ButtonPress-1>", self._start_window_drag)
            widget.bind("<B1-Motion>", self._drag_window)
            widget.bind("<ButtonRelease-1>", self._stop_window_drag)

        self.variables = {
            "move_interval_ms": tk.StringVar(value="1000"),
            "return_interval_ms": tk.StringVar(value="1000"),
            "distance": tk.StringVar(value="10"),
        }
        self.entries: dict[str, tk.Entry] = {}

        validate_number = root.register(
            lambda proposed: len(proposed) <= 4
            and NUMBER_PATTERN.fullmatch(proposed) is not None
        )
        fields = (
            ("move_interval_ms", "Интервал перемещения, мс"),
            ("return_interval_ms", "Интервал возврата, мс"),
            ("distance", "Смещение курсора, пиксели"),
        )
        for row, (name, label) in enumerate(fields, start=1):
            tk.Label(
                root,
                text=label,
                bg=BACKGROUND,
                anchor="w",
                font=("TkDefaultFont", 9),
            ).grid(row=row, column=0, sticky="ew", padx=(0, 6), pady=3)
            entry = tk.Entry(
                root,
                textvariable=self.variables[name],
                width=5,
                font=("TkDefaultFont", 9),
                validate="key",
                validatecommand=(validate_number, "%P"),
            )
            entry.grid(row=row, column=1, sticky="w", pady=3)
            entry.bind(
                "<FocusOut>",
                lambda _event, field=name: self._commit(field),
            )
            self.variables[name].trace_add(
                "write", lambda *_args, field=name: self._schedule_commit(field)
            )
            self.entries[name] = entry

        root.columnconfigure(0, weight=1)

        self.movement_button = tk.Button(
            root,
            width=28,
            font=("TkDefaultFont", 9, "bold"),
            fg="white",
            activeforeground="white",
            command=self.toggle_movement,
        )
        self.movement_button.grid(
            row=1, column=2, sticky="ew", padx=(6, 0), pady=3
        )

        self.return_button = tk.Button(
            root,
            width=28,
            font=("TkDefaultFont", 9),
            fg="white",
            activeforeground="white",
            command=self.toggle_return,
        )
        self.return_button.grid(
            row=2, column=2, sticky="ew", padx=(6, 0), pady=3
        )

        self.window_controls = tk.Frame(root, bg=BACKGROUND)
        self.window_controls.grid(
            row=3, column=2, sticky="ew", padx=(6, 0), pady=3
        )
        self.window_controls.columnconfigure(0, weight=1)
        self.window_controls.columnconfigure(1, weight=1)

        self.minimize_button = tk.Button(
            self.window_controls,
            text="Свернуть",
            width=12,
            command=self.minimize,
            font=("TkDefaultFont", 9),
        )
        self.minimize_button.grid(
            row=0, column=0, sticky="ew", padx=(0, 2)
        )

        self.close_button = tk.Button(
            self.window_controls,
            text="Закрыть",
            width=12,
            command=self.close,
            font=("TkDefaultFont", 9),
        )
        self.close_button.grid(
            row=0, column=1, sticky="ew", padx=(2, 0)
        )

        self._map_binding: str | None = None
        self._update_movement_button(False)
        self._update_return_button()
        self._poll_after_id = root.after(100, self._poll_errors)

    def minimize(self) -> None:
        # A native frame is temporarily restored so the minimized window
        # remains accessible in the taskbar on all supported desktops.
        self.root.overrideredirect(False)
        self.root.iconify()
        if self._map_binding is None:
            self._map_binding = self.root.bind(
                "<Map>", self._restore_borderless, add="+"
            )

    def _restore_borderless(self, _event: tk.Event) -> None:
        if self.root.state() == "iconic":
            return
        self.root.overrideredirect(True)
        if self._map_binding:
            self.root.unbind("<Map>", self._map_binding)
            self._map_binding = None

    def _start_window_drag(self, event: tk.Event) -> None:
        self._drag_offset = (
            event.x_root - self.root.winfo_x(),
            event.y_root - self.root.winfo_y(),
        )

    def _drag_window(self, event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.root.geometry(f"+{x}+{y}")

    def _stop_window_drag(self, _event: tk.Event) -> None:
        self._drag_offset = None

    def _schedule_commit(self, name: str) -> None:
        if self._setting_variable or self._closing:
            return
        pending = self._pending_commits.get(name)
        if pending:
            self.root.after_cancel(pending)
        self._pending_commits[name] = self.root.after(
            1000, lambda: self._commit(name)
        )

    def _commit(self, name: str) -> None:
        pending = self._pending_commits.pop(name, None)
        if pending:
            try:
                self.root.after_cancel(pending)
            except tk.TclError:
                pass
        current: JigglerSettings = self.settings.snapshot()
        previous = getattr(current, name)
        value = normalize_int32(self.variables[name].get(), previous)
        self._setting_variable = True
        try:
            self.variables[name].set(str(value))
        finally:
            self._setting_variable = False
        self.settings.update(**{name: value})
        if self._engine:
            self._engine.wake()

    def _button_colors(self, enabled: bool) -> dict[str, str]:
        color = GREEN if enabled else RED
        return {"bg": color, "activebackground": color}

    def _update_movement_button(self, running: bool) -> None:
        text = (
            "Mouse Jiggler действует"
            if running
            else "Mouse Jiggler не действует"
        )
        self.movement_button.configure(
            text=text, **self._button_colors(running)
        )

    def _update_return_button(self) -> None:
        enabled = self.settings.snapshot().return_cursor
        self.return_button.configure(
            text="Возвращать курсор" if enabled else "Не возвращать курсор",
            **self._button_colors(enabled),
        )
        self.entries["return_interval_ms"].configure(
            state="normal" if enabled else "disabled"
        )

    def toggle_return(self) -> None:
        enabled = not self.settings.snapshot().return_cursor
        self.settings.update(return_cursor=enabled)
        self._update_return_button()
        if self._engine:
            self._engine.wake()

    def toggle_movement(self) -> None:
        if self._engine and self._engine.is_running:
            self._engine.stop()
            self._update_movement_button(False)
            return

        try:
            if self._cursor is None:
                self._cursor = self._cursor_factory()
            if self._engine is None:
                self._engine = JiggleEngine(
                    self.settings, self._cursor, self._on_engine_error
                )
            self._engine.start()
            self._update_movement_button(True)
        except Exception as error:
            self._update_movement_button(False)
            messagebox.showerror("Ошибка запуска", str(error), parent=self.root)

    def _on_engine_error(self, error: Exception) -> None:
        self._errors.put(error)

    def _poll_errors(self) -> None:
        if self._closing:
            return
        try:
            error = self._errors.get_nowait()
        except queue.Empty:
            pass
        else:
            self._update_movement_button(False)
            messagebox.showerror(
                "Ошибка перемещения курсора", str(error), parent=self.root
            )
        self._poll_after_id = self.root.after(100, self._poll_errors)

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        if self._poll_after_id:
            self.root.after_cancel(self._poll_after_id)
        for pending in self._pending_commits.values():
            self.root.after_cancel(pending)
        self._pending_commits.clear()
        if self._engine:
            self._engine.stop()
        close_cursor = getattr(self._cursor, "close", None)
        if close_cursor:
            close_cursor()
        self.root.destroy()


def main() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as error:
        raise SystemExit(f"Не удалось открыть графический интерфейс: {error}") from error
    MouseJigglerApp(root)
    root.mainloop()
