from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from evdev import InputDevice, KeyEvent, categorize, ecodes, list_devices

log = logging.getLogger(__name__)


def _find_keyboard_with(keycode: str) -> InputDevice:
    """Return the first keyboard device that exposes the given KEY_* code."""
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
    def __init__(self, keycode: str = "KEY_CALC", device_path: str | None = None) -> None:
        self._keycode = keycode
        self._device_path = device_path
        self._target_code = ecodes.ecodes[keycode]

    async def toggles(self) -> AsyncIterator[None]:
        if self._device_path and self._device_path != "auto":
            dev = InputDevice(self._device_path)
        else:
            dev = _find_keyboard_with(self._keycode)

        loop = asyncio.get_running_loop()
        try:
            async for event in dev.async_read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                if event.code != self._target_code:
                    continue
                key_event = categorize(event)
                if isinstance(key_event, KeyEvent) and key_event.keystate == KeyEvent.key_down:
                    yield None
        finally:
            dev.close()
