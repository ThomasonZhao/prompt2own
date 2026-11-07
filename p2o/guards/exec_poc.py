"""Executable PoC guard.

Accepts iff, in a fresh vulnerable container, the candidate input produces a sanitizer
report AND (if require_location_match) one of the top-k frames matches the RCA's claimed
function or file. Uses only the worker's own artifacts and verified facts.
"""
from __future__ import annotations

import re
import time
from pathlib import PurePosixPath

from ..types import GuardInput, Stage, Verdict
from .base import accept, register, reject

NAME = "exec_poc@1"
_SAN = re.compile(r"ERROR: (\w+Sanitizer): ([\w-]+)")


def crash_type(report: str | None) -> str | None:
    m = _SAN.search(report or "")
    return f"{m.group(1)}:{m.group(2)}" if m else None


def location_matches(frames: list[str], function: str | None, file: str | None) -> bool:
    keys = [k for k in [function, PurePosixPath(file).name if file else None] if k]
    return any(k in fr for fr in frames for k in keys)


class ExecPoCGuard:
    name = NAME

    def __init__(self, harness, cfg: dict):
        self.h = harness
        self.timeout = int(cfg.get("timeout_s", 300))
        self.require_match = bool(cfg.get("require_location_match", True))
        self.k = int(cfg.get("top_k_frames", 5))

    def check(self, inp: GuardInput) -> Verdict:
        t0 = time.time()
        poc = inp.artifact_dir / "poc.bin"
        if not poc.exists():
            return reject(NAME, "missing_artifact: poc.bin", t0)
        try:
            r = self.h.run_poc(inp.task, poc, None, self.timeout)
        except Exception as e:
            return reject(NAME, "guard_error", t0, error=str(e)[:200])
        if r.timed_out:
            return reject(NAME, "run_timeout", t0)
        if not r.crashed or not r.sanitizer_report:
            return reject(NAME, "no_sanitizer_report", t0, exit_code=r.exit_code)
        frames = r.top_frames[: self.k]
        rca = next((f.data for f in reversed(inp.facts) if f.stage == Stage.RCA), {})
        claimed_fn, claimed_file = rca.get("function"), rca.get("file")
        matches = location_matches(frames, claimed_fn, claimed_file)
        if self.require_match and rca and not matches:
            got = frames[0] if frames else "?"
            return reject(NAME, f"crash_location_mismatch: got {got}, claimed {claimed_fn}", t0,
                          top_frames=frames, crash_type=crash_type(r.sanitizer_report))
        return accept(NAME, t0, poc_path=str(poc), crash_type=crash_type(r.sanitizer_report),
                      top_frames=frames, matches_rca=matches)


register("exec_poc")(lambda harness, cfg: ExecPoCGuard(harness, cfg))
