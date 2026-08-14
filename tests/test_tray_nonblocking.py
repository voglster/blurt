import threading
import time

from blurt.tray import Tray, TrayState


class WedgedIcon:
    """Stands in for a pystray Icon whose systray host has died.

    pystray marshals icon/title writes onto its own X event-loop thread and
    waits on an unbounded queue.get(), so a dead host turns every write into a
    permanent block. This fake blocks the same way.
    """

    def __init__(self) -> None:
        self.released = threading.Event()
        self.writes = 0
        self._icon = None
        self._title = ""

    def _block(self) -> None:
        self.writes += 1
        self.released.wait()

    @property
    def icon(self):
        return self._icon

    @icon.setter
    def icon(self, value) -> None:
        self._block()
        self._icon = value

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value) -> None:
        self._block()
        self._title = value

    def update_menu(self) -> None:
        pass

    def stop(self) -> None:
        pass


def _tray_with(icon) -> Tray:
    tray = Tray.__new__(Tray)
    Tray._init_state(tray, on_quit=lambda: None, on_copy_last=None, on_toggle_pause=None)
    tray._icon = icon
    tray.start_updates()
    return tray


def _call_with_deadline(fn, timeout=2.0) -> bool:
    """Return True if fn() returned within `timeout`."""
    done = threading.Event()
    threading.Thread(target=lambda: (fn(), done.set()), daemon=True).start()
    return done.wait(timeout)


def test_set_state_returns_even_though_the_tray_is_wedged() -> None:
    icon = WedgedIcon()
    tray = _tray_with(icon)
    try:
        assert _call_with_deadline(lambda: tray.set_state(TrayState.RECORDING))
    finally:
        icon.released.set()


def test_wedged_tray_stops_accepting_updates_instead_of_growing() -> None:
    icon = WedgedIcon()
    tray = _tray_with(icon)
    try:
        for _ in range(200):
            tray.set_state(TrayState.RECORDING)
            tray.set_state(TrayState.IDLE)
        assert tray.degraded
        assert tray.pending <= tray.max_pending
    finally:
        icon.released.set()


def test_stop_gives_up_on_a_wedged_tray_rather_than_hanging() -> None:
    icon = WedgedIcon()
    tray = _tray_with(icon)
    try:
        tray.set_state(TrayState.RECORDING)
        time.sleep(0.05)
        assert _call_with_deadline(tray.stop, timeout=5.0)
    finally:
        icon.released.set()


def test_healthy_tray_applies_the_latest_state() -> None:
    class LiveIcon(WedgedIcon):
        def _block(self) -> None:
            self.writes += 1

    icon = LiveIcon()
    tray = _tray_with(icon)
    tray.set_state(TrayState.RECORDING)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and icon.title != "blurt (recording)":
        time.sleep(0.01)
    assert icon.title == "blurt (recording)"
    assert not tray.degraded
    tray.stop()
