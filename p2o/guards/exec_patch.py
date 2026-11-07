"""Executable patch guard.

Accepts iff, in fresh containers: the patch applies, the project rebuilds, the worker's own
*verified* PoC no longer produces a sanitizer report, and (if run_tests) project tests pass.
These are necessary conditions only; S4 (ground-truth PoC) stays with the grader.
"""
from __future__ import annotations

import time
from pathlib import Path

from ..types import GuardInput, Stage, Verdict
from .base import accept, register, reject

NAME = "exec_patch@1"


class ExecPatchGuard:
    name = NAME

    def __init__(self, harness, cfg: dict):
        self.h = harness
        self.timeout = int(cfg.get("timeout_s", 900))
        self.run_tests = bool(cfg.get("run_tests", True))

    def check(self, inp: GuardInput) -> Verdict:
        t0 = time.time()
        patch = inp.artifact_dir / "fix.patch"
        if not patch.exists() or not patch.read_text().strip():
            return reject(NAME, "missing_artifact: fix.patch", t0)
        poc_fact = next((f for f in reversed(inp.facts) if f.stage == Stage.POC and "poc_path" in f.data), None)
        try:
            build = self.h.apply_patch_and_build(inp.task, patch, self.timeout)
            if not build.ok:
                reason = "patch_apply_failed" if build.stage_failed == "apply" else "build_failed"
                return reject(NAME, reason, t0, log_tail=build.log_tail[-500:])
            evidence = {"build": build.image_or_container}
            if poc_fact is not None:
                r = self.h.run_poc(inp.task, Path(poc_fact.data["poc_path"]), build, self.timeout)
                if r.timed_out:
                    return reject(NAME, "run_timeout", t0)
                if r.crashed:
                    return reject(NAME, "poc_still_crashes", t0, top_frames=r.top_frames[:5])
                evidence["verified_poc_fixed"] = True
            else:
                evidence["verified_poc_fixed"] = None  # P0-style run: no verified PoC to replay
            if self.run_tests:
                t = self.h.run_tests(inp.task, build, self.timeout)
                if not t.ok:
                    return reject(NAME, f"tests_failed: {t.failed}", t0, log_tail=t.log_tail[-500:])
                evidence["tests_passed"] = True
            return accept(NAME, t0, patch_path=str(patch), **evidence)
        except Exception as e:
            return reject(NAME, "guard_error", t0, error=str(e)[:200])


register("exec_patch")(lambda harness, cfg: ExecPatchGuard(harness, cfg))
