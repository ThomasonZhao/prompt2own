"""Wrap the official CyberGym-E2E grader. # STATUS: implemented (M0)

Runs only after a run has a run.json. Writes results/grades/<config>/<task>.json (+ .log).
NEVER modify the grader's logic; only call it and parse its output. The official entry point is
`run_agent.run_final_validation` (docs/HARNESS.md Q4): fresh container per stage, official
setup_workspace (with the ground-truth PoC, grader-side only), official validate.py.
"""
from __future__ import annotations

import contextlib
import time
from pathlib import Path

from .types import GradeRecord, Task


def grade_path(results_root: Path, config_id: str, task: Task) -> Path:
    return results_root / "grades" / config_id / (task.task_id.replace("/", "__") + ".json")


def official_grade(config_id: str, task: Task, run_dir: Path, log_path: Path | None = None,
                   harness_root: Path = Path("third_party/cybergym-e2e"),
                   data_root: Path = Path("data")) -> GradeRecord:
    """Call the official grading entry point on run_dir/deliverables and map it to S1..S4.

    Mirrors the official loop's short-circuits (run_agent.py:938-966): no PoC -> stage1 "no_poc", nothing
    graded. Unlike the official loop, a PoC without a patch is still graded for S1 (ARCHITECTURE §3);
    `raw.official_loop_s1` records S1 as the official loop would score it (False without a patch)."""
    from .harness import CyberGymE2EAdapter   # reuse task-config + harness import, no worker zone
    ad = CyberGymE2EAdapter(harness_root, data_root, use_firewall=False)
    d = run_dir / "deliverables"
    poc, patch = d / "poc.bin", d / "fix.patch"
    has_poc, has_patch = poc.exists(), patch.exists()
    t0 = time.time()
    if not has_poc:
        results = {"stage1": "no_poc", "stage2": "skipped", "stage3": "skipped", "stage4": "skipped"}
    else:
        log_path = log_path or (run_dir / "grade.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "w") as lf, contextlib.redirect_stdout(lf), contextlib.redirect_stderr(lf):
            results = ad.ra.run_final_validation(
                poc_path=poc.resolve(), patch_path=patch.resolve() if has_patch else None,
                data_path=ad.data_path(task), script_path=ad.script_path(task),
                build_image=ad.build_image(task), mode="e2e")
    s = {k: results.get(f"stage{k}") == "passed" for k in (1, 2, 3, 4)}
    return GradeRecord(config=config_id, task_id=task.task_id, s1=s[1], s2=s[2], s3=s[3], s4=s[4],
                       raw={"results": results, "has_poc": has_poc, "has_patch": has_patch,
                            "official_loop_s1": bool(s[1] and has_patch),
                            "grader": "run_agent.run_final_validation@d0ae0f0",
                            "seconds": round(time.time() - t0, 1)})


def grade(results_root: Path, config_id: str, task: Task, fake: bool = False) -> GradeRecord:
    run_dir = results_root / "runs" / config_id / task.task_id.replace("/", "__")
    if not (run_dir / "run.json").exists():
        raise FileNotFoundError(f"{run_dir} has no run.json; grade only finished runs")
    out = grade_path(results_root, config_id, task)
    if fake:  # synthetic grading for FakeHarness runs only
        d = run_dir / "deliverables"
        poc = d / "poc.bin"
        patch = d / "fix.patch"
        s1 = poc.exists() and poc.read_bytes().startswith(b"CRASH")
        s2 = s1 and patch.exists() and "FIX" in patch.read_text()
        rec = GradeRecord(config=config_id, task_id=task.task_id, s1=s1, s2=s2, s3=s2, s4=s2, raw={"fake": True})
    else:
        rec = official_grade(config_id, task, run_dir, log_path=out.with_suffix(".log"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rec.model_dump_json(indent=2))
    return rec
