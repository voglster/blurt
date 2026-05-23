from __future__ import annotations

import logging
import threading
from enum import Enum

import pystray
from PIL import Image, ImageDraw

log = logging.getLogger(__name__)


class TrayState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


def _make_icon(state: TrayState) -> Image.Image:
    """Render a 64x64 icon for the given state."""
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
    def __init__(self, on_quit: callable) -> None:
        self._on_quit = on_quit
        self._icon = pystray.Icon(
            "blurt",
            icon=_make_icon(TrayState.IDLE),
            title="blurt (idle)",
            menu=pystray.Menu(
                pystray.MenuItem("Quit", self._handle_quit),
            ),
        )
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def set_state(self, state: TrayState) -> None:
        self._icon.icon = _make_icon(state)
        self._icon.title = f"blurt ({state.value})"

    def stop(self) -> None:
        self._icon.stop()

    def _handle_quit(self) -> None:
        log.info("tray quit requested")
        self._on_quit()
