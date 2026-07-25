from collections.abc import AsyncIterator

import pytest

from blurt.whisper_client import TranscriptEvent, WhisperSession


class FakeServer:
    """In-process Wyoming server for testing. Yields scripted events."""

    def __init__(self, events: list[TranscriptEvent]) -> None:
        self.events = events
        self.received_chunks: list[bytes] = []
        self.audio_started = False
        self.audio_stopped = False

    async def stream(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[TranscriptEvent]:
        self.audio_started = True
        async for chunk in audio_chunks:
            self.received_chunks.append(chunk)
        self.audio_stopped = True
        for ev in self.events:
            yield ev


@pytest.mark.asyncio
async def test_session_yields_partials_and_final() -> None:
    fake = FakeServer(events=[
        TranscriptEvent(text="hello", is_final=False),
        TranscriptEvent(text="hello world", is_final=False),
        TranscriptEvent(text="hello world.", is_final=True),
    ])

    async def audio() -> AsyncIterator[bytes]:
        yield b"\x00" * 320
        yield b"\x00" * 320

    session = WhisperSession(server=fake)
    collected: list[TranscriptEvent] = []
    async for ev in session.run(audio()):
        collected.append(ev)

    assert [e.text for e in collected] == ["hello", "hello world", "hello world."]
    assert collected[-1].is_final is True
    assert fake.audio_started
    assert fake.audio_stopped
    assert len(fake.received_chunks) == 2
