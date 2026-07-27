from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Iterable, Sequence
from enum import Enum

from evdev import InputDevice, KeyEvent as EvdevKeyEvent, categorize, ecodes, list_devices

from blurt.config import HotkeyConfig

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


def group_bindings(bindings: Iterable[HotkeyConfig]) -> dict[str, list[str]]:
    """Collapse bindings into {device spec: [keycode, ...]}, preserving order.

    Two keys on one keyboard must not open that keyboard twice — a second open
    would compete for the same grab.
    """
    grouped: dict[str, list[str]] = {}
    for binding in bindings:
        codes = grouped.setdefault(binding.device, [])
        if binding.keycode not in codes:
            codes.append(binding.keycode)
    return grouped


class HotkeyListener:
    """Watches one or more keyboards for their toggle keys plus, while recording,
    Enter/Esc/C. Emits semantic `KeyEvent` values.

    Each device carries its own toggle keycodes: the Framework key (KEY_MEDIA) is
    only meaningful on the built-in keyboard, while an external keyboard may use a
    different key entirely.
    """

    def __init__(
        self,
        bindings: Sequence[HotkeyConfig] | None = None,
        keycode: str | None = None,
        device_path: str | None = None,
        device: object | None = None,
        devices: Sequence[tuple[object, Sequence[str]]] | None = None,
    ) -> None:
        if bindings is None:
            bindings = [HotkeyConfig(
                keycode=keycode or "KEY_CALC",
                device=device_path or "auto",
            )]
        self._bindings = list(bindings)
        self._commit_code = ecodes.ecodes["KEY_ENTER"]
        self._cancel_code = ecodes.ecodes["KEY_ESC"]
        self._copy_code = ecodes.ecodes["KEY_C"]
        self._recording = False
        self._paused = False
        self._grabbed = False

        # Test seams: `devices` supplies opened devices with their toggle codes;
        # `device` is the older single-device form.
        self._opened: list[tuple[object, set[int]]] = []
        if devices is not None:
            self._opened = [
                (dev, {ecodes.ecodes[c] for c in codes}) for dev, codes in devices
            ]
        elif device is not None:
            codes = {ecodes.ecodes[b.keycode] for b in self._bindings}
            self._opened = [(device, codes)]

    def _open(self) -> None:
        if self._opened:
            return
        for spec, keycodes in group_bindings(self._bindings).items():
            try:
                if spec and spec != "auto":
                    dev = InputDevice(spec)
                    log.info("hotkey device: %s (%s)", dev.path, dev.name)
                else:
                    dev = _find_keyboard_with(keycodes[0])
            except Exception as exc:
                log.warning("hotkey device %r unavailable (%s); skipping", spec, exc)
                continue
            self._opened.append((dev, {ecodes.ecodes[c] for c in keycodes}))
        if not self._opened:
            raise RuntimeError("no hotkey device could be opened")

    def set_recording(self, value: bool) -> None:
        self._recording = value
        if not self._opened:
            log.info("set_recording(%s) called before devices opened — no grab", value)
            return
        if value:
            if self._grabbed:
                return
            for dev, _ in self._opened:
                try:
                    dev.grab()
                    log.info("dev.grab() ok on %s", getattr(dev, "path", "?"))
                except Exception as exc:
                    log.warning("dev.grab() failed on %s: %s", getattr(dev, "path", "?"), exc)
            self._grabbed = True
        else:
            # Only ungrab if we actually hold the grab; ungrab on a non-grabbed
            # device raises EINVAL, which spammed the shutdown path with warnings.
            if not self._grabbed:
                return
            for dev, _ in self._opened:
                try:
                    dev.ungrab()
                    log.info("dev.ungrab() ok on %s", getattr(dev, "path", "?"))
                except Exception as exc:
                    log.warning("dev.ungrab() failed on %s: %s", getattr(dev, "path", "?"), exc)
            self._grabbed = False

    def set_paused(self, value: bool) -> None:
        self._paused = value

    def _classify(self, code: int, toggle_codes: set[int]) -> KeyEvent | None:
        if code in toggle_codes:
            return None if self._paused else KeyEvent.TOGGLE
        if not self._recording:
            return None
        if code == self._commit_code:
            return KeyEvent.COMMIT
        if code == self._cancel_code:
            return KeyEvent.CANCEL
        if code == self._copy_code:
            return KeyEvent.COPY
        return None

    async def _pump(self, dev, toggle_codes: set[int], out: asyncio.Queue) -> None:
        """Feed one device's key-downs into the shared queue.

        A device that dies (unplugged keyboard) must not take the others with it.
        """
        try:
            async for event in dev.async_read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                key_event = categorize(event)
                if not isinstance(key_event, EvdevKeyEvent):
                    continue
                if key_event.keystate != EvdevKeyEvent.key_down:
                    continue
                semantic = self._classify(event.code, toggle_codes)
                if semantic is not None:
                    await out.put(semantic)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("hotkey device %s stopped: %s", getattr(dev, "path", "?"), exc)
        finally:
            await out.put(None)

    async def events(self) -> AsyncIterator[KeyEvent]:
        self._open()
        queue: asyncio.Queue = asyncio.Queue()
        pumps = [
            asyncio.create_task(self._pump(dev, codes, queue))
            for dev, codes in self._opened
        ]
        live = len(pumps)
        try:
            while live:
                item = await queue.get()
                if item is None:
                    live -= 1
                    continue
                yield item
        finally:
            for task in pumps:
                task.cancel()
            for task in pumps:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            for dev, _ in self._opened:
                try:
                    dev.close()
                except Exception:
                    pass
