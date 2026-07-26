import pytest

from blurt.tray import TrayState, _title

ALL_COMBINATIONS = [(state, paused) for state in TrayState for paused in (False, True)]


@pytest.mark.parametrize(("state", "paused"), ALL_COMBINATIONS)
def test_title_survives_pystrays_latin_1_encoding(state: TrayState, paused: bool) -> None:
    _title(state, paused).encode("latin-1")


def test_title_reports_state():
    assert _title(TrayState.RECORDING, paused=False) == "blurt (recording)"


def test_title_reports_pause():
    assert _title(TrayState.IDLE, paused=True) == "blurt (idle) (paused)"
