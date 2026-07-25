"""Word error rate, stdlib-only, for comparing STT candidates in the bench."""

from __future__ import annotations

import re

_NOT_WORD_CHARS = re.compile(r"[^\w\s]")


def normalize(text: str) -> list[str]:
    return _NOT_WORD_CHARS.sub("", text.lower()).split()


def wer(reference: str, hypothesis: str) -> float:
    ref = normalize(reference)
    hyp = normalize(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return _edit_distance(ref, hyp) / len(ref)


def _edit_distance(a: list[str], b: list[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, a_word in enumerate(a, start=1):
        current = [i]
        for j, b_word in enumerate(b, start=1):
            current.append(min(
                previous[j] + 1,                              # deletion
                current[j - 1] + 1,                           # insertion
                previous[j - 1] + (a_word != b_word),         # substitution
            ))
        previous = current
    return previous[-1]
