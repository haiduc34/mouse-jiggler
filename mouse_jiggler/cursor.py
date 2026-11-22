"""Native, dependency-free mouse cursor control for desktop platforms."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import sys
from typing import Protocol


class CursorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class ScreenBounds:
    """Virtual screen rectangle; right and bottom edges are exclusive."""

    left: int
    top: int
    right: int
    bottom: int


class CursorController(Protocol):
    def get_position(self) -> Point: ...

    def get_bounds(self) -> ScreenBounds: ...

    def move_to(self, point: Point) -> None: ...


class WindowsCursorController:
    def __init__(self) -> None:
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        self._point_type = POINT
        self._user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        self._user32.GetCursorPos.restype = ctypes.c_int
        self._user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        self._user32.SetCursorPos.restype = ctypes.c_int
        self._user32.GetSystemMetrics.argtypes = [ctypes.c_int]
        self._user32.GetSystemMetrics.restype = ctypes.c_int

    def get_position(self) -> Point:
        point = self._point_type()
        if not self._user32.GetCursorPos(ctypes.byref(point)):
            raise ctypes.WinError(ctypes.get_last_error())
        return Point(point.x, point.y)

    def get_bounds(self) -> ScreenBounds:
        # SM_XVIRTUALSCREEN, SM_YVIRTUALSCREEN,
        # SM_CXVIRTUALSCREEN, SM_CYVIRTUALSCREEN.
        left = self._user32.GetSystemMetrics(76)
        top = self._user32.GetSystemMetrics(77)
        width = self._user32.GetSystemMetrics(78)
        height = self._user32.GetSystemMetrics(79)
        if width <= 0 or height <= 0:
            raise CursorError("Не удалось определить границы экрана Windows.")
        return ScreenBounds(left, top, left + width, top + height)

    def move_to(self, point: Point) -> None:
        if not self._user32.SetCursorPos(point.x, point.y):
            raise ctypes.WinError(ctypes.get_last_error())


class MacOSCursorController:
    def __init__(self) -> None:
        self._cg = ctypes.CDLL(
            "/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics"
        )
        self._cf = ctypes.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )

        class CGPoint(ctypes.Structure):
            _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]

        class CGSize(ctypes.Structure):
            _fields_ = [
                ("width", ctypes.c_double),
                ("height", ctypes.c_double),
            ]

        class CGRect(ctypes.Structure):
            _fields_ = [("origin", CGPoint), ("size", CGSize)]

        self._cg_point = CGPoint
        self._cg_rect = CGRect
        self._cg.CGEventCreate.argtypes = [ctypes.c_void_p]
        self._cg.CGEventCreate.restype = ctypes.c_void_p
        self._cg.CGEventGetLocation.argtypes = [ctypes.c_void_p]
        self._cg.CGEventGetLocation.restype = CGPoint
        self._cg.CGWarpMouseCursorPosition.argtypes = [CGPoint]
        self._cg.CGWarpMouseCursorPosition.restype = ctypes.c_int32
        self._cg.CGGetActiveDisplayList.argtypes = [
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint32),
            ctypes.POINTER(ctypes.c_uint32),
        ]
        self._cg.CGGetActiveDisplayList.restype = ctypes.c_int32
        self._cg.CGDisplayBounds.argtypes = [ctypes.c_uint32]
        self._cg.CGDisplayBounds.restype = CGRect
        self._cf.CFRelease.argtypes = [ctypes.c_void_p]
        self._cf.CFRelease.restype = None

    def get_position(self) -> Point:
        event = self._cg.CGEventCreate(None)
        if not event:
            raise CursorError("Не удалось получить позицию курсора macOS.")
        try:
            point = self._cg.CGEventGetLocation(event)
            return Point(round(point.x), round(point.y))
        finally:
            self._cf.CFRelease(event)

    def get_bounds(self) -> ScreenBounds:
        count = ctypes.c_uint32()
        result = self._cg.CGGetActiveDisplayList(0, None, ctypes.byref(count))
        if result != 0 or count.value == 0:
            raise CursorError("Не удалось получить список дисплеев macOS.")

        displays = (ctypes.c_uint32 * count.value)()
        result = self._cg.CGGetActiveDisplayList(
            count, displays, ctypes.byref(count)
        )
        if result != 0:
            raise CursorError("Не удалось получить список дисплеев macOS.")

        rectangles = [self._cg.CGDisplayBounds(display) for display in displays]
        left = min(rect.origin.x for rect in rectangles)
        top = min(rect.origin.y for rect in rectangles)
        right = max(rect.origin.x + rect.size.width for rect in rectangles)
        bottom = max(rect.origin.y + rect.size.height for rect in rectangles)
        return ScreenBounds(
            round(left), round(top), round(right), round(bottom)
        )

    def move_to(self, point: Point) -> None:
        result = self._cg.CGWarpMouseCursorPosition(
            self._cg_point(point.x, point.y)
        )
        if result != 0:
            raise CursorError(f"macOS отклонила перемещение курсора: {result}.")


class LinuxX11CursorController:
    def __init__(self) -> None:
        try:
            self._x11 = ctypes.CDLL("libX11.so.6")
        except OSError as error:
            raise CursorError("Для Linux требуется библиотека libX11.") from error

        self._display = self._x11.XOpenDisplay
        self._x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self._x11.XOpenDisplay.restype = ctypes.c_void_p
        self._x11.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        self._x11.XDefaultRootWindow.restype = ctypes.c_ulong
        self._x11.XQueryPointer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint),
        ]
        self._x11.XQueryPointer.restype = ctypes.c_int
        self._x11.XGetGeometry.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
            ctypes.POINTER(ctypes.c_uint),
        ]
        self._x11.XGetGeometry.restype = ctypes.c_int
        self._x11.XWarpPointer.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_int,
            ctypes.c_int,
        ]
        self._x11.XWarpPointer.restype = ctypes.c_int
        self._x11.XFlush.argtypes = [ctypes.c_void_p]
        self._x11.XFlush.restype = ctypes.c_int
        self._x11.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self._x11.XCloseDisplay.restype = ctypes.c_int

        self._display = self._x11.XOpenDisplay(None)
        if not self._display:
            raise CursorError(
                "Не удалось подключиться к X11. В Wayland глобальное "
                "перемещение курсора не поддерживается."
            )
        self._root = self._x11.XDefaultRootWindow(self._display)

    def get_position(self) -> Point:
        root = ctypes.c_ulong()
        child = ctypes.c_ulong()
        root_x = ctypes.c_int()
        root_y = ctypes.c_int()
        child_x = ctypes.c_int()
        child_y = ctypes.c_int()
        mask = ctypes.c_uint()
        success = self._x11.XQueryPointer(
            self._display,
            self._root,
            ctypes.byref(root),
            ctypes.byref(child),
            ctypes.byref(root_x),
            ctypes.byref(root_y),
            ctypes.byref(child_x),
            ctypes.byref(child_y),
            ctypes.byref(mask),
        )
        if not success:
            raise CursorError("Не удалось получить позицию курсора X11.")
        return Point(root_x.value, root_y.value)

    def get_bounds(self) -> ScreenBounds:
        root = ctypes.c_ulong()
        x = ctypes.c_int()
        y = ctypes.c_int()
        width = ctypes.c_uint()
        height = ctypes.c_uint()
        border = ctypes.c_uint()
        depth = ctypes.c_uint()
        success = self._x11.XGetGeometry(
            self._display,
            self._root,
            ctypes.byref(root),
            ctypes.byref(x),
            ctypes.byref(y),
            ctypes.byref(width),
            ctypes.byref(height),
            ctypes.byref(border),
            ctypes.byref(depth),
        )
        if not success:
            raise CursorError("Не удалось определить границы экрана X11.")
        return ScreenBounds(0, 0, width.value, height.value)

    def move_to(self, point: Point) -> None:
        self._x11.XWarpPointer(
            self._display, 0, self._root, 0, 0, 0, 0, point.x, point.y
        )
        self._x11.XFlush(self._display)

    def close(self) -> None:
        if self._display:
            self._x11.XCloseDisplay(self._display)
            self._display = None


def create_cursor_controller() -> CursorController:
    if sys.platform == "win32":
        return WindowsCursorController()
    if sys.platform == "darwin":
        return MacOSCursorController()
    if sys.platform.startswith("linux"):
        return LinuxX11CursorController()
    raise CursorError(f"Операционная система {sys.platform} не поддерживается.")
