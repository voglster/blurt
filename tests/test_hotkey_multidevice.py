import asyncio

import pytest
from evdev import ecodes

from blurt.config import HotkeyConfig
from blurt.hotkey import HotkeyListener, KeyEvent


class FakeInputEvent:
    def __init__(self, code: int, value: int) -> None:
        self.type = ecodes.EV_KEY
        self.code = code
        self.value = value


class FakeDevice:
    """A keyboard that emits `events`, then optionally stays open forever."""

    def __init__(self, name: str, events: list[FakeInputEvent], linger: bool = False) -> None:
        self.name = name
        self.path = f"/dev/input/{name}"
        self._events = events
        self._linger = linger
        self.grabbed = False
        self.grab_calls = 0
        self.ungrab_calls = 0
        self.closed = False

    def capabilities(self) -> dict:
        return {ecodes.EV_KEY: list(ecodes.ecodes.values())}

    def grab(self) -> None:
        self.grabbed = True
        self.grab_calls += 1

    def ungrab(self) -> None:
        self.grabbed = False
        self.ungrab_calls += 1

    def close(self) -> None:
        self.closed = True

    async def async_read_loop(self):
        for e in self._events:
            yield e
            await asyncio.sleep(0)
        while self._linger:
            await asyncio.sleep(0.01)


def _down(name: str) -> FakeInputEvent:
    return FakeInputEvent(ecodes.ecodes[name], 1)


async def _collect(listener: HotkeyListener, count: int, timeout: float = 2.0):
    got: list[KeyEvent] = []

    async def run():
        async for ke in listener.events():
            got.append(ke)
            if len(got) >= count:
                return

    await asyncio.wait_for(run(), timeout)
    return got


@pytest.mark.asyncio
async def test_toggle_fires_from_either_keyboard():
    internal = FakeDevice("internal", [_down("KEY_MEDIA")], linger=True)
    external = FakeDevice("external", [_down("KEY_CALC")], linger=True)
    listener = HotkeyListener(devices=[(internal, ["KEY_MEDIA"]), (external, ["KEY_CALC"])])

    got = await _collect(listener, 2)

    assert got == [KeyEvent.TOGGLE, KeyEvent.TOGGLE]


@pytest.mark.asyncio
async def test_a_keycode_bound_on_one_device_is_ignored_on_another():
    """KEY_CALC belongs to the external keyboard here; the internal one must not fire."""
    internal = FakeDevice("internal", [_down("KEY_CALC"), _down("KEY_MEDIA")], linger=True)
    listener = HotkeyListener(devices=[(internal, ["KEY_MEDIA"])])

    got = await _collect(listener, 1)

    assert got == [KeyEvent.TOGGLE]


@pytest.mark.asyncio
async def test_in_session_keys_are_honoured_from_a_second_keyboard():
    internal = FakeDevice("internal", [_down("KEY_MEDIA")], linger=True)
    external = FakeDevice("external", [_down("KEY_ESC")], linger=True)
    listener = HotkeyListener(devices=[(internal, ["KEY_MEDIA"]), (external, ["KEY_CALC"])])
    listener.set_recording(True)

    got = await _collect(listener, 2)

    assert KeyEvent.CANCEL in got


@pytest.mark.asyncio
async def test_recording_grabs_every_watched_device():
    a = FakeDevice("a", [], linger=True)
    b = FakeDevice("b", [], linger=True)
    listener = HotkeyListener(devices=[(a, ["KEY_MEDIA"]), (b, ["KEY_CALC"])])

    listener.set_recording(True)

    assert (a.grabbed, b.grabbed) == (True, True)


@pytest.mark.asyncio
async def test_ending_a_session_releases_every_device():
    a = FakeDevice("a", [], linger=True)
    b = FakeDevice("b", [], linger=True)
    listener = HotkeyListener(devices=[(a, ["KEY_MEDIA"]), (b, ["KEY_CALC"])])

    listener.set_recording(True)
    listener.set_recording(False)

    assert (a.grabbed, b.grabbed) == (False, False)
    assert (a.ungrab_calls, b.ungrab_calls) == (1, 1)


@pytest.mark.asyncio
async def test_repeated_set_recording_grabs_once_per_device():
    a = FakeDevice("a", [], linger=True)
    listener = HotkeyListener(devices=[(a, ["KEY_MEDIA"])])

    listener.set_recording(True)
    listener.set_recording(True)

    assert a.grab_calls == 1


@pytest.mark.asyncio
async def test_pause_suppresses_toggle_on_all_devices():
    a = FakeDevice("a", [_down("KEY_MEDIA")], linger=False)
    b = FakeDevice("b", [_down("KEY_CALC")], linger=False)
    listener = HotkeyListener(devices=[(a, ["KEY_MEDIA"]), (b, ["KEY_CALC"])])
    listener.set_paused(True)

    got: list[KeyEvent] = []
    async for ke in listener.events():
        got.append(ke)

    assert got == []


@pytest.mark.asyncio
async def test_every_device_is_closed_on_exit():
    a = FakeDevice("a", [_down("KEY_MEDIA")], linger=False)
    b = FakeDevice("b", [], linger=False)
    listener = HotkeyListener(devices=[(a, ["KEY_MEDIA"]), (b, ["KEY_CALC"])])

    async for _ in listener.events():
        pass

    assert (a.closed, b.closed) == (True, True)


@pytest.mark.asyncio
async def test_one_dead_device_does_not_kill_the_other():
    """A keyboard unplugged mid-session raises on read; the rest must keep working."""

    class Exploding(FakeDevice):
        async def async_read_loop(self):
            raise OSError("device went away")
            yield  # pragma: no cover

    dead = Exploding("dead", [])
    alive = FakeDevice("alive", [_down("KEY_CALC")], linger=True)
    listener = HotkeyListener(devices=[(dead, ["KEY_MEDIA"]), (alive, ["KEY_CALC"])])

    got = await _collect(listener, 1)

    assert got == [KeyEvent.TOGGLE]


@pytest.mark.asyncio
async def test_bindings_config_is_accepted_directly():
    a = FakeDevice("a", [_down("KEY_MEDIA")], linger=True)
    listener = HotkeyListener(
        bindings=[HotkeyConfig(keycode="KEY_MEDIA", device="/dev/input/a")],
        devices=[(a, ["KEY_MEDIA"])],
    )

    assert await _collect(listener, 1) == [KeyEvent.TOGGLE]
