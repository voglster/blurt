"""Measure Ollama cleanup latency across candidate models.

Runs the cleanup prompt against a set of test transcripts for each candidate
model and prints median + p95 latencies. Use the lowest-median model that
produces acceptable output.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import time

from blurt.cleanup_client import CleanupClient

SAMPLES = [
    "open git hub dot com",
    "git clone the repo and run cube cuttle apply",
    "lets debug this with post grass and check the j son output",
    "send a put request to the api endpoint",
    "the docker container failed to start due to a y a m l error",
]


async def _bench_model(host: str, port: int, model: str, timeout_ms: int) -> None:
    client = CleanupClient(
        base_url=f"http://{host}:{port}",
        model=model,
        timeout_ms=timeout_ms,
    )
    try:
        await client.cleanup(SAMPLES[0])  # warm-up

        latencies_ms: list[float] = []
        for sample in SAMPLES:
            t0 = time.perf_counter()
            result = await client.cleanup(sample)
            dt = (time.perf_counter() - t0) * 1000
            latencies_ms.append(dt)
            print(f"  [{dt:7.1f} ms] {sample!r} -> {result!r}")

        median = statistics.median(latencies_ms)
        p95 = sorted(latencies_ms)[int(0.95 * (len(latencies_ms) - 1))]
        print(f"\n  median={median:.1f} ms  p95={p95:.1f} ms\n")
    finally:
        await client.aclose()


async def _run(host: str, port: int, models: list[str], timeout_ms: int) -> None:
    for model in models:
        print(f"=== {model} ===")
        await _bench_model(host, port, model, timeout_ms)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="blurt bench-cleanup")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=11434)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen2.5:1.5b", "llama3.2:1b", "phi3:mini"],
    )
    parser.add_argument("--timeout-ms", type=int, default=5000)
    args = parser.parse_args(argv)
    asyncio.run(_run(args.host, args.port, args.models, args.timeout_ms))
    return 0
