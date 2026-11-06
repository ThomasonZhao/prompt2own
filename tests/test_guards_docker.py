"""M3 acceptance: real guards against a dev task. Run on the VM: pytest -q -m docker tests/test_guards_docker.py

Positive control uses the dev task's ground-truth PoC (test-only; this file must never be
imported by p2o/). Dev task: libspng/arvo_14935 (easy stratum, default base-builder image).
Skips only when the environment is missing (Docker, dataset files, harness clone); an
unimplemented adapter method fails, it does not skip.
Env overrides: P2O_HARNESS_ROOT (default third_party/cybergym-e2e), P2O_DATA_ROOT (default data).
"""
import os
import shutil
from pathlib import Path

import pytest

from p2o.guards.exec_patch import ExecPatchGuard
from p2o.guards.exec_poc import ExecPoCGuard
from p2o.types import Claim, Fact, GuardInput, Stage, Task

pytestmark = pytest.mark.docker

REPO = Path(__file__).resolve().parent.parent
HARNESS = Path(os.environ.get("P2O_HARNESS_ROOT", REPO / "third_party" / "cybergym-e2e"))
DATA = Path(os.environ.get("P2O_DATA_ROOT", REPO / "data"))
TASK = Task(task_id="libspng/arvo_14935", project="libspng")
GT_POC = DATA / "projects" / TASK.task_id / "poc.bin"       # ground truth: test-only positive control
POC_TIMEOUT, BUILD_TIMEOUT = 600, 1800


@pytest.fixture(scope="module")
def adapter():
    if shutil.which("docker") is None:
        pytest.skip("docker not installed")
    for p, what in ((HARNESS, "harness clone"), (GT_POC, "dev task data (scripts/fetch_sampled.py)")):
        if not p.exists():
            pytest.skip(f"missing {what}: {p}")
    from p2o.harness import CyberGymE2EAdapter
    return CyberGymE2EAdapter(harness_root=HARNESS, data_root=DATA, use_firewall=False)


def _inp(tmp_path: Path, stage: Stage, files: dict[str, bytes], facts=()) -> GuardInput:
    art = tmp_path / stage.value / "1"
    art.mkdir(parents=True)
    for name, data in files.items():
        (art / name).write_bytes(data)
    return GuardInput(task=TASK, stage=stage, attempt=1, artifact_dir=art,
                      claim=Claim(done=True, confidence=0.5), facts=list(facts))


def _poc_guard(adapter, match=False):
    return ExecPoCGuard(adapter, {"timeout_s": POC_TIMEOUT, "require_location_match": match, "top_k_frames": 5})


# ---------------------------------------------------------------- adapter level

def test_run_poc_ground_truth_crashes(adapter):
    r = adapter.run_poc(TASK, GT_POC, None, POC_TIMEOUT)
    assert not r.timed_out
    assert r.crashed, f"exit={r.exit_code}"
    assert r.sanitizer_report and "Sanitizer" in r.sanitizer_report
    assert r.top_frames, "no stack frames parsed from the sanitizer report"


def test_run_poc_empty_input_does_not_crash(adapter, tmp_path):
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    r = adapter.run_poc(TASK, empty, None, POC_TIMEOUT)
    assert not r.timed_out and not r.crashed and not r.sanitizer_report


def test_run_poc_does_not_alter_the_candidate(adapter, tmp_path):
    p = tmp_path / "poc.bin"
    p.write_bytes(GT_POC.read_bytes())
    adapter.run_poc(TASK, p, None, POC_TIMEOUT)
    assert p.read_bytes() == GT_POC.read_bytes()


# ---------------------------------------------------------------- exec_poc guard

def test_exec_poc_accepts_ground_truth_poc(adapter, tmp_path):
    v = _poc_guard(adapter).check(_inp(tmp_path, Stage.POC, {"poc.bin": GT_POC.read_bytes()}))
    assert v.accept, v.reason
    assert v.evidence["crash_type"] and v.evidence["top_frames"]


def test_exec_poc_rejects_empty_file(adapter, tmp_path):
    v = _poc_guard(adapter).check(_inp(tmp_path, Stage.POC, {"poc.bin": b""}))
    assert not v.accept and v.reason == "no_sanitizer_report"


def test_exec_poc_location_mismatch_against_wrong_rca(adapter, tmp_path):
    rca = Fact(stage=Stage.RCA, attempt=1, guard="null@1",
               data={"file": "src/definitely_not_here.c", "function": "p2o_no_such_function"})
    v = _poc_guard(adapter, match=True).check(
        _inp(tmp_path, Stage.POC, {"poc.bin": GT_POC.read_bytes()}, facts=[rca]))
    assert not v.accept and v.reason.startswith("crash_location_mismatch")


# ---------------------------------------------------------------- exec_patch guard

def _patch_guard(adapter, tests=False):
    return ExecPatchGuard(adapter, {"timeout_s": BUILD_TIMEOUT, "run_tests": tests})


def test_exec_patch_rejects_empty_patch(adapter, tmp_path):
    v = _patch_guard(adapter).check(_inp(tmp_path, Stage.PATCH, {"fix.patch": b""}))
    assert not v.accept and v.reason.startswith("missing_artifact")


def test_exec_patch_rejects_patch_that_does_not_apply(adapter, tmp_path):
    bad = (b"--- a/p2o_no_such_file.c\n+++ b/p2o_no_such_file.c\n@@ -1,1 +1,1 @@\n"
           b"-this line does not exist\n+neither does this one\n")
    v = _patch_guard(adapter).check(_inp(tmp_path, Stage.PATCH, {"fix.patch": bad}))
    assert not v.accept and v.reason == "patch_apply_failed", (v.reason, v.evidence)


def test_apply_patch_and_build_reports_apply_failure(adapter, tmp_path):
    bad = tmp_path / "bad.patch"
    bad.write_text("--- a/p2o_no_such_file.c\n+++ b/p2o_no_such_file.c\n@@ -1 +1 @@\n-x\n+y\n")
    b = adapter.apply_patch_and_build(TASK, bad, BUILD_TIMEOUT)
    assert not b.ok and b.stage_failed == "apply"
