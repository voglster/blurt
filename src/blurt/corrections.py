from __future__ import annotations

import re
from pathlib import Path

import yaml


class Corrections:
    def __init__(self, rules: list[tuple[str, str]]) -> None:
        self._rules = [(re.compile(p), r) for p, r in rules]

    def apply(self, text: str) -> str:
        for pat, repl in self._rules:
            text = pat.sub(repl, text)
        return text


def load(path: Path) -> Corrections:
    if not path.exists():
        return Corrections([])
    with path.open() as f:
        data = yaml.safe_load(f) or []
    rules = [(item["pattern"], item["replacement"]) for item in data]
    return Corrections(rules)
