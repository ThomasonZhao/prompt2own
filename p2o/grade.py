"""Wrap the official CyberGym-E2E grader. # STATUS: stub (M0)

Runs only after a run has a run.json. Writes results/grades/<config>/<task>.json.
NEVER modify the grader's logic; only call it and parse its output.
"""
from __future__ import annotations

from pathlib import Path

from .types import GradeRecord, Task


def grade_path(results_root: Path, config_id: str, task: Task) -> Path:
    return results_root / "grades" / config_id / (task.task_id.replace("/", "__") + ".json")


def official_grade(config_id: str, task: Task, run_dir: Path) -> GradeRecord:
    """Call the official grading entry point (docs/HARNESS.md question 4) on the
    deliverables of run_dir and map its output to S1..S4. Keep the raw output in `raw`."""
    raise NotImplementedError("M0: see docs/HARNESS.md question 4")


def grade(results_root: Path, config_id: str, task: Task, fake: bool = False) -> GradeRecord:
    run_dir = results_root / "runs" / config_id / task.task_id.replace("/", "__")
    if not (run_dir / "run.json").exists():
        raise FileNotFoundError(f"{run_dir} has no run.json; grade only finished runs")
    if fake:  # synthetic grading for FakeHarness runs only
        d = run_dir / "deliverables"
        poc = d / "poc.bin"
        patch = d / "fix.patch"
        s1 = poc.exists() and poc.read_bytes().startswith(b"CRASH")
        s2 = s1 and patch.exists() and "FIX" in patch.read_text()
        rec = GradeRecord(config=config_id, task_id=task.task_id, s1=s1, s2=s2, s3=s2, s4=s2, raw={"fake": True})
    else:
        rec = official_grade(config_id, task, run_dir)
    out = grade_path(results_root, config_id, task)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rec.model_dump_json(indent=2))
    return rec
