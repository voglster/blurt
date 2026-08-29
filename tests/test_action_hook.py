import asyncio
import textwrap
from pathlib import Path
import pytest
from evdev import ecodes

from blurt.config import ActionConfig, load
from blurt.daemon import Outcome, State
from blurt.hotkey import ActionEvent, HotkeyListener, KeyEvent
from tests.test_daemon_state import _make_daemon_with_mocks
from tests.test_hotkey import FakeDevice, _key_down


def test_load_actions(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text(
        textwrap.dedent("""
            [[actions]]
            keycode = "KEY_P"
            command = "piper-send"
        """)
    )

    cfg = load(cfg_file)

    assert cfg.actions == (ActionConfig(keycode="KEY_P", command="piper-send"),)


def test_no_actions_configured_by_default(tmp_path: Path) -> None:
    cfg_file = tmp_path / "config.toml"
    cfg_file.write_text("[tray]\nenabled = true\n")
    assert load(cfg_file).actions == ()


def _listener() -> HotkeyListener:
    return HotkeyListener(
        keycode="KEY_CALC",
        actions=[ActionConfig(keycode="KEY_P", command="piper-send")],
    )


def test_action_key_classifies_while_recording() -> None:
    listener = _listener()
    listener._recording = True
    assert listener._classify(ecodes.ecodes["KEY_P"], set()) == ActionEvent("piper-send")


def test_action_key_ignored_when_idle() -> None:
    listener = _listener()
    assert listener._classify(ecodes.ecodes["KEY_P"], set()) is None


def test_unconfigured_key_still_ignored_while_recording() -> None:
    listener = _listener()
    listener._recording = True
    assert listener._classify(ecodes.ecodes["KEY_Q"], set()) is None


async def _drain_action_tasks(daemon) -> None:
    while daemon._action_tasks:
        await asyncio.gather(*daemon._action_tasks)


@pytest.mark.asyncio
async def test_action_pipes_corrected_text_to_command(tmp_path: Path) -> None:
    sink = tmp_path / "sink.txt"
    d = _make_daemon_with_mocks()
    d._state = State.RECORDING
    d._corrections.apply.side_effect = lambda text: text.replace("piper", "Piper")
    d._current_text = "hey piper"

    await d._handle_key(ActionEvent(f"sh -c 'cat > {sink}'"))
    await _drain_action_tasks(d)

    assert sink.read_text() == "hey Piper"
    d._type_at_window.assert_not_called()
    d._clipboard_copy.assert_not_called()
    assert d._state == State.IDLE


@pytest.mark.asyncio
async def test_action_that_cannot_launch_notifies_instead_of_raising() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "hello"

    await d._finalize(Outcome.ACTION, command="blurt-no-such-sink-exists")
    await _drain_action_tasks(d)

    d._notify_error.assert_called_once()
    assert d._state == State.IDLE


@pytest.mark.asyncio
async def test_empty_action_command_notifies() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "hello"

    await d._finalize(Outcome.ACTION, command="   ")

    d._notify_error.assert_called_once()
    assert not d._action_tasks


@pytest.mark.asyncio
async def test_action_key_reaches_the_event_stream() -> None:
    dev = FakeDevice([_key_down("KEY_CALC"), _key_down("KEY_P")])
    listener = HotkeyListener(
        device=dev,
        keycode="KEY_CALC",
        actions=[ActionConfig(keycode="KEY_P", command="piper-send")],
    )

    received = []
    async for event in listener.events():
        received.append(event)
        if event is KeyEvent.TOGGLE:
            listener.set_recording(True)

    assert received == [KeyEvent.TOGGLE, ActionEvent("piper-send")]
