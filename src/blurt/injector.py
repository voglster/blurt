from __future__ import annotations

import subprocess
import time
from typing import Protocol


class Runner(Protocol):
    def run(self, args: list[str]) -> None: ...


class SubprocessRunner:
    def run(self, args: list[str]) -> None:
        subprocess.run(args, check=False)


def type_at_window(
    window_id: int | None,
    text: str,
    runner: Runner | None = None,
    settle_ms: int = 30,
    append_return: bool = False,
) -> None:
    """Restore focus to `window_id` (if given) and type `text` via xdotool.

    One-shot: no diff, no backspaces. The overlay UX guarantees the caller
    only invokes this on commit, after the user has visually verified the text.

    If `append_return` is True, a Return keystroke is sent after the text —
    used when commit was triggered by Enter (vs. the toggle key), matching
    user expectation of "Enter submits."
    """
    if not text and not append_return:
        return
    runner = runner or SubprocessRunner()
    if window_id is not None:
        runner.run(["xdotool", "windowactivate", "--sync", str(window_id)])
        if settle_ms > 0:
            time.sleep(settle_ms / 1000.0)
    if text:
        runner.run(["xdotool", "type", "--clearmodifiers", "--delay", "0", text])
    if append_return:
        runner.run(["xdotool", "key", "--clearmodifiers", "Return"])
