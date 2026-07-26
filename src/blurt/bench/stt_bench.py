"""Compare WhisperLive candidate models on latency and accuracy.

Streams each fixture WAV at real-time pace and reports, per model: time to first
partial, partial count, time to final, and WER against the fixture's reference
transcript. Fixtures are `<name>.wav` + `<name>.txt` pairs in tests/fixtures/.

A fixture named `silence` is streamed and printed but excluded from the aggregate
scores — it exists to catch an `initial_prompt` that makes the model hallucinate
prompt-adjacent text when there is nothing to transcribe.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from blurt.config import Config, load
from blurt.wer import wer as word_error_rate
from blurt.whisper_client import WhisperLiveServer, WhisperSession

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def resolve_prompting(
    initial_prompt: str | None,
    hotwords: str | None,
    no_prompt: bool,
    config: Config | None = None,
) -> tuple[str | None, str | None]:
    """Decide what prompting to benchmark with.

    Defaulting to the user's `[stt]` config means the benchmark measures the
    setup they actually dictate under. Passing either flag suppresses config for
    both, so a run never silently mixes a flag with a config value the user did
    not pair it with; `--no-prompt` forces the bare baseline.
    """
    if no_prompt:
        return None, None
    if initial_prompt is not None or hotwords is not None:
        return initial_prompt, hotwords
    cfg = config if config is not None else load()
    return cfg.stt.initial_prompt or None, cfg.stt.hotwords or None


@dataclass
class Result:
    fixture: str
    first_partial_ms: float | None
    n_partials: int
    final_ms: float
    wer: float
    text: str


async def _wav_chunks(path: Path, chunk_ms: int = 100):
    with wave.open(str(path), "rb") as w:
        assert w.getframerate() == 16000, f"{path.name}: must be 16kHz"
        assert w.getsampwidth() == 2, f"{path.name}: must be s16"
        assert w.getnchannels() == 1, f"{path.name}: must be mono"
        frames = int(16000 * chunk_ms / 1000)
        while True:
            data = w.readframes(frames)
            if not data:
                return
            yield data
            await asyncio.sleep(chunk_ms / 1000)


async def _run_fixture(
    host: str, port: int, model: str, wav: Path, reference: str,
    initial_prompt: str | None, hotwords: str | None,
) -> Result:
    server = WhisperLiveServer(
        host=host, port=port, model=model,
        initial_prompt=initial_prompt, hotwords=hotwords,
    )
    session = WhisperSession(server=server)
    t0 = time.perf_counter()
    first_partial_ms: float | None = None
    n_partials = 0
    text = ""
    async for event in session.run(_wav_chunks(wav)):
        elapsed_ms = (time.perf_counter() - t0) * 1000
        text = event.text
        if event.is_final:
            break
        n_partials += 1
        if first_partial_ms is None:
            first_partial_ms = elapsed_ms
    return Result(
        fixture=wav.stem,
        first_partial_ms=first_partial_ms,
        n_partials=n_partials,
        final_ms=(time.perf_counter() - t0) * 1000,
        wer=word_error_rate(reference, text),
        text=text,
    )


async def _run(
    host: str, port: int, models: list[str], fixtures: Path,
    initial_prompt: str | None, hotwords: str | None,
) -> None:
    pairs = [(w, w.with_suffix(".txt")) for w in sorted(fixtures.glob("*.wav"))]
    pairs = [(w, t) for w, t in pairs if t.exists()]
    if not pairs:
        raise SystemExit(f"no <name>.wav + <name>.txt pairs in {fixtures}")

    for model in models:
        print(f"\n=== {model} ===")
        results: list[Result] = []
        for wav, txt in pairs:
            reference = txt.read_text().strip()
            r = await _run_fixture(
                host, port, model, wav, reference, initial_prompt, hotwords
            )
            results.append(r)
            first = f"{r.first_partial_ms:.0f}" if r.first_partial_ms else "  -"
            print(
                f"  {r.fixture:10s} wer={r.wer:5.3f} "
                f"first_partial={first:>6s}ms partials={r.n_partials:3d} "
                f"final={r.final_ms:7.0f}ms"
            )
            print(f"    {r.text!r}")
        scored = [r for r in results if r.fixture != "silence"]
        if scored:
            print(
                f"  ---> mean WER {statistics.mean(r.wer for r in scored):.3f}   "
                f"median final {statistics.median(r.final_ms for r in scored):.0f}ms"
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blurt bench-stt")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=9091)
    parser.add_argument(
        "--models", nargs="+",
        default=[
            "base.en",
            "small.en",
            "distil-whisper/distil-large-v3.5-ct2",
            "deepdml/faster-whisper-large-v3-turbo-ct2",
        ],
    )
    parser.add_argument("--fixtures", type=Path, default=FIXTURES)
    parser.add_argument(
        "--initial-prompt", default=None,
        help="override [stt] initial_prompt from your config",
    )
    parser.add_argument(
        "--hotwords", default=None,
        help="override [stt] hotwords from your config",
    )
    parser.add_argument(
        "--no-prompt", action="store_true",
        help="benchmark with no prompting at all, ignoring your config",
    )
    args = parser.parse_args(argv)
    initial_prompt, hotwords = resolve_prompting(
        args.initial_prompt, args.hotwords, args.no_prompt
    )
    print(f"initial_prompt: {initial_prompt!r}\nhotwords:       {hotwords!r}")
    asyncio.run(_run(
        args.host, args.port, args.models, args.fixtures,
        initial_prompt, hotwords,
    ))
    return 0
