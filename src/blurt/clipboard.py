from __future__ import annotations

import logging
import subprocess
from typing import Protocol

log = logging.getLogger(__name__)


class Runner(Protocol):
    def run(self, args: list[str], stdin_bytes: bytes) -> None: ...


class SubprocessRunner:
    def run(self, args: list[str], stdin_bytes: bytes) -> None:
        try:
            subprocess.run(args, input=stdin_bytes, check=False, timeout=2.0)
        except subprocess.TimeoutExpired:
            log.warning("xclip timed out")
        except FileNotFoundError:
            log.warning("xclip not found; clipboard copy skipped")


def copy(text: str, runner: Runner | None = None) -> None:
    """Place `text` on the X11 CLIPBOARD selection via xclip."""
    if not text:
        return
    runner = runner or SubprocessRunner()
    runner.run(["xclip", "-selection", "clipboard"], text.encode("utf-8"))
