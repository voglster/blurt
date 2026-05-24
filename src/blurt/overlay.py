from __future__ import annotations

import logging
import threading
import tkinter as tk
from dataclasses import dataclass

log = logging.getLogger(__name__)


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

    # --- lifecycle ---

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=2.0)

    def stop(self) -> None:
        root = self._root
        if root is not None:
            try:
                root.after(0, root.destroy)
            except tk.TclError:
                pass
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    # --- public (thread-safe) ---

    def show(self) -> None:
        if self._root is None:
            return
        self._root.after(0, self._show_impl)

    def hide(self) -> None:
        if self._root is None:
            return
        self._root.after(0, self._hide_impl)

    def set_text(self, text: str) -> None:
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
            # destroy() may already have been called via stop(); guard against
            # double-destroy.
            try:
                self._root.destroy()
            except tk.TclError:
                pass
            self._root = None

    def _show_impl(self) -> None:
        assert self._root is not None and self._text_widget is not None
        screen_w = self._root.winfo_screenwidth()
        screen_h = self._root.winfo_screenheight()
        w = int(screen_w * self._cfg.width_fraction)
        h = self._cfg.min_height_px
        x = (screen_w - w) // 2
        y = screen_h - h - 80  # 80px above bottom edge
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
        screen_h = self._root.winfo_screenheight()
        max_h = int(screen_h * self._cfg.max_height_fraction)
        # Force layout so we can ask for required height.
        self._text_widget.update_idletasks()
        # Count display lines; multiply by line height for a height estimate.
        line_count = int(self._text_widget.count("1.0", "end", "displaylines") or 1)
        font_metrics = self._text_widget.tk.call("font", "metrics", self._cfg.font, "-linespace")
        line_h = int(font_metrics)
        desired = line_count * line_h + 24  # padding
        new_h = min(max(desired, self._cfg.min_height_px), max_h)
        geom = self._root.geometry()  # "WxH+X+Y"
        size, _, rest = geom.partition("+")
        w_str, _, _ = size.partition("x")
        x_str, _, y_str = rest.partition("+")
        try:
            screen_w = self._root.winfo_screenwidth()
            w = int(w_str)
            new_y = screen_h - new_h - 80
            new_x = (screen_w - w) // 2
            self._root.geometry(f"{w}x{new_h}+{new_x}+{new_y}")
        except ValueError:
            pass
