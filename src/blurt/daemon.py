from __future__ import annotations

import asyncio
import logging
import signal
from enum import Enum
from pathlib import Path

from blurt.audio import AudioCapture
from blurt.cleanup_client import CleanupClient
from blurt.config import load as load_config
from blurt.corrections import load as load_corrections
from blurt.hotkey import HotkeyListener
from blurt.injector import Injector
from blurt.tray import Tray, TrayState
from blurt.whisper_client import WhisperLiveServer, WhisperSession, WyomingServer

log = logging.getLogger(__name__)


class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    FINALIZING = "finalizing"


class Daemon:
    def __init__(self) -> None:
        self._cfg = load_config()
        self._corrections = load_corrections(Path(self._cfg.corrections.file).expanduser())
        self._injector = Injector()
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
        self._tray = Tray(on_quit=self._request_stop) if self._cfg.tray.enabled else None
        self._state = State.IDLE
        self._session_task: asyncio.Task[None] | None = None
        self._audio: AudioCapture | None = None
        self._stop_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None  # set in run()

    def _request_stop(self) -> None:
        # May be called from tray thread OR signal handler (loop thread).
        if self._loop is not None and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)
        else:
            self._stop_event.set()

    def _set_tray(self, state: State) -> None:
        if self._tray is None:
            return
        mapping = {
            State.IDLE: TrayState.IDLE,
            State.RECORDING: TrayState.RECORDING,
            State.FINALIZING: TrayState.PROCESSING,
        }
        self._tray.set_state(mapping[state])

    async def _on_toggle(self) -> None:
        if self._state == State.IDLE:
            await self._start_session()
        elif self._state == State.RECORDING:
            await self._finish_session()
        else:
            log.info("toggle ignored in state=%s", self._state)

    async def _start_session(self) -> None:
        log.info("session start")
        self._state = State.RECORDING
        self._set_tray(self._state)
        self._injector.reset()
        self._audio = AudioCapture()
        await self._audio.start()
        self._session_task = asyncio.create_task(self._run_session())

    async def _run_session(self) -> None:
        assert self._audio is not None
        session = WhisperSession(server=self._whisper_server)
        final_text = ""
        try:
            async for event in session.run(self._audio.chunks()):
                self._injector.commit(event.text)
                if event.is_final:
                    final_text = event.text
                    break
        except Exception as exc:
            log.warning("session error: %s", exc)
            self._state = State.IDLE
            self._set_tray(self._state)
            return

        if self._cfg.cleanup.enabled and final_text:
            cleaned = await self._cleanup.cleanup(final_text)
            if cleaned and cleaned != final_text:
                self._injector.commit(cleaned)
                final_text = cleaned

        corrected = self._corrections.apply(final_text)
        if corrected != final_text:
            self._injector.commit(corrected)

        self._state = State.IDLE
        self._set_tray(self._state)
        self._injector.reset()
        self._session_task = None

    async def _finish_session(self) -> None:
        log.info("session finish requested")
        self._state = State.FINALIZING
        self._set_tray(self._state)
        # Capture the user's trailing audio (e.g. the last word still tailing off
        # when they tap the hotkey) before tearing down pw-cat.
        await asyncio.sleep(0.3)
        if self._audio is not None:
            await self._audio.stop()
            self._audio = None
        if self._session_task is not None:
            await self._session_task

    async def run(self) -> int:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
        if self._tray is not None:
            self._tray.start()
        self._set_tray(self._state)

        self._loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._loop.add_signal_handler(sig, self._request_stop)

        toggle_iter = self._hotkey.toggles()
        try:
            while not self._stop_event.is_set():
                next_toggle = asyncio.create_task(toggle_iter.__anext__())
                stop_task = asyncio.create_task(self._stop_event.wait())
                done, pending = await asyncio.wait(
                    {next_toggle, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for p in pending:
                    p.cancel()
                if stop_task in done:
                    break
                try:
                    next_toggle.result()
                except StopAsyncIteration:
                    break
                await self._on_toggle()
        finally:
            if self._session_task is not None and not self._session_task.done():
                self._session_task.cancel()
                try:
                    await self._session_task
                except (asyncio.CancelledError, Exception):
                    pass
            if self._audio is not None:
                await self._audio.stop()
            await self._cleanup.aclose()
            if self._tray is not None:
                self._tray.stop()
        return 0


def run() -> int:
    return asyncio.run(Daemon().run())
