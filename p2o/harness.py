"""Everything Docker- and CyberGym-E2E-specific lives behind HarnessAdapter.

# STATUS: Protocol final; CyberGymE2EAdapter is a stub filled in M0 / M2 / M3.
Read docs/HARNESS.md first and reuse the official harness's own commands.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .types import BuildResult, PoCRun, Task, TestResult, WorkerExec, Workspace


class HarnessAdapter(Protocol):
    # ----- worker zone -----
    def prepare_task(self, task: Task, run_dir: Path) -> Workspace:
        """Start the task container from the *vulnerable* image, run leak cleanup
        (docs/HARNESS.md "Leak cleanup"), attach the firewall, return a Workspace."""

    def exec_worker(self, ws: Workspace, prompt: str, work_subdir: str,
                    env: dict[str, str], timeout_s: int) -> WorkerExec:
        """Write prompt to <container>/p2o/work/<work_subdir>/prompt.md and run headless
        Claude Code there with cwd = ws.src_path. Return its stdout (JSON)."""

    def copy_out(self, ws: Workspace, container_path: str, host_dir: Path) -> None:
        """Copy a container directory to host_dir (created if missing)."""

    def official_prompt(self, task: Task) -> str:
        """The harness's own e2e task prompt for this task (used verbatim by B1, wrapped by B2)."""

    def write_deliverables(self, ws: Workspace, poc: Path | None, patch: Path | None) -> None:
        """Place poc.bin / fix.patch where the official grader reads them, and also
        copy them to ws.run_dir/deliverables/. If poc/patch is None (single-session runs
        write them where the official prompt says), collect them from those container paths."""

    def teardown(self, ws: Workspace) -> None: ...

    # ----- guard zone: every call uses a FRESH container from the vulnerable image -----
    def run_poc(self, task: Task, poc_path: Path, build: BuildResult | None,
                timeout_s: int) -> PoCRun:
        """Run the candidate input through the task's fuzz target using the harness's own
        reproduce command. build=None -> original vulnerable build; otherwise the patched
        build returned by apply_patch_and_build. Parse sanitizer report + top frames."""

    def apply_patch_and_build(self, task: Task, patch_path: Path, timeout_s: int) -> BuildResult:
        """Fresh container: apply patch (git apply), rebuild with the harness's build command.
        Keep the container/image so run_poc / run_tests can use it; record it in the result."""

    def run_tests(self, task: Task, build: BuildResult, timeout_s: int) -> TestResult:
        """Run the project's test command (as the harness's S3 check does) on the patched build."""


class CyberGymE2EAdapter:
    """Real adapter. Fill in during M0 (prepare_task, write_deliverables),
    M2 (exec_worker, copy_out, teardown) and M3 (run_poc, apply_patch_and_build, run_tests)."""

    def __init__(self, harness_root: Path = Path("third_party/cybergym-e2e"), data_root: Path = Path("data")):
        self.harness_root, self.data_root = harness_root, data_root

    def prepare_task(self, task: Task, run_dir: Path) -> Workspace:
        raise NotImplementedError("M0/M2: see docs/HARNESS.md questions 1, 6, 7")

    def exec_worker(self, ws, prompt, work_subdir, env, timeout_s) -> WorkerExec:
        raise NotImplementedError("M2: see docs/HARNESS.md question 1")

    def copy_out(self, ws, container_path, host_dir) -> None:
        raise NotImplementedError("M2: docker cp")

    def official_prompt(self, task) -> str:
        raise NotImplementedError("M0: see docs/HARNESS.md question 1")

    def write_deliverables(self, ws, poc, patch) -> None:
        raise NotImplementedError("M0: see docs/HARNESS.md question 3")

    def teardown(self, ws) -> None:
        raise NotImplementedError("M2")

    def run_poc(self, task, poc_path, build, timeout_s) -> PoCRun:
        raise NotImplementedError("M3: see docs/HARNESS.md question 5b")

    def apply_patch_and_build(self, task, patch_path, timeout_s) -> BuildResult:
        raise NotImplementedError("M3: see docs/HARNESS.md question 5a")

    def run_tests(self, task, build, timeout_s) -> TestResult:
        raise NotImplementedError("M3: see docs/HARNESS.md question 5c")
