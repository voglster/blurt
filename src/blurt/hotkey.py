from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from evdev import InputDevice, KeyEvent as EvdevKeyEvent, categorize, ecodes, list_devices

from blurt.config import ActionConfig, HotkeyConfig

log = logging.getLogger(__name__)

# How often to look for a configured keyboard that is not currently open. A dock
# or receiver coming back is noticed within this long. Only missing devices are
# probed, so with everything plugged in a tick is one list walk and nothing else.
RESCAN_INTERVAL_S = 2.0


class KeyEvent(Enum):
    TOGGLE = "toggle"
    COMMIT = "commit"
    CANCEL = "cancel"
    COPY = "copy"


@dataclass(frozen=True)
class ActionEvent:
    """A configured action key was pressed. Carries its command so consumers
    need no second lookup, and so a new sink costs only a config block."""
    command: str


Event = KeyEvent | ActionEvent


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


def _open_spec(spec: str, keycodes: Sequence[str]) -> InputDevice:
    if spec and spec != "auto":
        dev = InputDevice(spec)
        log.info("hotkey device: %s (%s)", dev.path, dev.name)
        return dev
    return _find_keyboard_with(keycodes[0])


@dataclass
class _Slot:
    """One watched keyboard: where to find it, its toggle keys, and the open
    device while it is present.

    `spec` is None for devices handed in directly (tests); those are never
    reopened, so a listener built only from them ends when they do.
    """

    spec: str | None
    keycodes: list[str]
    codes: set[int]
    dev: object | None = None
    # A spec that failed to open is only retried once its path exists again, so
    # an unplugged dock costs a stat per tick and logs once, not every 2s.
    warned: bool = False

    @property
    def reconnectable(self) -> bool:
        return self.spec is not None


