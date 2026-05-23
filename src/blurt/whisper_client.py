from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TranscriptEvent:
    text: str
    is_final: bool


class WhisperServer(Protocol):
    def stream(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[TranscriptEvent]: ...


class WhisperSession:
    def __init__(self, server: WhisperServer) -> None:
        self._server = server

    async def run(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[TranscriptEvent]:
        async for event in self._server.stream(audio_chunks):
            yield event


class WyomingServer:
    """Production WhisperServer: speaks Wyoming to a remote faster-whisper instance."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port

    async def stream(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[TranscriptEvent]:
        from wyoming.asr import Transcribe, Transcript
        from wyoming.audio import AudioChunk, AudioStart, AudioStop
        from wyoming.client import AsyncTcpClient

        async with AsyncTcpClient(self._host, self._port) as client:
            await client.write_event(Transcribe(language="en").event())
            await client.write_event(AudioStart(rate=16000, width=2, channels=1).event())

            async def send_audio() -> None:
                try:
                    async for chunk in audio_chunks:
                        await client.write_event(
                            AudioChunk(rate=16000, width=2, channels=1, audio=chunk).event()
                        )
                except Exception as exc:
                    log.info("audio stream ended: %s", exc)
                finally:
                    try:
                        await client.write_event(AudioStop().event())
                    except Exception:
                        pass

            send_task = asyncio.create_task(send_audio())
            try:
                while True:
                    event = await client.read_event()
                    if event is None:
                        break
                    if Transcript.is_type(event.type):
                        t = Transcript.from_event(event)
                        is_final = bool(getattr(t, "is_final", True))
                        yield TranscriptEvent(text=t.text or "", is_final=is_final)
                        if is_final:
                            break
            finally:
                send_task.cancel()
                try:
                    await send_task
                except (asyncio.CancelledError, Exception):
                    pass


class WhisperLiveServer:
    """WhisperServer that streams to a Collabora WhisperLive instance over WebSocket.

    Emits interim TranscriptEvents as segments update, then a final event
    when the server signals it has flushed all segments.
    """

    END_OF_AUDIO = b"END_OF_AUDIO"

    def __init__(
        self,
        host: str,
        port: int,
        model: str = "small.en",
        language: str = "en",
        use_vad: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._model = model
        self._language = language
        self._use_vad = use_vad

    async def stream(
        self, audio_chunks: AsyncIterator[bytes]
    ) -> AsyncIterator[TranscriptEvent]:
        from websockets.asyncio.client import connect

        uri = f"ws://{self._host}:{self._port}"
        uid = str(uuid.uuid4())

        async with connect(uri, max_size=2**24) as ws:
            await ws.send(json.dumps({
                "uid": uid,
                "language": self._language,
                "task": "transcribe",
                "model": self._model,
                "use_vad": self._use_vad,
                "send_last_n_segments": 10,
            }))

            # Wait for SERVER_READY before streaming audio.
            ready = False
            audio_sent_eof = False
            send_task: asyncio.Task[None] | None = None

            async def send_audio() -> None:
                try:
                    async for chunk in audio_chunks:
                        await ws.send(chunk)
                except Exception as exc:
                    log.info("audio stream ended: %s", exc)
                finally:
                    try:
                        await ws.send(WhisperLiveServer.END_OF_AUDIO)
                    except Exception:
                        pass

            last_text = ""
            try:
                while True:
                    try:
                        raw = await ws.recv()
                    except Exception as exc:
                        log.info("whisperlive socket closed: %s", exc)
                        break

                    if isinstance(raw, bytes):
                        continue
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    if msg.get("uid") != uid:
                        continue

                    if msg.get("message") == "SERVER_READY" and not ready:
                        ready = True
                        send_task = asyncio.create_task(send_audio())
                        continue

                    if msg.get("status") in ("ERROR", "WARNING", "WAIT"):
                        log.warning("whisperlive status: %s", msg)
                        continue

                    segments = msg.get("segments")
                    if segments is None:
                        continue

                    text = " ".join(s.get("text", "").strip() for s in segments).strip()
                    if not text:
                        continue
                    all_complete = all(s.get("completed") for s in segments)
                    is_final = all_complete and audio_sent_eof

                    if text != last_text or is_final:
                        last_text = text
                        yield TranscriptEvent(text=text, is_final=is_final)
                        if is_final:
                            break

                    # Track whether audio sender has finished
                    if send_task is not None and send_task.done() and not audio_sent_eof:
                        audio_sent_eof = True
            finally:
                if send_task is not None:
                    send_task.cancel()
                    try:
                        await send_task
                    except (asyncio.CancelledError, Exception):
                        pass
