"""Workers: one fresh headless Claude Code session per call.

# STATUS: Protocol final; ClaudeCodeWorker logic written, verify flags + usage parsing in M2.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Protocol

from .config import RunConfig
from .harness import HarnessAdapter
from .stage_io import parse_outputs
from .types import Stage, StageOutput, Usage, Workspace


class Worker(Protocol):
    def run(self, ws: Workspace, stage: Stage, attempt: int, prompt: str,
            artifact_dir: Path, prompt_hash: str) -> StageOutput:
        """Run one session. Must copy the worker's stage workspace to artifact_dir and
        return parsed outputs. Never raises for agent-side failures: set worker_error."""


def _to_usage(u: dict) -> Usage:
    return Usage(
        tokens_in=int(u.get("input_tokens", 0) or 0) + int(u.get("cache_creation_input_tokens", 0) or 0),
        tokens_cached=int(u.get("cache_read_input_tokens", 0) or 0),
        tokens_out=int(u.get("output_tokens", 0) or 0),
    )


def parse_stream(stdout: str) -> tuple[Usage, dict | None, str | None]:
    """Parse `claude -p --output-format stream-json --verbose` output (Claude Code 2.1.x, as launched
    by the official harness). Returns (usage, result_event, cap_reason).

    Usage: the final `result` event's `usage` (session total) when present; otherwise (session killed
    by timeout / token cap) the sum of per-request `assistant` usages, de-duplicated by message id
    (one API response is streamed as several assistant events sharing an id). This function is the
    only place that knows these field names."""
    per_msg: dict[str, dict] = {}
    result, cap = None, None
    for i, line in enumerate(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = d.get("type")
        if t == "assistant":
            msg = d.get("message") or {}
            if msg.get("usage"):
                per_msg[msg.get("id") or f"_{i}"] = msg["usage"]
        elif t == "result":
            result = d
        elif t == "p2o_cap":
            cap = d.get("reason")
    if result is not None and result.get("usage"):
        return _to_usage(result["usage"]), result, cap
    total = Usage()
    for u in per_msg.values():
        total = total + _to_usage(u)
    return total, result, cap


def parse_usage(stdout: str) -> Usage:
    return parse_stream(stdout)[0]


API_KEY_ENV = "OPENROUTER_API_KEY"

# Every model alias Claude Code may resolve on its own (background/small-fast calls, subagents,
# /model shortcuts). On OpenRouter an unpinned "claude-*" default can hit a real Anthropic model,
# which would mix models within a run and bill at Anthropic rates, so all of them = cfg.model.
_MODEL_VARS = ("ANTHROPIC_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
               "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL",
               "CLAUDE_CODE_SUBAGENT_MODEL")


class ClaudeCodeWorker:
    def __init__(self, harness: HarnessAdapter, cfg: RunConfig):
        if not os.environ.get(API_KEY_ENV):
            raise RuntimeError(f"{API_KEY_ENV} is not set (see .env.example)")
        self.h, self.cfg = harness, cfg

    def _env(self) -> dict[str, str]:
        return {
            "ANTHROPIC_BASE_URL": self.cfg.base_url,
            "ANTHROPIC_AUTH_TOKEN": os.environ[API_KEY_ENV],
            "ANTHROPIC_API_KEY": "",   # must be empty, else Claude Code may prefer it over the token
            **{k: self.cfg.model for k in _MODEL_VARS},
            "P2O_MAX_TURNS": str(self.cfg.worker.max_turns),   # adapter controls, not sent to container
            "P2O_TOKEN_CAP": str(self.cfg.caps.max_tokens),
            "DISABLE_TELEMETRY": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",   # model endpoint only (firewall rule)
        }

    def run(self, ws, stage, attempt, prompt, artifact_dir, prompt_hash) -> StageOutput:
        sub = f"{stage.value}/{attempt}"
        t0 = time.time()
        out = StageOutput(stage=stage, attempt=attempt, artifact_dir=artifact_dir, prompt_hash=prompt_hash)
        # single-session runs (B1/B2) get the whole run's wall clock; stages get the stage timeout
        timeout_s = (self.cfg.caps.wall_minutes if stage == Stage.SINGLE
                     else self.cfg.worker.stage_timeout_minutes) * 60
        try:
            ex = self.h.exec_worker(ws, prompt, sub, self._env(), timeout_s)
            self.h.copy_out(ws, f"/p2o/work/{sub}", artifact_dir)
            (artifact_dir / "worker_stdout.json").write_text(ex.stdout)
            usage, result, cap = parse_stream(ex.stdout)
            out.usage, out.exit_code = usage, ex.exit_code
            if cap:
                out.worker_error = cap
            elif ex.timed_out:
                out.worker_error = "worker_timeout"
            elif result is None and ex.exit_code != 0:
                out.worker_error = f"worker_error: exit {ex.exit_code}: {ex.stdout.strip()[-150:]}"
        except Exception as e:  # infrastructure failure inside a stage = rejected attempt
            out.worker_error = f"worker_error: {type(e).__name__}: {str(e)[:150]}"
        out.seconds = time.time() - t0
        # parse even after a timeout/cap: claimed_success is whatever the worker last wrote.
        # The orchestrator still rejects any attempt that has a worker_error.
        out.claim, out.rca, out.schema_error = parse_outputs(stage, artifact_dir)
        return out
