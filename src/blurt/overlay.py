from __future__ import annotations

import gc
import logging
import math
import re
import subprocess
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    import tkinter as tk

log = logging.getLogger(__name__)


class MonitorInfo(NamedTuple):
    name: str
    primary: bool
    x: int
    y: int
    w: int
    h: int


# The X11 last-resort bitmap. Tk only lands here when it could not resolve the
# requested family at all — generic aliases like "monospace" need fontconfig,
# which a Tk built without Xft does not have.
_LAST_RESORT_FAMILY = "fixed"


def unresolved_font_warning(requested: str, resolved_family: str) -> str | None:
    if resolved_family.strip().casefold() != _LAST_RESORT_FAMILY:
        return None
    return (
        f"overlay font {requested!r} did not resolve — Tk fell back to the "
        f"{_LAST_RESORT_FAMILY!r} bitmap font, so the overlay will look blocky and "
        "un-anti-aliased. This Python's Tk was built without Xft. Reinstall against "
        "the system interpreter, which has an Xft-enabled Tk: "
        "`sudo apt install python3-tk` then "
        "`uv tool install --force --python /usr/bin/python3 --editable .`"
    )


_MONITOR_LINE = re.compile(
    r"^\s*\d+:\s+\+(?P<primary>\*?)(?P<name>\S+)\s+"
    r"(?P<w>\d+)/\d+x(?P<h>\d+)/\d+\+(?P<x>-?\d+)\+(?P<y>-?\d+)"
)


def _parse_listmonitors(output: str) -> list[MonitorInfo]:
    """Parse `xrandr --listmonitors`. Lines look like:

        0: +*DP-4 2560/700x1440/390+2560+0  DP-4

    The leading `+` marks an active monitor and `*` marks the primary one.
    """
    monitors: list[MonitorInfo] = []
    for line in output.splitlines():
        m = _MONITOR_LINE.match(line)
        if m:
            monitors.append(MonitorInfo(
                name=m.group("name"),
                primary=bool(m.group("primary")),
                x=int(m.group("x")),
                y=int(m.group("y")),
                w=int(m.group("w")),
                h=int(m.group("h")),
            ))
    return monitors


def _list_monitors_detailed() -> list[MonitorInfo]:
    try:
        out = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True, text=True, check=True, timeout=1.0,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        log.warning("xrandr --listmonitors failed: %s", exc)
        return []
    return _parse_listmonitors(out)


def _list_monitors() -> list[tuple[int, int, int, int]]:
    """Return [(x, y, w, h), ...] for every monitor."""
    return [(m.x, m.y, m.w, m.h) for m in _list_monitors_detailed()]


