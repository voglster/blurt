from __future__ import annotations

import gc
import logging
import re
import subprocess
import threading
import tkinter as tk
from dataclasses import dataclass

log = logging.getLogger(__name__)


def _list_monitors() -> list[tuple[int, int, int, int]]:
    """Return [(x, y, w, h), ...] for every monitor via xrandr --listmonitors."""
    try:
        out = subprocess.run(
            ["xrandr", "--listmonitors"],
            capture_output=True, text=True, check=True, timeout=1.0,
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError) as exc:
        log.warning("xrandr --listmonitors failed: %s", exc)
        return []
    monitors: list[tuple[int, int, int, int]] = []
    # Line shape: " 0: +*HDMI-1 1920/520x1080/290+0+0  HDMI-1"
    pat = re.compile(r"(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)")
    for line in out.splitlines():
        m = pat.search(line)
        if m:
            w, h, x, y = (int(v) for v in m.groups())
            monitors.append((x, y, w, h))
    return monitors


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


def _monitor_for_window(window_id: int | None) -> tuple[int, int, int, int] | None:
    """Return the monitor rect containing the window's center, or None."""
    monitors = _list_monitors()
    if not monitors:
        return None
    if window_id is None:
        return monitors[0]
    rect = _window_rect(window_id)
    if rect is None:
        return monitors[0]
    cx = rect[0] + rect[2] // 2
    cy = rect[1] + rect[3] // 2
    for mx, my, mw, mh in monitors:
        if mx <= cx < mx + mw and my <= cy < my + mh:
            return (mx, my, mw, mh)
    return monitors[0]


@dataclass
class OverlayConfig:
    enabled: bool = True
    position: str = "bottom-center"
    width_fraction: float = 0.6
    min_height_px: int = 120
    max_height_fraction: float = 0.33
    opacity: float = 0.85
    font: str = "monospace 18"


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
        self._monitor = _monitor_for_window(target_window)
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

    def _run(self) -> None:
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
        w = int(mw * self._cfg.width_fraction)
        h = self._cfg.min_height_px
        x = mx + (mw - w) // 2
        y = my + mh - h - 80  # 80px above the monitor's bottom edge
        self._root.geometry(f"{w}x{h}+{x}+{y}")
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
        w = int(mw * self._cfg.width_fraction)
        new_x = mx + (mw - w) // 2
        new_y = my + mh - new_h - 80
        self._root.geometry(f"{w}x{new_h}+{new_x}+{new_y}")
