from __future__ import annotations

import logging
import subprocess
from typing import Callable, Protocol

from blurt.session import is_wayland

log = logging.getLogger(__name__)


class Runner(Protocol):
    def run(self, args: list[str], stdin_bytes: bytes) -> None: ...


class SubprocessRunner:
    def run(self, args: list[str], stdin_bytes: bytes) -> None:
        try:
            subprocess.run(args, input=stdin_bytes, check=False, timeout=2.0)
        except subprocess.TimeoutExpired:
            log.warning("%s timed out", args[0])
        except FileNotFoundError:
            log.warning("%s not found; clipboard copy skipped", args[0])


def _argv() -> list[str]:
    # wl-copy owns the Wayland clipboard; xclip only drives the X11 selection,
    # which native Wayland apps can't read.
    return ["wl-copy"] if is_wayland() else ["xclip", "-selection", "clipboard"]


def copy(
    text: str,
    runner: Runner | None = None,
    argv: list[str] | None = None,
) -> None:
    """Place `text` on the system clipboard via `argv` (defaults to xclip)."""
    if not text:
        return
    runner = runner or SubprocessRunner()
    runner.run(argv or ["xclip", "-selection", "clipboard"], text.encode("utf-8"))


def make_copy(runner: Runner | None = None) -> Callable[[str], None]:
    """Return a copy function bound to the right clipboard tool for the session."""
    argv = _argv()
    return lambda text: copy(text, runner=runner, argv=argv)
