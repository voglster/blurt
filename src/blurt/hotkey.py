from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from enum import Enum

from evdev import InputDevice, KeyEvent as EvdevKeyEvent, categorize, ecodes, list_devices

log = logging.getLogger(__name__)


class KeyEvent(Enum):
    TOGGLE = "toggle"
    COMMIT = "commit"
    CANCEL = "cancel"
    COPY = "copy"


def _find_keyboard_with(keycode: str) -> InputDevice:
    target = ecodes.ecodes[keycode]
    for path in list_devices():
        dev = InputDevice(path)
        caps = dev.capabilities().get(ecodes.EV_KEY, [])
        if target in caps:
            log.info("hotkey device: %s (%s)", dev.path, dev.name)
            return dev
        dev.close()
    raise RuntimeError(f"no input device exposes {keycode}; add user to 'input' group?")


class HotkeyListener:
    """Watches an input device for the toggle key plus, while recording,
    Enter/Esc/C. Emits semantic `KeyEvent` values."""

    def __init__(
        self,
        keycode: str = "KEY_CALC",
        device_path: str | None = None,
        device: object | None = None,
    ) -> None:
        self._keycode = keycode
        self._device_path = device_path
        self._toggle_code = ecodes.ecodes[keycode]
        self._commit_code = ecodes.ecodes["KEY_ENTER"]
        self._cancel_code = ecodes.ecodes["KEY_ESC"]
        self._copy_code = ecodes.ecodes["KEY_C"]
        self._recording = False
        self._paused = False
        self._dev = device  # for testing; if None, opened in events()

    def set_recording(self, value: bool) -> None:
        self._recording = value
        if self._dev is None:
            return
        if value:
            try:
                self._dev.grab()
            except Exception as exc:
                log.warning("dev.grab() failed: %s", exc)
        else:
            try:
                self._dev.ungrab()
            except Exception as exc:
                log.warning("dev.ungrab() failed: %s", exc)

    def set_paused(self, value: bool) -> None:
        self._paused = value

    async def events(self) -> AsyncIterator[KeyEvent]:
        if self._dev is None:
            if self._device_path and self._device_path != "auto":
                self._dev = InputDevice(self._device_path)
            else:
                self._dev = _find_keyboard_with(self._keycode)

        try:
            async for event in self._dev.async_read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                key_event = categorize(event)
                if not isinstance(key_event, EvdevKeyEvent):
                    continue
                if key_event.keystate != EvdevKeyEvent.key_down:
                    continue

                code = event.code
                if code == self._toggle_code:
                    if self._paused:
                        continue
                    yield KeyEvent.TOGGLE
                elif self._recording and code == self._commit_code:
                    yield KeyEvent.COMMIT
                elif self._recording and code == self._cancel_code:
                    yield KeyEvent.CANCEL
                elif self._recording and code == self._copy_code:
                    yield KeyEvent.COPY
        finally:
            try:
                self._dev.close()
            except Exception:
                pass
