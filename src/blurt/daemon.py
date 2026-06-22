from __future__ import annotations

import asyncio
import logging
import signal
import subprocess
from enum import Enum
from pathlib import Path

from blurt import clipboard
from blurt.audio import AudioCapture
from blurt.cleanup_client import CleanupClient
from blurt.config import load as load_config
from blurt.corrections import load as load_corrections
from blurt.hotkey import HotkeyListener, KeyEvent
from blurt.injector import make_typer
from blurt.overlay import Overlay, OverlayConfig
from blurt.session import is_wayland
from blurt.tray import Tray, TrayState
from blurt.whisper_client import WhisperLiveServer, WhisperSession, WyomingServer

log = logging.getLogger(__name__)


def _notify(summary: str, body: str) -> None:
    try:
        subprocess.run(
            ["notify-send", "-a", "blurt", summary, body],
            check=False, timeout=1.0,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        log.warning("notify-send unavailable")


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    FINALIZING = "finalizing"


class Outcome(Enum):
    COMMIT = "commit"
    COPY = "copy"
    CANCEL = "cancel"


def _xdotool_get_active_window() -> int | None:
    try:
        out = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True, text=True, check=True, timeout=1.0,
        )
        return int(out.stdout.strip())
    except (subprocess.SubprocessError, ValueError) as exc:
        log.warning("getactivewindow failed: %s", exc)
        return None


