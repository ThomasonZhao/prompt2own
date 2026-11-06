"""Render stage prompt templates. # STATUS: implemented

Templates use {placeholders}: src_path, workspace, facts, last_reason, task_id.
Tune templates on dev tasks only. Any edit changes prompt_hash, which is logged per run.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .types import Stage


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def prompt_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def load(prompt_dir: str | Path, name: str) -> str:
    return (Path(prompt_dir) / name).read_text()


def render_stage(prompt_dir: str | Path, stage: Stage, *, task_id: str, src_path: str,
                 workspace: str, facts: str, last_reason: str | None) -> str:
    tmpl = load(prompt_dir, "common.md") + "\n" + load(prompt_dir, f"{stage.value}.md")
    retry = (f"\n## Previous attempt was rejected\nReason from the checker: {last_reason}\n"
             "Address this reason directly.\n") if last_reason else ""
    return tmpl.format_map(_Safe(task_id=task_id, src_path=src_path, workspace=workspace,
                                 facts=facts, last_reason=last_reason or "")) + retry


def render_single(prompt_dir: str | Path, base_prompt: str, suffix_name: str, workspace: str) -> str:
    return base_prompt + "\n\n" + load(prompt_dir, suffix_name).format_map(_Safe(workspace=workspace))
