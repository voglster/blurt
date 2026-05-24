from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from enum import Enum

import pystray
from PIL import Image, ImageDraw

log = logging.getLogger(__name__)


class TrayState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


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
        self._on_quit = on_quit
        self._on_copy_last = on_copy_last
        self._on_toggle_pause = on_toggle_pause
        self._state = TrayState.IDLE
        self._paused = False
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
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def set_state(self, state: TrayState) -> None:
        self._state = state
        self._icon.icon = _make_icon(state)
        self._refresh_title()

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        self._refresh_title()
        self._icon.update_menu()

    def stop(self) -> None:
        self._icon.stop()

    def _refresh_title(self) -> None:
        suffix = " — paused" if self._paused else ""
        self._icon.title = f"blurt ({self._state.value}){suffix}"

    def _handle_copy_last(self) -> None:
        if self._on_copy_last is not None:
            self._on_copy_last()

    def _handle_toggle_pause(self) -> None:
        if self._on_toggle_pause is not None:
            self._on_toggle_pause()

    def _handle_quit(self) -> None:
        log.info("tray quit requested")
        self._on_quit()
