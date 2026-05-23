from __future__ import annotations


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
