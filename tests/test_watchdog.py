import pytest

from blurt.watchdog import Watchdog


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def _watchdog(clock, timeout_s=5.0):
    fired: list[str] = []
    wd = Watchdog(timeout_s=timeout_s, on_wedge=fired.append, clock=clock)
    return wd, fired


def test_idle_watchdog_never_fires(clock) -> None:
    wd, fired = _watchdog(clock)
    clock.advance(3600)
    assert not wd.check()
    assert fired == []


def test_section_that_finishes_in_time_never_fires(clock) -> None:
    wd, fired = _watchdog(clock)
    with wd.guard("start-session"):
        clock.advance(1.0)
        assert not wd.check()
    clock.advance(3600)
    assert not wd.check()
    assert fired == []


def test_section_that_overruns_fires_with_its_label(clock) -> None:
    wd, fired = _watchdog(clock)
    with wd.guard("start-session"):
        clock.advance(5.1)
        assert wd.check()
    assert fired == ["start-session"]


def test_it_fires_only_once(clock) -> None:
    wd, fired = _watchdog(clock)
    guard = wd.guard("start-session")  # held: dropping it would disarm on GC
    guard.__enter__()
    clock.advance(5.1)
    assert wd.check()
    clock.advance(5.1)
    assert not wd.check()
    assert fired == ["start-session"]


def test_a_section_raising_still_disarms(clock) -> None:
    wd, fired = _watchdog(clock)
    with pytest.raises(RuntimeError), wd.guard("start-session"):
        raise RuntimeError("boom")
    clock.advance(3600)
    assert not wd.check()
    assert fired == []
