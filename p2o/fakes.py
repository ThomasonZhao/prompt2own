"""In-memory fakes for tests and `--fake` CLI runs. No Docker, no ground truth.

# STATUS: implemented
FakeWorker follows a script: per (stage, attempt) what to write. FakeHarness's run_poc
"crashes" iff the PoC bytes start with b"CRASH", and a patched build fixes it iff the
patch text contains "FIX". Purely synthetic; for exercising control flow only.
"""
from __future__ import annotations

import json
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


class FakeWorker:
    def __init__(self, script: dict | None = None, done: bool = True, usage: Usage | None = None):
        self.script = script or DEFAULT_SCRIPT
        self.done, self.usage = done, usage or Usage(tokens_in=10_000, tokens_out=1_000, tokens_cached=50_000)
        self.calls: list[tuple[str, int, str]] = []

    def run(self, ws, stage: Stage, attempt: int, prompt: str, artifact_dir: Path, prompt_hash: str) -> StageOutput:
        self.calls.append((stage.value, attempt, prompt))
        step = self.script.get((stage.value, attempt), {})
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
        return BuildResult(ok=True, image_or_container="FIX" if "FIX" in text else "nofix")

    def run_tests(self, task, build, timeout_s) -> TestResult:
        return TestResult(ok=True)