def _window_rect(window_id: int) -> tuple[int, int, int, int] | None:
    """Return (x, y, w, h) for a window via xdotool, or None on failure."""
    try:
        out = subprocess.run(
            ["xdotool", "getwindowgeometry", "--shell", str(window_id)],
            capture_output=True, text=True, check=True, timeout=1.0,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        log.warning("xdotool getwindowgeometry failed: %s", exc)
        return None
    fields: dict[str, int] = {}
    for line in out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            try:
                fields[k.strip()] = int(v.strip())
            except ValueError:
                pass
    try:
        return fields["X"], fields["Y"], fields["WIDTH"], fields["HEIGHT"]
    except KeyError:
        return None


def _pointer_xy() -> tuple[int, int] | None:
    """Return the pointer's (x, y) in the X/XWayland screen space, or None.

    This is the best monitor hint on Wayland, where there's no focused-window
    geometry to query — the overlay should appear on whatever screen the user
    is actively working on, which is almost always where their cursor is.
    """
    try:
        out = subprocess.run(
            ["xdotool", "getmouselocation", "--shell"],
            capture_output=True, text=True, check=True, timeout=1.0,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        log.warning("xdotool getmouselocation failed: %s", exc)
        return None
    fields: dict[str, int] = {}
    for line in out.splitlines():
        k, _, v = line.partition("=")
        if k in ("X", "Y"):
            try:
                fields[k] = int(v.strip())
            except ValueError:
                pass
    if "X" in fields and "Y" in fields:
        return fields["X"], fields["Y"]
    return None


def _monitor_containing(
    monitors: list[tuple[int, int, int, int]], x: int, y: int
) -> tuple[int, int, int, int] | None:
    for mx, my, mw, mh in monitors:
        if mx <= x < mx + mw and my <= y < my + mh:
            return (mx, my, mw, mh)
    return None


def _resolve_monitor(
    window_id: int | None, preference: str = "primary"
) -> tuple[int, int, int, int] | None:
    """Pick the monitor to show the overlay on.

    `preference` is an output name, "primary", or "pointer". Pointer resolution is
    only trustworthy on X11: under XWayland, XQueryPointer reports the pointer only
    while it sits over an X11 surface, so on a mostly-Wayland desktop it returns a
    stale position and the overlay lands on an arbitrary monitor.
    """
    detailed = _list_monitors_detailed()
    if not detailed:
        return None

    if preference == "pointer":
        return _resolve_monitor_by_signal(window_id, [m[2:] for m in detailed])

    if preference != "primary":
        for m in detailed:
            if m.name == preference:
                return m[2:]
        log.warning("overlay.monitor=%r matches no output; using primary", preference)

    for m in detailed:
        if m.primary:
            return m[2:]
    return detailed[0][2:]


def _resolve_monitor_by_signal(
    window_id: int | None, monitors: list[tuple[int, int, int, int]]
) -> tuple[int, int, int, int] | None:
    if window_id is not None:
        rect = _window_rect(window_id)
        if rect is not None:
            cx = rect[0] + rect[2] // 2
            cy = rect[1] + rect[3] // 2
            found = _monitor_containing(monitors, cx, cy)
            if found is not None:
                return found
    pos = _pointer_xy()
    if pos is not None:
        found = _monitor_containing(monitors, *pos)
        if found is not None:
            return found
    return monitors[0]


@dataclass
class OverlayConfig:
    enabled: bool = True
    position: str = "center"
    width_fraction: float = 0.75
    min_height_px: int = 200
    max_height_fraction: float = 0.33
    opacity: float = 0.85
    font: str = "monospace 22"
    monitor: str = "primary"
    corner_radius: int = 14


_EDGE_MARGIN_PX = 80
_DEFAULT_POSITION = "center"
_POSITIONS = ("center", "top-center", "bottom-center")


def _rounded_rect_scanlines(w: int, h: int, radius: int) -> list[tuple[int, int, int, int]]:
    """Approximate a rounded rectangle as (x, y, width, height) rects.

    X11's SHAPE extension takes a region, not a path, so the curve is built one
    scanline per row of each corner. The mask is 1-bit, so corners come out
    hard-edged — there is no anti-aliasing to be had here.
    """
    radius = min(radius, w // 2, h // 2)
    if radius <= 0:
        return [(0, 0, w, h)]

    rects = [(0, radius, w, h - 2 * radius)]
    for dy in range(radius):
        # Distance from the corner circle's centre to this scanline's midpoint.
        offset = radius - dy - 0.5
        inset = radius - int(math.sqrt(max(radius * radius - offset * offset, 0.0)))
        width = w - 2 * inset
        rects.append((inset, dy, width, 1))
        rects.append((inset, h - 1 - dy, width, 1))
    return rects


def _overlay_geometry(
    monitor: tuple[int, int, int, int], cfg: OverlayConfig, height: int
) -> tuple[int, int, int, int]:
    """Return (w, h, x, y) for the overlay on `monitor`.

    top-center and bottom-center sit one margin in from their respective edges,
    mirroring each other. The anchored edge decides how the box grows as the
    transcript lengthens: top-center grows downward with a fixed y, bottom-center
    grows upward, and center grows both ways at half the rate.
    """
    mx, my, mw, mh = monitor
    w = int(mw * cfg.width_fraction)
    x = mx + (mw - w) // 2

    position = cfg.position
    if position not in _POSITIONS:
        log.warning(
            "overlay.position=%r is not one of %s; using %s",
            position, ", ".join(_POSITIONS), _DEFAULT_POSITION,
        )
        position = _DEFAULT_POSITION

    if position == "top-center":
        return w, height, x, my + _EDGE_MARGIN_PX
    if position == "bottom-center":
        return w, height, x, my + mh - height - _EDGE_MARGIN_PX
    return w, height, x, my + (mh - height) // 2


class Overlay:
    """Frameless always-on-top text overlay backed by Tk.

    Public API is thread-safe. Internally, all Tk calls are marshalled onto
    the Tk mainloop thread via `root.after(0, ...)`.
    """

    def __init__(self, cfg: OverlayConfig) -> None:
        self._cfg = cfg
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._root: tk.Tk | None = None
        self._text_widget: tk.Text | None = None
        self._pending_text: str | None = None
        self._visible: bool = False
        self._monitor: tuple[int, int, int, int] | None = None
        self._xdisplay = None
        self._shaping_unavailable = False

    # --- lifecycle ---

    def start(self) -> None:
        if not self._cfg.enabled:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def stop(self) -> None:
        if not self._cfg.enabled:
            return
        import tkinter as tk

        root = self._root
        if root is not None:
            # Ask the Tk thread to exit its mainloop; the actual destroy +
            # interpreter teardown happens on that thread in _run's finally,
            # which is the only thread allowed to delete the Tcl interpreter.
            try:
                root.after(0, root.quit)
            except tk.TclError:
                pass
        # Drop this thread's reference BEFORE joining. If we held it across the
        # join, the worker thread's gc.collect() couldn't free the interpreter
        # (live ref here), and it would instead be finalized on this thread at
        # shutdown — the exact cross-thread teardown we're avoiding.
        del root
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    # --- public (thread-safe) ---

    def show(self, target_window: int | None = None) -> None:
        if not self._cfg.enabled:
            return
        if self._root is None:
            return
        # Resolve target monitor BEFORE marshalling to the Tk thread (xrandr +
        # xdotool calls block; cheaper to do off the UI thread).
        self._monitor = _resolve_monitor(target_window, preference=self._cfg.monitor)
        self._root.after(0, self._show_impl)

    def hide(self) -> None:
        if not self._cfg.enabled:
            return
        if self._root is None:
            return
        self._root.after(0, self._hide_impl)

    def set_text(self, text: str) -> None:
        if not self._cfg.enabled:
            return
        if self._root is None:
            self._pending_text = text
            return
        self._root.after(0, lambda: self._set_text_impl(text))

    # --- Tk-thread internals ---

    def _apply_corner_shape(self, w: int, h: int) -> None:
        """Clip the window to a rounded rectangle via the X11 SHAPE extension.

        Tk cannot round a window itself. The shape is in window coordinates, so it
        has to be reapplied after every geometry change. Purely decorative: any
        failure here degrades to square corners rather than costing a dictation.
        """
        if self._cfg.corner_radius <= 0 or self._shaping_unavailable:
            return
        try:
            from Xlib import display as xdisplay
            from Xlib.ext import shape

            if self._xdisplay is None:
                self._xdisplay = xdisplay.Display()
            window = self._xdisplay.create_resource_object(
                "window", self._root.winfo_id()
            )
            window.shape_rectangles(
                shape.SO.Set, shape.SK.Bounding, 0, 0, 0,
                [
                    {"x": x, "y": y, "width": rw, "height": rh}
                    for x, y, rw, rh in _rounded_rect_scanlines(
                        w, h, self._cfg.corner_radius
                    )
                ],
            )
            self._xdisplay.sync()
        except Exception as exc:
            self._shaping_unavailable = True
            log.warning("rounded corners unavailable (%s); using square corners", exc)

    def _warn_if_font_unresolved(self) -> None:
        import tkinter as tk

        try:
            resolved = self._root.tk.call("font", "actual", self._cfg.font, "-family")
        except tk.TclError:
            return
        warning = unresolved_font_warning(self._cfg.font, str(resolved))
        if warning:
            log.warning("%s", warning)

    def _run(self) -> None:
        # Imported per-method rather than at module scope: Tk ships as a separate
        # OS package (python3-tk on Debian), and needing it to merely *import*
        # blurt broke headless installs and CI. Only using an overlay needs it.
        import tkinter as tk

        self._root = tk.Tk()
        self._root.withdraw()
        self._root.overrideredirect(True)
        self._root.attributes("-topmost", True)
        try:
            self._root.attributes("-alpha", self._cfg.opacity)
        except tk.TclError:
            pass
        self._root.configure(bg="#1a1a1a")

        self._text_widget = tk.Text(
            self._root,
            font=self._cfg.font,
            wrap="word",
            bg="#1a1a1a",
            fg="#f0f0f0",
            insertontime=0,
            highlightthickness=0,
            borderwidth=0,
            padx=12,
            pady=10,
        )
        self._text_widget.pack(fill="both", expand=True)
        self._text_widget.configure(state="disabled")
        self._warn_if_font_unresolved()

        self._ready.set()
        try:
            self._root.mainloop()
        except tk.TclError:
            pass
        finally:
            try:
                self._root.destroy()
            except tk.TclError:
                pass
            # Drop EVERY reference to a Tk object so the Tcl interpreter is
            # finalized here, on its creating thread. root and the Text widget
            # form a reference cycle, so plain refcounting won't free the
            # interpreter — without the explicit collect it survives until
            # process-shutdown GC on the main thread, which aborts with
            # "Tcl_AsyncDelete: async handler deleted by the wrong thread".
            if self._xdisplay is not None:
                try:
                    self._xdisplay.close()
                except Exception:
                    pass
                self._xdisplay = None
            self._text_widget = None
            self._root = None
            gc.collect()

    def _show_impl(self) -> None:
        assert self._root is not None and self._text_widget is not None
        mx, my, mw, mh = self._monitor or (
            0, 0,
            self._root.winfo_screenwidth(),
            self._root.winfo_screenheight(),
        )
        w, h, x, y = _overlay_geometry(
            (mx, my, mw, mh), self._cfg, self._cfg.min_height_px
        )
        self._root.geometry(f"{w}x{h}+{x}+{y}")
        self._root.update_idletasks()
        self._apply_corner_shape(w, h)
        self._root.deiconify()
        self._root.lift()
        self._visible = True
        if self._pending_text is not None:
            self._set_text_impl(self._pending_text)
            self._pending_text = None

    def _hide_impl(self) -> None:
        assert self._root is not None and self._text_widget is not None
        self._visible = False
        self._pending_text = None
        self._root.withdraw()
        self._text_widget.configure(state="normal")
        self._text_widget.delete("1.0", "end")
        self._text_widget.configure(state="disabled")

    def _set_text_impl(self, text: str) -> None:
        assert self._root is not None and self._text_widget is not None
        self._text_widget.configure(state="normal")
        self._text_widget.delete("1.0", "end")
        self._text_widget.insert("1.0", text)
        self._text_widget.configure(state="disabled")
        self._maybe_resize()
        self._text_widget.see("end")

    def _maybe_resize(self) -> None:
        """Auto-grow up to max_height_fraction; beyond that, let it scroll."""
        assert self._root is not None and self._text_widget is not None
        if not self._visible:
            return
        mx, my, mw, mh = self._monitor or (
            0, 0,
            self._root.winfo_screenwidth(),
            self._root.winfo_screenheight(),
        )
        max_h = int(mh * self._cfg.max_height_fraction)
        self._text_widget.update_idletasks()
        count_result = self._text_widget.count("1.0", "end", "displaylines")
        if isinstance(count_result, tuple):
            line_count = int(count_result[0]) if count_result else 1
        else:
            line_count = int(count_result or 1)
        font_metrics = self._text_widget.tk.call("font", "metrics", self._cfg.font, "-linespace")
        line_h = int(font_metrics)
        desired = line_count * line_h + 24  # padding
        new_h = min(max(desired, self._cfg.min_height_px), max_h)
        w, h, x, y = _overlay_geometry((mx, my, mw, mh), self._cfg, new_h)
        self._root.geometry(f"{w}x{h}+{x}+{y}")
        self._root.update_idletasks()
        self._apply_corner_shape(w, h)