class HotkeyListener:
    """Watches one or more keyboards for their toggle keys plus, while recording,
    Enter/Esc/C. Emits semantic `KeyEvent` values.

    Each device carries its own toggle keycodes: the Framework key (KEY_MEDIA) is
    only meaningful on the built-in keyboard, while an external keyboard may use a
    different key entirely.

    Configured keyboards come and go: a docked keyboard that is absent at start,
    or unplugged later, is picked up again when its device path reappears.
    """

    def __init__(
        self,
        bindings: Sequence[HotkeyConfig] | None = None,
        actions: Sequence[ActionConfig] = (),
        keycode: str | None = None,
        device_path: str | None = None,
        device: object | None = None,
        devices: Sequence[tuple[object, Sequence[str]]] | None = None,
        open_device=_open_spec,
        rescan_interval: float = RESCAN_INTERVAL_S,
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
        self._action_commands = {
            ecodes.ecodes[a.keycode]: a.command for a in actions
        }
        self._recording = False
        self._paused = False
        self._grabbed = False
        self._open_device = open_device
        self._rescan_interval = rescan_interval

        # Test seams: `devices` supplies opened devices with their toggle codes;
        # `device` is the older single-device form. Neither is reopened.
        self._slots: list[_Slot] = []
        if devices is not None:
            for dev, codes in devices:
                self._add_fixed(dev, list(codes))
        elif device is not None:
            self._add_fixed(device, [b.keycode for b in self._bindings])
        else:
            for spec, codes in group_bindings(self._bindings).items():
                self._slots.append(_Slot(
                    spec=spec, keycodes=codes,
                    codes={ecodes.ecodes[c] for c in codes},
                ))
        self._opened_once = devices is not None or device is not None

    def _add_fixed(self, dev: object, keycodes: list[str]) -> None:
        self._slots.append(_Slot(
            spec=None, keycodes=keycodes,
            codes={ecodes.ecodes[c] for c in keycodes}, dev=dev,
        ))

    @property
    def _opened(self) -> list[tuple[object, set[int]]]:
        return [(s.dev, s.codes) for s in self._slots if s.dev is not None]

    def _try_open(self, slot: _Slot) -> bool:
        """Open a missing slot's device. Returns True if it is now open."""
        if slot.dev is not None:
            return True
        explicit = slot.spec and slot.spec != "auto"
        if explicit and slot.warned and not os.path.exists(slot.spec):
            return False
        try:
            dev = self._open_device(slot.spec, slot.keycodes)
        except Exception as exc:
            if not slot.warned:
                log.warning(
                    "hotkey device %r unavailable (%s); will pick it up when it appears",
                    slot.spec, exc,
                )
                slot.warned = True
            return False
        slot.dev = dev
        slot.warned = False
        if self._grabbed:
            # A keyboard that shows up mid-dictation must not leak Enter/Esc/C
            # into the focused window while the others are grabbed.
            self._grab(dev)
        return True

    def _open(self) -> None:
        if self._opened_once:
            return
        self._opened_once = True
        for slot in self._slots:
            self._try_open(slot)
        if not self._opened:
            log.warning("no hotkey device present yet; waiting for one to appear")

    def _grab(self, dev) -> None:
        try:
            dev.grab()
            log.info("dev.grab() ok on %s", getattr(dev, "path", "?"))
        except Exception as exc:
            log.warning("dev.grab() failed on %s: %s", getattr(dev, "path", "?"), exc)

    def set_recording(self, value: bool) -> None:
        self._recording = value
        if not self._opened:
            log.info("set_recording(%s) called with no devices open — no grab", value)
            # Still track intent: a device that arrives mid-session gets grabbed.
            self._grabbed = value
            return
        if value:
            if self._grabbed:
                return
            for dev, _ in self._opened:
                self._grab(dev)
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

    def _classify(self, code: int, toggle_codes: set[int]) -> Event | None:
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
        command = self._action_commands.get(code)
        if command is not None:
            return ActionEvent(command)
        return None

    async def _pump(self, slot: _Slot, out: asyncio.Queue) -> None:
        """Feed one device's key-downs into the shared queue.

        A device that dies (unplugged keyboard) must not take the others with it.
        Its slot is emptied so the rescan can reopen it when it comes back.
        """
        dev = slot.dev
        try:
            async for event in dev.async_read_loop():
                if event.type != ecodes.EV_KEY:
                    continue
                key_event = categorize(event)
                if not isinstance(key_event, EvdevKeyEvent):
                    continue
                if key_event.keystate != EvdevKeyEvent.key_down:
                    continue
                semantic = self._classify(event.code, slot.codes)
                if semantic is not None:
                    await out.put(semantic)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("hotkey device %s stopped: %s", getattr(dev, "path", "?"), exc)
        if slot.reconnectable:
            try:
                dev.close()
            except Exception:
                pass
            slot.dev = None
        await out.put(None)

    async def events(self) -> AsyncIterator[Event]:
        self._open()
        queue: asyncio.Queue = asyncio.Queue()
        pumps: dict[int, asyncio.Task] = {}

        def start(slot: _Slot) -> None:
            pumps[id(slot)] = asyncio.create_task(self._pump(slot, queue))

        for slot in self._slots:
            if slot.dev is not None:
                start(slot)
        live = len(pumps)

        async def rescan() -> None:
            nonlocal live
            while True:
                await asyncio.sleep(self._rescan_interval)
                for slot in self._slots:
                    if not slot.reconnectable or slot.dev is not None:
                        continue
                    task = pumps.get(id(slot))
                    if task is not None and not task.done():
                        continue  # its pump is still winding down
                    if self._try_open(slot):
                        log.info("hotkey device reconnected: %s", slot.spec)
                        live += 1
                        start(slot)

        rescanner = (
            asyncio.create_task(rescan())
            if any(s.reconnectable for s in self._slots) else None
        )
        try:
            # With a reconnectable keyboard configured the stream never ends on
            # its own: losing every device just means waiting for one to return.
            while live or rescanner is not None:
                item = await queue.get()
                if item is None:
                    live -= 1
                    continue
                yield item
        finally:
            tasks = list(pumps.values())
            if rescanner is not None:
                tasks.append(rescanner)
            for task in tasks:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
            for slot in self._slots:
                if slot.dev is None:
                    continue
                try:
                    slot.dev.close()
                except Exception:
                    pass
