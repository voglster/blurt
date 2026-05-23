from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


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
            await client.write_event(
                AudioStart(rate=16000, width=2, channels=1).event()
            )
            import asyncio

            async def send_audio() -> None:
                async for chunk in audio_chunks:
                    await client.write_event(
                        AudioChunk(rate=16000, width=2, channels=1, audio=chunk).event()
                    )
                await client.write_event(AudioStop().event())

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
                except asyncio.CancelledError:
                    pass
