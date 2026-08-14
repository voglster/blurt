from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

log = logging.getLogger(__name__)


class Watchdog:
    """Notices when a section that must never block blocks anyway.

    This runs on its own OS thread rather than as an asyncio timer, because the
    failure it exists to catch is the event loop itself stuck on a lock — and a
    loop-based timer cannot fire while the loop is blocked.
    """

    def __init__(
        self,
        timeout_s: float,
        on_wedge: Callable[[str], None],
        interval_s: float = 0.25,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout_s = timeout_s
        self._on_wedge = on_wedge
        self._interval_s = interval_s
        self._clock = clock
        self._lock = threading.Lock()
        self._deadline: float | None = None
        self._label = ""
        self._fired = False
        self._stopping = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._watch, daemon=True, name="blurt-watchdog"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopping.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    @contextmanager
    def guard(self, label: str) -> Iterator[None]:
        with self._lock:
            self._deadline = self._clock() + self._timeout_s
            self._label = label
        try:
            yield
        finally:
            with self._lock:
                self._deadline = None

    def check(self) -> bool:
        """Fire the callback if the guarded section is overdue.

        Returns whether it fired. Split out from the polling loop so the
        decision is testable without real threads or sleeps.
        """
        with self._lock:
            if self._deadline is None or self._fired:
                return False
            if self._clock() < self._deadline:
                return False
            self._fired = True
            label = self._label
        self._on_wedge(label)
        return True

    def _watch(self) -> None:
        while not self._stopping.wait(self._interval_s):
            try:
                self.check()
            except Exception:
                log.exception("watchdog check failed")
