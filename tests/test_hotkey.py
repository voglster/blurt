import asyncio

import pytest
from evdev import ecodes

from blurt.hotkey import HotkeyListener, KeyEvent


class FakeKeyEvent:
    """Mimic evdev.KeyEvent enough for categorize() round-trip."""
    key_down = 1

    def __init__(self, keystate: int) -> None:
        self.keystate = keystate


class FakeInputEvent:
    def __init__(self, code: int, value: int) -> None:
        self.type = ecodes.EV_KEY
        self.code = code
        self.value = value


class FakeDevice:
    def __init__(self, events: list[FakeInputEvent]) -> None:
        self._events = events
        self.grabbed = False
        self.path = "/dev/input/fake"
        self.name = "fake"

    def capabilities(self) -> dict:
        return {ecodes.EV_KEY: list(ecodes.ecodes.values())}

    def grab(self) -> None:
        self.grabbed = True

    def ungrab(self) -> None:
        self.grabbed = False

    def close(self) -> None:
        pass

    async def async_read_loop(self):
        for e in self._events:
            yield e
            await asyncio.sleep(0)


def _key_down(name: str) -> FakeInputEvent:
    return FakeInputEvent(ecodes.ecodes[name], 1)


@pytest.mark.asyncio
async def test_toggle_only_in_idle(monkeypatch) -> None:
    events = [_key_down("KEY_CALC"), _key_down("KEY_ENTER"), _key_down("KEY_C")]
    dev = FakeDevice(events)
    listener = HotkeyListener(device=dev)

    received: list[KeyEvent] = []
    async for ke in listener.events():
        received.append(ke)
        if len(received) == 1:
            break

    assert received == [KeyEvent.TOGGLE]


@pytest.mark.asyncio
async def test_recording_mode_emits_all_four(monkeypatch) -> None:
    events = [_key_down("KEY_CALC"), _key_down("KEY_ENTER"), _key_down("KEY_C"), _key_down("KEY_ESC")]
    dev = FakeDevice(events)
    listener = HotkeyListener(device=dev)
    listener.set_recording(True)

    received: list[KeyEvent] = []
    async for ke in listener.events():
        received.append(ke)
        if len(received) == 4:
            break

    assert received == [KeyEvent.TOGGLE, KeyEvent.COMMIT, KeyEvent.COPY, KeyEvent.CANCEL]


@pytest.mark.asyncio
async def test_set_recording_grabs_and_ungrabs() -> None:
    dev = FakeDevice([])
    listener = HotkeyListener(device=dev)
    listener.set_recording(True)
    assert dev.grabbed is True
    listener.set_recording(False)
    assert dev.grabbed is False


class StrictGrabDevice(FakeDevice):
    """Mimics evdev: ungrab() on a non-grabbed device raises EINVAL."""

    def __init__(self) -> None:
        super().__init__([])
        self.ungrab_calls = 0

    def ungrab(self) -> None:
        self.ungrab_calls += 1
        if not self.grabbed:
            raise OSError(22, "Invalid argument")
        self.grabbed = False


def test_set_recording_false_when_never_grabbed_does_not_ungrab() -> None:
    dev = StrictGrabDevice()
    listener = HotkeyListener(device=dev)
    listener.set_recording(False)  # e.g. shutdown path with no active recording
    assert dev.ungrab_calls == 0


def test_set_recording_is_idempotent() -> None:
    dev = StrictGrabDevice()
    listener = HotkeyListener(device=dev)
    listener.set_recording(True)
    listener.set_recording(True)  # no double-grab
    assert dev.grabbed is True
    listener.set_recording(False)
    listener.set_recording(False)  # no EINVAL on second ungrab
    assert dev.grabbed is False
    assert dev.ungrab_calls == 1
