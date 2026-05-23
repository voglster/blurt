from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

log = logging.getLogger(__name__)

# 16kHz s16le mono = 32,000 bytes/sec. 100ms frames = 3200 bytes.
CHUNK_BYTES = 3200


class AudioCapture:
    def __init__(self) -> None:
        self._proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        if self._proc is not None:
            raise RuntimeError("AudioCapture already started")
        self._proc = await asyncio.create_subprocess_exec(
            "pw-cat",
            "--record",
            "-",
            "--format=s16",
            "--rate=16000",
            "--channels=1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        log.info("audio capture started (pid=%s)", self._proc.pid)

    async def chunks(self) -> AsyncIterator[bytes]:
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            chunk = await self._proc.stdout.readexactly(CHUNK_BYTES)
            yield chunk

    async def stop(self) -> None:
        if self._proc is None:
            return
        try:
            if self._proc.returncode is None:
                try:
                    self._proc.terminate()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(self._proc.wait(), timeout=1.0)
                except asyncio.TimeoutError:
                    try:
                        self._proc.kill()
                    except ProcessLookupError:
                        pass
                    await self._proc.wait()
        finally:
            log.info("audio capture stopped")
            self._proc = None
