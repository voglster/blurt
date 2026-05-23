from __future__ import annotations

import subprocess
from typing import Protocol


def diff(last_typed: str, candidate: str) -> tuple[int, str]:
    """Compute the keystroke delta from `last_typed` to `candidate`.

    Returns (n_backspaces, tail_to_type).
    """
    # Longest common prefix
    i = 0
    n = min(len(last_typed), len(candidate))
    while i < n and last_typed[i] == candidate[i]:
        i += 1
    n_backspaces = len(last_typed) - i
    tail = candidate[i:]
    return n_backspaces, tail


class Runner(Protocol):
    def run(self, args: list[str]) -> None: ...


class SubprocessRunner:
    def run(self, args: list[str]) -> None:
        subprocess.run(args, check=False)


class Injector:
    def __init__(self, runner: Runner | None = None) -> None:
        self._runner = runner or SubprocessRunner()
        self.last_typed: str = ""

    def commit(self, candidate: str) -> None:
        n_back, tail = diff(self.last_typed, candidate)
        if n_back:
            self._runner.run([
                "xdotool", "key", "--clearmodifiers", "--delay", "0",
                "--repeat", str(n_back), "BackSpace",
            ])
        if tail:
            self._runner.run([
                "xdotool", "type", "--clearmodifiers", "--delay", "0", tail,
            ])
        self.last_typed = candidate

    def reset(self) -> None:
        self.last_typed = ""
