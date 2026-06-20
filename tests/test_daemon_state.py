import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from blurt.daemon import Daemon, Outcome, State
from blurt.hotkey import KeyEvent


def _make_daemon_with_mocks() -> Daemon:
    """Build a Daemon with all I/O collaborators faked."""
    d = Daemon.__new__(Daemon)  # bypass real __init__
    d._cfg = MagicMock()
    d._cfg.cleanup.enabled = False
    d._cfg.tray.enabled = False
    d._corrections = MagicMock()
    d._corrections.apply.side_effect = lambda s: s
    d._cleanup = MagicMock()
    d._cleanup.aclose = AsyncMock()
    d._whisper_server = MagicMock()
    d._hotkey = MagicMock()
    d._tray = None
    d._overlay = MagicMock()
    d._type_at_window = MagicMock()
    d._clipboard_copy = MagicMock()
    d._get_active_window = MagicMock(return_value=42)
    d._state = State.IDLE
    d._session_task = None
    d._audio = None
    d._stop_event = asyncio.Event()
    d._loop = None
    d._target_window = None
    d._last_text = ""
    d._current_text = ""
    d._session_error = None
    d._notify_error = MagicMock()
    return d


@pytest.mark.asyncio
async def test_commit_types_at_captured_window() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "hello"
    d._target_window = 42
    await d._finalize(Outcome.COMMIT)
    d._type_at_window.assert_called_once_with(42, "hello", append_return=False)
    d._clipboard_copy.assert_not_called()
    assert d._last_text == "hello"
    assert d._state == State.IDLE


@pytest.mark.asyncio
async def test_commit_with_return_appends_enter() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "hello"
    d._target_window = 42
    await d._finalize(Outcome.COMMIT, with_return=True)
    d._type_at_window.assert_called_once_with(42, "hello", append_return=True)


@pytest.mark.asyncio
async def test_handle_key_routes_commit_with_return_for_enter() -> None:
    d = _make_daemon_with_mocks()
    d._state = State.RECORDING
    d._current_text = "x"
    d._target_window = 42
    await d._handle_key(KeyEvent.COMMIT)
    d._type_at_window.assert_called_once_with(42, "x", append_return=True)


@pytest.mark.asyncio
async def test_handle_key_routes_commit_without_return_for_toggle() -> None:
    d = _make_daemon_with_mocks()
    d._state = State.RECORDING
    d._current_text = "x"
    d._target_window = 42
    await d._handle_key(KeyEvent.TOGGLE)
    d._type_at_window.assert_called_once_with(42, "x", append_return=False)


@pytest.mark.asyncio
async def test_copy_writes_to_clipboard_no_typing() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "yo"
    d._target_window = 42
    await d._finalize(Outcome.COPY)
    d._clipboard_copy.assert_called_once_with("yo")
    d._type_at_window.assert_not_called()
    assert d._last_text == "yo"
    assert d._state == State.IDLE


@pytest.mark.asyncio
async def test_cancel_neither_types_nor_copies_but_remembers() -> None:
    d = _make_daemon_with_mocks()
    d._current_text = "discarded"
    d._target_window = 42
    await d._finalize(Outcome.CANCEL)
    d._type_at_window.assert_not_called()
    d._clipboard_copy.assert_not_called()
    assert d._last_text == "discarded"
    assert d._state == State.IDLE


@pytest.mark.asyncio
async def test_finalize_always_hides_overlay_and_ungrabs() -> None:
    for outcome in (Outcome.COMMIT, Outcome.COPY, Outcome.CANCEL):
        d = _make_daemon_with_mocks()
        d._current_text = "x"
        d._target_window = 42
        await d._finalize(outcome)
        d._overlay.hide.assert_called()
        d._hotkey.set_recording.assert_called_with(False)


def test_copy_last_uses_stored_text() -> None:
    d = _make_daemon_with_mocks()
    d._last_text = "previously"
    d._on_copy_last()
    d._clipboard_copy.assert_called_once_with("previously")


@pytest.mark.asyncio
async def test_auto_finalize_on_error_releases_grab() -> None:
    d = _make_daemon_with_mocks()
    d._state = State.RECORDING
    d._current_text = "partial"
    d._session_error = RuntimeError("whisper unreachable")
    await d._auto_finalize_on_error()
    d._hotkey.set_recording.assert_called_with(False)
    d._overlay.hide.assert_called()
    d._notify_error.assert_called_once_with("whisper unreachable")
    assert d._state == State.IDLE


def test_toggle_pause_flips_hotkey() -> None:
    d = _make_daemon_with_mocks()
    d._paused = False
    d._on_toggle_pause()
    assert d._paused is True
    d._hotkey.set_paused.assert_called_with(True)
    d._on_toggle_pause()
    assert d._paused is False
    d._hotkey.set_paused.assert_called_with(False)
