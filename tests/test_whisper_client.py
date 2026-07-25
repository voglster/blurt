import json
from collections.abc import AsyncIterator

import pytest

from blurt.whisper_client import TranscriptEvent, WhisperLiveServer, WhisperSession


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


class FakeWebSocket:
    """Captures the config payload, then reports the connection closed."""

    def __init__(self) -> None:
        self.sent: list[str | bytes] = []

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        raise ConnectionError("closed by test")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


async def _no_audio() -> AsyncIterator[bytes]:
    return
    yield b""


async def _drain(server: WhisperLiveServer) -> None:
    async for _ in server.stream(_no_audio()):
        pass


@pytest.mark.asyncio
async def test_connect_payload_carries_prompt_and_hotwords(monkeypatch) -> None:
    ws = FakeWebSocket()
    monkeypatch.setattr("websockets.asyncio.client.connect", lambda *a, **k: ws)
    await _drain(WhisperLiveServer(
        host="h", port=1, model="small.en",
        initial_prompt="kubectl, Postgres", hotwords="kubectl,Postgres",
    ))

    config = json.loads(ws.sent[0])
    assert config["initial_prompt"] == "kubectl, Postgres"
    assert config["hotwords"] == "kubectl,Postgres"
    assert config["model"] == "small.en"


@pytest.mark.asyncio
async def test_connect_payload_omits_blank_prompt(monkeypatch) -> None:
    ws = FakeWebSocket()
    monkeypatch.setattr("websockets.asyncio.client.connect", lambda *a, **k: ws)
    await _drain(WhisperLiveServer(host="h", port=1, initial_prompt="", hotwords=""))

    config = json.loads(ws.sent[0])
    assert config["initial_prompt"] is None
    assert config["hotwords"] is None
