"""Measure Wyoming whisper partial cadence and final latency.

Streams a known WAV file in real-time-ish chunks to llmbox:10300 and prints
how long it takes to receive each transcript event.
"""

from __future__ import annotations

import argparse
import asyncio
import time
import wave
from pathlib import Path

from blurt.whisper_client import WhisperSession, WyomingServer


async def _wav_chunks(path: Path, chunk_ms: int = 100):
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == 16000, "WAV must be 16kHz"
        assert w.getsampwidth() == 2, "WAV must be s16"
        assert w.getnchannels() == 1, "WAV must be mono"
        frames_per_chunk = int(16000 * chunk_ms / 1000)
        while True:
            data = w.readframes(frames_per_chunk)
            if not data:
                return
            yield data
            await asyncio.sleep(chunk_ms / 1000)


async def _run(host: str, port: int, wav: Path) -> None:
    server = WyomingServer(host=host, port=port)
    session = WhisperSession(server=server)
    t0 = time.perf_counter()
    n_partial = 0
    async for event in session.run(_wav_chunks(wav)):
        dt = (time.perf_counter() - t0) * 1000
        kind = "FINAL" if event.is_final else "partial"
        print(f"[{dt:7.1f} ms] {kind:7s} {event.text!r}")
        if not event.is_final:
            n_partial += 1
    print(f"\n{n_partial} partials, final latency {(time.perf_counter() - t0) * 1000:.1f} ms total")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blurt bench-whisper")
    parser.add_argument("--host", default="llmbox")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument(
        "--wav",
        type=Path,
        default=Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "sample.wav",
    )
    args = parser.parse_args(argv)
    asyncio.run(_run(args.host, args.port, args.wav))
    return 0
