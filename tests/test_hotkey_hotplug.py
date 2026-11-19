"""Keyboards that come and go: docks, receivers, USB cables.

The listener must pick a configured keyboard up when it appears after start, and
again after it is unplugged and plugged back in, without a daemon restart.
"""

import asyncio

import pytest
from evdev import ecodes

from blurt.config import HotkeyConfig
from blurt.hotkey import HotkeyListener, KeyEvent


class FakeInputEvent:
    def __init__(self, code: int) -> None:
        self.type = ecodes.EV_KEY
        self.code = code
        self.value = 1


class Plug:
    """A keyboard whose reads can be fed keys or made to fail like an unplug."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.name = path
        self.queue: asyncio.Queue = asyncio.Queue()
        self.grabbed = False
        self.closed = False

    def press(self, keycode: str) -> None:
        self.queue.put_nowait(FakeInputEvent(ecodes.ecodes[keycode]))

    def unplug(self) -> None:
        self.queue.put_nowait(OSError(19, "No such device"))

    def grab(self) -> None:
        self.grabbed = True

    def ungrab(self) -> None:
        self.grabbed = False

    def close(self) -> None:
        self.closed = True

    async def async_read_loop(self):
        while True:
            item = await self.queue.get()
            if isinstance(item, Exception):
                raise item
            yield item


class Port:
    """Stands in for /dev/input: a path that exists only while plugged in."""

    def __init__(self, tmp_path, name: str) -> None:
        self.path = str(tmp_path / name)
        self.opens = 0
        self.attempts = 0
        self.current: Plug | None = None

    def plug_in(self) -> Plug:
        open(self.path, "w").close()
        self.current = Plug(self.path)
        return self.current

    def pull(self) -> None:
        import os
        os.unlink(self.path)
        if self.current is not None:
            self.current.unplug()
        self.current = None


def _opener(*ports: Port):
    by_path = {p.path: p for p in ports}

    def open_device(spec, keycodes):
        port = by_path[spec]
        port.attempts += 1
        if port.current is None:
            raise FileNotFoundError(spec)
        port.opens += 1
        return port.current

    return open_device


def _listener(*ports_and_keys, interval=0.01) -> HotkeyListener:
    ports = [p for p, _ in ports_and_keys]
    return HotkeyListener(
        bindings=[HotkeyConfig(keycode=k, device=p.path) for p, k in ports_and_keys],
        open_device=_opener(*ports),
        rescan_interval=interval,
    )


async def _next(agen, timeout=1.0):
    return await asyncio.wait_for(agen.__anext__(), timeout)


async def _abandon(pending, events):
    pending.cancel()
    try:
        await pending
    except asyncio.CancelledError:
        pass
    await events.aclose()


async def _until(cond, timeout=1.0):
    async def wait():
        while not cond():
            await asyncio.sleep(0.005)
    await asyncio.wait_for(wait(), timeout)


async def test_a_keyboard_absent_at_start_is_picked_up_when_docked(tmp_path):
    laptop, dock = Port(tmp_path, "laptop"), Port(tmp_path, "dock")
    kbd = laptop.plug_in()
    listener = _listener((laptop, "KEY_MEDIA"), (dock, "KEY_CALC"))
    events = listener.events()

    kbd.press("KEY_MEDIA")
    assert await _next(events) == KeyEvent.TOGGLE

    ext = dock.plug_in()
    await _until(lambda: dock.opens == 1)
    ext.press("KEY_CALC")
    assert await _next(events) == KeyEvent.TOGGLE
    await events.aclose()


async def test_an_unplugged_keyboard_works_again_after_replug(tmp_path):
    dock = Port(tmp_path, "dock")
    first = dock.plug_in()
    listener = _listener((dock, "KEY_CALC"))
    events = listener.events()

    first.press("KEY_CALC")
    assert await _next(events) == KeyEvent.TOGGLE

    dock.pull()
    await _until(lambda: first.closed)

    second = dock.plug_in()
    await _until(lambda: dock.opens == 2)
    second.press("KEY_CALC")
    assert await _next(events) == KeyEvent.TOGGLE
    await events.aclose()


async def test_losing_every_keyboard_does_not_end_the_stream(tmp_path):
    """The daemon treats the end of the stream as shutdown; undocking is not that."""
    dock = Port(tmp_path, "dock")
    dock.plug_in()
    listener = _listener((dock, "KEY_CALC"))
    events = listener.events()
    pending = asyncio.ensure_future(events.__anext__())

    dock.pull()
    await asyncio.sleep(0.05)
    assert not pending.done()

    dock.plug_in().press("KEY_CALC")
    assert await asyncio.wait_for(pending, 1.0) == KeyEvent.TOGGLE
    await events.aclose()


async def test_starting_with_no_keyboard_waits_instead_of_failing(tmp_path):
    dock = Port(tmp_path, "dock")
    listener = _listener((dock, "KEY_CALC"))
    events = listener.events()
    pending = asyncio.ensure_future(events.__anext__())

    await asyncio.sleep(0.05)
    assert not pending.done()

    dock.plug_in().press("KEY_CALC")
    assert await asyncio.wait_for(pending, 1.0) == KeyEvent.TOGGLE
    await events.aclose()


async def test_a_keyboard_docked_mid_dictation_is_grabbed(tmp_path):
    laptop, dock = Port(tmp_path, "laptop"), Port(tmp_path, "dock")
    internal = laptop.plug_in()
    listener = _listener((laptop, "KEY_MEDIA"), (dock, "KEY_CALC"))
    events = listener.events()
    pending = asyncio.ensure_future(events.__anext__())
    await asyncio.sleep(0.02)

    listener.set_recording(True)
    assert internal.grabbed

    ext = dock.plug_in()
    await _until(lambda: dock.opens == 1)
    assert ext.grabbed

    listener.set_recording(False)
    assert not ext.grabbed
    await _abandon(pending, events)


async def test_a_missing_path_is_not_reopened_every_tick(tmp_path):
    """Once a device is known missing, only a stat runs until its node returns."""
    dock = Port(tmp_path, "dock")
    listener = _listener((dock, "KEY_CALC"))
    events = listener.events()
    pending = asyncio.ensure_future(events.__anext__())

    await asyncio.sleep(0.1)
    assert dock.attempts == 1

    await _abandon(pending, events)


async def test_every_open_keyboard_is_closed_on_exit(tmp_path):
    laptop, dock = Port(tmp_path, "laptop"), Port(tmp_path, "dock")
    a, b = laptop.plug_in(), dock.plug_in()
    listener = _listener((laptop, "KEY_MEDIA"), (dock, "KEY_CALC"))
    events = listener.events()
    a.press("KEY_MEDIA")
    await _next(events)

    await events.aclose()

    assert (a.closed, b.closed) == (True, True)