class Daemon:
    def __init__(self) -> None:
        self._cfg = load_config()
        self._corrections = load_corrections(Path(self._cfg.corrections.file).expanduser())
        self._cleanup = CleanupClient(
            base_url=f"http://{self._cfg.cleanup.host}:{self._cfg.cleanup.port}",
            model=self._cfg.cleanup.model,
            timeout_ms=self._cfg.cleanup.timeout_ms,
        )
        if self._cfg.whisper.backend == "whisperlive":
            self._whisper_server = WhisperLiveServer(
                host=self._cfg.whisper.host,
                port=self._cfg.whisper.port,
                model=self._cfg.whisper.model,
                use_vad=self._cfg.whisper.use_vad,
            )
        else:
            self._whisper_server = WyomingServer(
                host=self._cfg.whisper.host,
                port=self._cfg.whisper.port,
            )
        self._hotkey = HotkeyListener(
            keycode=self._cfg.hotkey.keycode,
            device_path=self._cfg.hotkey.device,
        )
        self._overlay = Overlay(OverlayConfig(
            enabled=self._cfg.overlay.enabled,
            position=self._cfg.overlay.position,
            width_fraction=self._cfg.overlay.width_fraction,
            min_height_px=self._cfg.overlay.min_height_px,
            max_height_fraction=self._cfg.overlay.max_height_fraction,
            opacity=self._cfg.overlay.opacity,
            font=self._cfg.overlay.font,
        ))
        self._tray = (
            Tray(
                on_quit=self._request_stop,
                on_copy_last=self._on_copy_last,
                on_toggle_pause=self._on_toggle_pause,
            )
            if self._cfg.tray.enabled else None
        )
        self._type_at_window = make_typer()
        self._clipboard_copy = clipboard.make_copy()
        # Wayland has no global window activation, so there's nothing to
        # capture or restore — the overlay (hidden before we type) returns
        # focus to the previously-focused app on its own.
        self._get_active_window = (
            (lambda: None) if is_wayland() else _xdotool_get_active_window
        )
        self._notify_error = lambda msg: _notify("blurt: whisper error", msg)

        self._state = State.IDLE
        self._session_task: asyncio.Task[None] | None = None
        self._audio: AudioCapture | None = None
        self._stop_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._target_window: int | None = None
        self._last_text: str = ""
        self._current_text: str = ""
        self._paused: bool = False
        self._outcome: Outcome | None = None
        self._session_error: Exception | None = None

    # --- callbacks (may be invoked from tray thread) ---

    def _request_stop(self) -> None:
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        else:
            self._stop_event.set()

    def _on_copy_last(self) -> None:
        if self._last_text:
            self._clipboard_copy(self._last_text)

    def _on_toggle_pause(self) -> None:
        self._paused = not self._paused
        self._hotkey.set_paused(self._paused)
        if self._tray is not None:
            self._tray.set_paused(self._paused)

    def _set_tray(self, state: State) -> None:
        if self._tray is None:
            return
        mapping = {
            State.IDLE: TrayState.IDLE,
            State.RECORDING: TrayState.RECORDING,
            State.FINALIZING: TrayState.PROCESSING,
        }
        self._tray.set_state(mapping[state])

    # --- session ---

    async def _start_session(self) -> None:
        log.info("session start")
        self._state = State.RECORDING
        self._set_tray(self._state)
        self._target_window = self._get_active_window()
        self._current_text = ""
        self._session_error = None
        self._outcome = None
        self._overlay.show(target_window=self._target_window)
        self._overlay.set_text("")
        self._hotkey.set_recording(True)
        self._audio = AudioCapture()
        await self._audio.start()
        self._session_task = asyncio.create_task(self._run_session())

    async def _run_session(self) -> None:
        assert self._audio is not None
        session = WhisperSession(server=self._whisper_server)
        try:
            async for event in session.run(self._audio.chunks()):
                self._current_text = event.text
                self._overlay.set_text(event.text)
                if event.is_final:
                    break
        except Exception as exc:
            log.warning("session error: %s", exc)
            self._session_error = exc
            asyncio.get_event_loop().call_soon(
                lambda: asyncio.create_task(self._auto_finalize_on_error())
            )

    async def _auto_finalize_on_error(self) -> None:
        """Triggered when _run_session errors. Releases the device grab and
        hides the overlay so the user isn't locked out."""
        if self._state == State.RECORDING:
            await self._finalize(Outcome.CANCEL)

    async def _finalize(self, outcome: Outcome, with_return: bool = False) -> None:
        """Terminal transition out of RECORDING. Always returns daemon to IDLE.

        Fast-path: snapshot whatever the overlay was showing and act on that
        immediately. We do NOT wait for WhisperLive's "official final" — the
        user already accepted the displayed text by pressing commit.

        `with_return` appends an Enter keystroke after typing, used when the
        user committed via Enter (matches "Enter = submit" expectation).
        """
        import time as _time
        t0 = _time.monotonic()
        def _ms(label: str) -> None:
            log.info("finalize step %s @ +%dms", label, int((_time.monotonic() - t0) * 1000))

        log.info("finalize outcome=%s", outcome)
        self._state = State.FINALIZING
        self._set_tray(self._state)

        # Snapshot what the overlay showed — that's what the user committed to.
        text = self._current_text

        # Tear down audio and the whisper session in the background. Don't wait.
        if self._audio is not None:
            await self._audio.stop()
            self._audio = None
        _ms("audio-stopped")
        if self._session_task is not None and not self._session_task.done():
            self._session_task.cancel()
        self._session_task = None
        _ms("session-task-cancelled")

        if self._session_error is not None:
            self._notify_error(str(self._session_error))
            self._session_error = None

        # Cleanup + corrections only apply on COMMIT and COPY (not CANCEL).
        if outcome in (Outcome.COMMIT, Outcome.COPY) and text:
            if self._cfg.cleanup.enabled:
                cleaned = await self._cleanup.cleanup(text)
                if cleaned:
                    text = cleaned
            text = self._corrections.apply(text)
        _ms("text-processed")

        self._overlay.hide()
        _ms("overlay-hide-issued")

        # Type FIRST, ungrab AFTER. If the user is still holding Enter (or any
        # other recording-mode key) when we'd otherwise have ungrabbed, the
        # release event would leak to the focused app — e.g. terminal sees an
        # Enter right after the typed text. Holding the grab through the type
        # call ensures any lingering events are absorbed.
        if outcome == Outcome.COMMIT:
            self._type_at_window(self._target_window, text, append_return=with_return)
            _ms("typed")
        elif outcome == Outcome.COPY:
            self._clipboard_copy(text)
            _ms("clipboard-copied")
        # CANCEL: do nothing.

        self._hotkey.set_recording(False)
        _ms("hotkey-ungrabbed")

        self._last_text = text
        self._state = State.IDLE
        self._set_tray(self._state)
        self._target_window = None
        _ms("done")

    async def _handle_key(self, ke: KeyEvent) -> None:
        if self._state == State.IDLE:
            if ke == KeyEvent.TOGGLE:
                await self._start_session()
            return

        if self._state == State.RECORDING:
            if ke == KeyEvent.TOGGLE:
                await self._finalize(Outcome.COMMIT, with_return=False)
            elif ke == KeyEvent.COMMIT:
                await self._finalize(Outcome.COMMIT, with_return=True)
            elif ke == KeyEvent.COPY:
                await self._finalize(Outcome.COPY)
            elif ke == KeyEvent.CANCEL:
                await self._finalize(Outcome.CANCEL)
            return

        log.info("key %s ignored in state=%s", ke, self._state)

    # --- main loop ---

    async def run(self) -> int:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        self._overlay.start()
        if self._tray is not None:
            self._tray.start()
        self._set_tray(self._state)

        self._loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._loop.add_signal_handler(sig, self._request_stop)

        events = self._hotkey.events()
        try:
            while not self._stop_event.is_set():
                next_event = asyncio.create_task(events.__anext__())
                stop_task = asyncio.create_task(self._stop_event.wait())
                done, pending = await asyncio.wait(
                    {next_event, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()
                if stop_task in done:
                    break
                try:
                    ke = next_event.result()
                except StopAsyncIteration:
                    break
                await self._handle_key(ke)
        finally:
            if self._session_task is not None and not self._session_task.done():
                self._session_task.cancel()
                try:
                    await self._session_task
                except (asyncio.CancelledError, Exception):
                    pass
            self._hotkey.set_recording(False)
            if self._audio is not None:
                await self._audio.stop()
            await self._cleanup.aclose()
            self._overlay.stop()
            if self._tray is not None:
                self._tray.stop()
        return 0


def run() -> int:
    return asyncio.run(Daemon().run())
