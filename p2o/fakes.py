"""In-memory fakes for tests and `--fake` CLI runs. No Docker, no ground truth.

FakeWorker follows a script: per (stage, attempt) what to write. FakeHarness's run_poc
"crashes" iff the PoC bytes start with b"CRASH", and a patched build fixes it iff the
patch text contains "FIX", and its tests fail iff the patch contains "BREAKS".
Purely synthetic; for exercising control flow and the analysis pipeline only.

FakeWorker(vary=<salt>) draws a different script per (salt, task_id), deterministically,
so `p2o.cli batch --fake` yields a mix of outcomes across configs and tasks.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

from .types import (BuildResult, PoCRun, Stage, StageOutput, Task, TestResult, Usage,
                    WorkerExec, Workspace)
from .stage_io import parse_outputs

DEFAULT_SCRIPT = {
    ("rca", 1): {"rca": {"file": "src/a.c", "function": "parse", "line_range": [1, 9],
                         "bug_class": "heap-buffer-overflow", "rationale": "fake"}},
    ("poc", 1): {"poc": b"nope"},                      # rejected: no sanitizer report
    ("poc", 2): {"poc": b"CRASH-in-parse"},            # accepted
    ("patch", 1): {"patch": "--- a\n+++ b\n@@\n+FIX\n"},  # accepted
    ("single", 1): {"poc": b"CRASH", "patch": "--- a\n+++ b\n+FIX\n"},
}


_FIX, _BREAKS = "--- a\n+++ b\n+FIX\n", "--- a\n+++ b\n+FIX BREAKS\n"
_BADAPPLY, _NOFIX = "--- a\n+++ b\n+BADAPPLY\n", "--- a\n+++ b\n+nothing\n"


def varied_script(salt: str, task_id: str) -> dict:
    """A plausible random script for one (config, task): sometimes right, sometimes not."""
    r = random.Random(hashlib.sha256(f"{salt}|{task_id}".encode()).digest())
    good_rca = r.random() < 0.8
    sc: dict = {("rca", 1): {"rca": {"file": "src/a.c" if good_rca else "src/other.c",
                                     "function": "parse" if good_rca else "elsewhere",
                                     "line_range": [1, 9], "bug_class": "heap-buffer-overflow",
                                     "rationale": "fake"}}}
    skill = r.random()                     # per-task difficulty: low = hard
    for a in (1, 2, 3):
        x = r.random()
        if x < 0.05:
            sc[("poc", a)] = {"raise": True}
        else:
            sc[("poc", a)] = {"poc": b"CRASH-in-parse" if x < 0.05 + 0.7 * skill else b"nope",
                              "done": r.random() < 0.85}
        y = r.random()
        patch = (_FIX if y < 0.6 * skill else _BREAKS if y < 0.7 * skill + 0.05
                 else _BADAPPLY if y < 0.8 * skill + 0.1 else _NOFIX)
        sc[("patch", a)] = {"patch": patch, "done": r.random() < 0.85}
    sc[("single", 1)] = {"poc": b"CRASH" if r.random() < 0.6 * skill + 0.1 else b"nope",
                         "patch": _FIX if r.random() < 0.6 * skill else _NOFIX,
                         "done": r.random() < 0.8}
    return sc


class FakeWorker:
    def __init__(self, script: dict | None = None, done: bool = True, usage: Usage | None = None,
                 vary: str | None = None):
        self.script = script or DEFAULT_SCRIPT
        self.vary = vary
        self.done, self.usage = done, usage or Usage(tokens_in=10_000, tokens_out=1_000, tokens_cached=50_000)
        self.calls: list[tuple[str, int, str]] = []

    def run(self, ws, stage: Stage, attempt: int, prompt: str, artifact_dir: Path, prompt_hash: str) -> StageOutput:
        self.calls.append((stage.value, attempt, prompt))
        script = varied_script(self.vary, ws.task.task_id) if self.vary is not None else self.script
        step = script.get((stage.value, attempt), {})
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if step.get("raise"):
            return StageOutput(stage=stage, attempt=attempt, artifact_dir=artifact_dir,
                               worker_error="worker_error: scripted", usage=self.usage)
        if "rca" in step:
            (artifact_dir / "rca.json").write_text(json.dumps(step["rca"]))
        if "poc" in step:
            (artifact_dir / "poc.bin").write_bytes(step["poc"])
        if "patch" in step:
            (artifact_dir / "fix.patch").write_text(step["patch"])
        if not step.get("no_claim"):
            (artifact_dir / "claim.json").write_text(json.dumps(
                {"done": step.get("done", self.done), "confidence": 0.9}))
        claim, rca, err = parse_outputs(stage, artifact_dir)
        return StageOutput(stage=stage, attempt=attempt, artifact_dir=artifact_dir, claim=claim,
                           rca=rca, schema_error=err, usage=self.usage, seconds=0.01,
                           prompt_hash=prompt_hash)


class FakeHarness:
    def __init__(self):
        self.delivered: dict = {}

    def prepare_task(self, task: Task, run_dir: Path) -> Workspace:
        return Workspace(task=task, run_dir=run_dir, container_id="fake", src_path="/src")

    def exec_worker(self, ws, prompt, work_subdir, env, timeout_s) -> WorkerExec:
        raise NotImplementedError("FakeWorker does not use exec_worker")

    def copy_out(self, ws, container_path, host_dir) -> None:
        pass

    def official_prompt(self, task: Task) -> str:
        return f"[official e2e prompt for {task.task_id}]"

    def write_deliverables(self, ws, poc, patch) -> None:
        d = ws.run_dir / "deliverables"
        d.mkdir(parents=True, exist_ok=True)
        if poc:
            (d / "poc.bin").write_bytes(Path(poc).read_bytes())
        if patch:
            (d / "fix.patch").write_text(Path(patch).read_text())
        self.delivered[ws.task.task_id] = (poc, patch)

    def teardown(self, ws) -> None:
        pass

    def run_poc(self, task, poc_path: Path, build: BuildResult | None, timeout_s) -> PoCRun:
        data = Path(poc_path).read_bytes()
        fixed = build is not None and "FIX" in build.image_or_container
        if data.startswith(b"CRASH") and not fixed:
            return PoCRun(crashed=True, sanitizer_report="==1==ERROR: AddressSanitizer: heap-buffer-overflow",
                          top_frames=["#0 parse src/a.c:5", "#1 LLVMFuzzerTestOneInput"], exit_code=1)
        return PoCRun(crashed=False, exit_code=0)

    def apply_patch_and_build(self, task, patch_path: Path, timeout_s) -> BuildResult:
        text = Path(patch_path).read_text()
        if "BADAPPLY" in text:
            return BuildResult(ok=False, stage_failed="apply")
        tag = ("FIX" if "FIX" in text else "nofix") + ("+BREAKS" if "BREAKS" in text else "")
        return BuildResult(ok=True, image_or_container=tag)

    def run_tests(self, task, build, timeout_s) -> TestResult:
        if "BREAKS" in build.image_or_container:
            return TestResult(ok=False, failed=1, log_tail="FAIL: test_fake")
        return TestResult(ok=True)
