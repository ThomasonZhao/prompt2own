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


def parse_usage(stdout: str) -> Usage:
    """Parse `claude -p --output-format json` output. VERIFY field names in M2 against the
    installed version (`claude --version`); keep this function the only place that knows them."""
    try:
        d = json.loads(stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return Usage()
    u = d.get("usage", {}) or {}
    return Usage(
        tokens_in=int(u.get("input_tokens", 0)) + int(u.get("cache_creation_input_tokens", 0)),
        tokens_cached=int(u.get("cache_read_input_tokens", 0)),
        tokens_out=int(u.get("output_tokens", 0)),
    )


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
            "P2O_MAX_TURNS": str(self.cfg.worker.max_turns),
            "DISABLE_TELEMETRY": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",   # model endpoint only (firewall rule)
        }

    def run(self, ws, stage, attempt, prompt, artifact_dir, prompt_hash) -> StageOutput:
        sub = f"{stage.value}/{attempt}"
        t0 = time.time()
        out = StageOutput(stage=stage, attempt=attempt, artifact_dir=artifact_dir, prompt_hash=prompt_hash)
        try:
            ex = self.h.exec_worker(ws, prompt, sub, self._env(), self.cfg.worker.stage_timeout_minutes * 60)
            self.h.copy_out(ws, f"/p2o/work/{sub}", artifact_dir)
            (artifact_dir / "worker_stdout.json").write_text(ex.stdout)
            out.usage, out.exit_code = parse_usage(ex.stdout), ex.exit_code
            if ex.timed_out:
                out.worker_error = "worker_timeout"
        except Exception as e:  # infrastructure failure inside a stage = rejected attempt
            out.worker_error = f"worker_error: {type(e).__name__}: {str(e)[:150]}"
        out.seconds = time.time() - t0
        if not out.worker_error:
            out.claim, out.rca, out.schema_error = parse_outputs(stage, artifact_dir)
        return out
