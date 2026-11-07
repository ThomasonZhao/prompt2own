"""Append-only evidence ledger and event log.

Only the orchestrator writes these. Workers see a rendering of Ledger.facts() in their prompt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .types import Fact, now


def _append(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, default=str) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


class Ledger:
    def __init__(self, run_dir: Path):
        self.path = run_dir / "ledger.jsonl"
        self._facts = [Fact(**d) for d in read_jsonl(self.path)]

    def append(self, fact: Fact) -> None:
        _append(self.path, fact.model_dump(mode="json"))
        self._facts.append(fact)

    def facts(self) -> list[Fact]:
        return list(self._facts)

    def render(self) -> str:
        """Plain-text view for worker prompts."""
        if not self._facts:
            return "(no verified facts yet)"
        lines = []
        for f in self._facts:
            lines.append(f"- [{f.stage.value}, verified by {f.guard}] " + json.dumps(f.data, default=str))
        return "\n".join(lines)


class EventLog:
    def __init__(self, run_dir: Path, base: dict[str, Any]):
        self.path = run_dir / "events.jsonl"
        self.base = base

    def emit(self, event: str, **fields: Any) -> None:
        _append(self.path, {"ts": now(), "event": event, **self.base, **fields})

    def has_run_end(self) -> bool:
        return any(e.get("event") == "run_end" for e in read_jsonl(self.path))
