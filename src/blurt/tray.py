from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from enum import Enum

from PIL import Image, ImageDraw

log = logging.getLogger(__name__)

# pystray's X11 backend does not apply icon or title writes on the calling
# thread: it posts a message to its own X event loop and then waits on an
# unbounded queue.get() for that loop to acknowledge. If the systray host dies —
# a GNOME Shell or extension restart destroys it — that acknowledgement may
# never come, and the caller blocks forever. So the daemon never writes to
# pystray directly; a dedicated thread does, and it is allowed to be the one
# that hangs. Beyond this many undrained updates we assume it has.
_MAX_PENDING_UPDATES = 8


class TrayState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


def _title(state: TrayState, paused: bool) -> str:
    # pystray's X11 backend sets the title via an Xlib string property, which it
    # encodes as latin-1 — a non-latin-1 character here raises instead of just
    # rendering oddly. Keep this ASCII.
    return f"blurt ({state.value}){' (paused)' if paused else ''}"


def _make_icon(state: TrayState) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    color = {
        TrayState.IDLE: (180, 180, 180, 255),
        TrayState.RECORDING: (220, 40, 40, 255),
        TrayState.PROCESSING: (220, 180, 40, 255),
    }[state]
    draw.ellipse((12, 12, 52, 52), fill=color)
    return img


class Tray:
    def __init__(
        self,
        on_quit: Callable[[], None],
        on_copy_last: Callable[[], None] | None = None,
        on_toggle_pause: Callable[[], None] | None = None,
    ) -> None:
        self._init_state(on_quit, on_copy_last, on_toggle_pause)
        # Imported here, not at module scope: pystray opens the X display as an
        # import side effect, which would make `import blurt.daemon` fail on a
        # headless machine even when the tray is disabled.
        import pystray

        self._icon = pystray.Icon(
            "blurt",
            icon=_make_icon(TrayState.IDLE),
            title="blurt (idle)",
            menu=pystray.Menu(
                pystray.MenuItem("Copy last transcript", self._handle_copy_last),
                pystray.MenuItem(
                    "Pause", self._handle_toggle_pause, checked=lambda _: self._paused
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._handle_quit),
            ),
        )

    def _init_state(
        self,
        on_quit: Callable[[], None],
        on_copy_last: Callable[[], None] | None,
        on_toggle_pause: Callable[[], None] | None,
    ) -> None:
        self._on_quit = on_quit
        self._on_copy_last = on_copy_last
        self._on_toggle_pause = on_toggle_pause
        self._state = TrayState.IDLE
        self._paused = False
        self._thread: threading.Thread | None = None
        self._updates: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._update_thread: threading.Thread | None = None
        self._degraded = False

    # --- lifecycle ---

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._icon.run, daemon=True, name="blurt-tray"
        )
        self._thread.start()
        self.start_updates()

    def start_updates(self) -> None:
        self._update_thread = threading.Thread(
            target=self._apply_updates, daemon=True, name="blurt-tray-updates"
        )
        self._update_thread.start()

    def stop(self) -> None:
        # icon.stop() marshals through the same X event loop, so it can block
        # exactly like an icon write; hand it to the update thread too.
        self._submit(self._icon.stop)
        self._updates.put(None)
        if self._update_thread is not None:
            self._update_thread.join(timeout=2.0)

    # --- public (non-blocking) ---

    def set_state(self, state: TrayState) -> None:
        self._state = state
        self._submit(self._apply_current)

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._submit(self._apply_current)

    @property
    def degraded(self) -> bool:
        return self._degraded

    @property
    def pending(self) -> int:
        return self._updates.qsize()

    @property
    def max_pending(self) -> int:
        return _MAX_PENDING_UPDATES

    # --- update thread ---

    def _submit(self, job: Callable[[], None]) -> None:
        if self._degraded:
            return
        if self._updates.qsize() >= _MAX_PENDING_UPDATES:
            self._degraded = True
            log.warning(
                "tray updates are not draining (%d queued) — the systray host has "
                "probably gone away. Leaving the icon stale for the rest of this run; "
                "dictation is unaffected.",
                self._updates.qsize(),
            )
            return
        self._updates.put(job)

    def _apply_updates(self) -> None:
        while True:
            job = self._updates.get()
            if job is None:
                return
            try:
                job()
            except Exception:
                log.warning("tray update failed", exc_info=True)

    def _apply_current(self) -> None:
        """Push the latest state to pystray, so queued updates coalesce."""
        self._icon.icon = _make_icon(self._state)
        self._icon.title = _title(self._state, self._paused)
        self._icon.update_menu()

    # --- callbacks (invoked on the pystray thread) ---

    def _handle_copy_last(self) -> None:
        if self._on_copy_last is not None:
            self._on_copy_last()

    def _handle_toggle_pause(self) -> None:
        if self._on_toggle_pause is not None:
            self._on_toggle_pause()

    def _handle_quit(self) -> None:
        log.info("tray quit requested")
        self._on_quit()
