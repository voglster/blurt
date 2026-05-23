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

    Emits interim TranscriptEvents as segments update, then a final event when
    no new segments arrive for ``QUIET_GAP_SECONDS`` after the audio source EOFs.

    NOTE: WhisperLive's faster_whisper backend disconnects immediately on
    END_OF_AUDIO without flushing, and its STT loop only processes audio when
    >=1s is buffered. We therefore (a) send a few seconds of silence after the
    real audio ends to push the buffer past the threshold, and (b) detect end
    of transcription via a quiet-gap timeout rather than END_OF_AUDIO.
    """

    SILENCE_PADDING_SECONDS = 2.0
    QUIET_GAP_SECONDS = 0.7
    RECV_POLL_SECONDS = 0.25

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
        import struct

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

            ready = False
            audio_sent_done = asyncio.Event()
            send_task: asyncio.Task[None] | None = None
            silence_chunk = struct.pack(f"<{1600}f", *([0.0] * 1600))  # 100ms

            async def send_audio() -> None:
                try:
                    async for chunk in audio_chunks:
                        n = len(chunk) // 2
                        if n == 0:
                            continue
                        samples = struct.unpack(f"<{n}h", chunk[: n * 2])
                        f32 = struct.pack(f"<{n}f", *(s / 32768.0 for s in samples))
                        await ws.send(f32)
                except Exception as exc:
                    log.info("audio stream ended: %s", exc)
                # Pad with silence to flush WhisperLive's >=1s buffer threshold.
                try:
                    n_silent = int(WhisperLiveServer.SILENCE_PADDING_SECONDS * 10)
                    for _ in range(n_silent):
                        await ws.send(silence_chunk)
                        await asyncio.sleep(0.05)
                except Exception:
                    pass
                audio_sent_done.set()

            loop = asyncio.get_running_loop()
            last_segment_time = 0.0
            last_text = ""
            last_segments: list[dict] = []

            try:
                while True:
                    try:
                        raw = await asyncio.wait_for(
                            ws.recv(), timeout=WhisperLiveServer.RECV_POLL_SECONDS
                        )
                    except asyncio.TimeoutError:
                        if audio_sent_done.is_set() and last_segment_time:
                            if loop.time() - last_segment_time > WhisperLiveServer.QUIET_GAP_SECONDS:
                                if last_segments:
                                    final_text = " ".join(
                                        s.get("text", "").strip() for s in last_segments
                                    ).strip()
                                    if final_text:
                                        yield TranscriptEvent(text=final_text, is_final=True)
                                break
                        # If audio done but never saw any segments, give up after a bit.
                        if audio_sent_done.is_set() and not last_segment_time:
                            if not hasattr(self, "_first_done_t"):
                                self._first_done_t = loop.time()
                            if loop.time() - self._first_done_t > 2.0:
                                log.info("whisperlive: no segments after audio sent; closing")
                                break
                        continue
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
                    last_segments = segments
                    last_segment_time = loop.time()
                    text = " ".join(s.get("text", "").strip() for s in segments).strip()
                    if text and text != last_text:
                        last_text = text
                        yield TranscriptEvent(text=text, is_final=False)
            finally:
                if send_task is not None:
                    send_task.cancel()
                    try:
                        await send_task
                    except (asyncio.CancelledError, Exception):
                        pass
