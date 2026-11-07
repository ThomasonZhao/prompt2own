"""Run lifecycle: caps, worker errors, resume; plus regressions for claimed_success / guard verdict bookkeeping."""
import json
import os
import shutil
import time

from typer.testing import CliRunner

from p2o.cli import app
from p2o.config import Caps
from p2o.fakes import FakeWorker
from p2o.ledger import read_jsonl
from p2o.types import Task, Usage

T = Task(task_id="proj/arvo_1", project="proj")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = "--- a\n+++ b\n+FIX\n"


def events(orch):
    return read_jsonl(orch.run_dir(T) / "events.jsonl")


def attempts(orch, stage=None):
    return [e for e in events(orch) if e["event"] == "stage_attempt" and (stage is None or e["stage"] == stage)]


# ---------------------------------------------------------------- caps

def test_cap_hit_stops_the_run(make):
    # rca attempt alone exceeds the token cap -> cap is checked before poc#1 -> nothing else runs
    w = FakeWorker(usage=Usage(tokens_in=10_000_000))
    orch, h, _ = make("configs/p3.yaml", worker=w)
    orch.cfg.caps = Caps(wall_minutes=45, max_tokens=1_000, max_usd=100)
    rec = orch.run(T)
    ev = events(orch)
    names = [e["event"] for e in ev]
    assert [c[:2] for c in w.calls] == [("rca", 1)]
    i = names.index("cap_hit")
    assert i > names.index("stage_attempt")
    assert "stage_attempt" not in names[i:]
    assert ev[i]["stage"] == "poc" and ev[i]["cap"] == "cap_tokens"
    assert rec.status == "cap_hit" and rec.failed_at.value == "poc" and not rec.claimed_success
    assert names[-1] == "run_end" and ev[-1]["status"] == "cap_hit"
    assert orch.is_done(T)                    # a capped run is finished: not retried on resume
    assert T.task_id in h.delivered           # partial deliverables are still written


def test_usd_cap(make):
    orch, _, w = make("configs/p3.yaml", worker=FakeWorker(usage=Usage(tokens_out=10_000_000)))
    orch.cfg.caps = Caps(wall_minutes=45, max_tokens=10**12, max_usd=0.01)
    rec = orch.run(T)
    assert rec.status == "cap_hit" and rec.stop_reason == "cap_usd" and len(w.calls) == 1


def test_wall_cap(make, monkeypatch):
    orch, _, w = make("configs/p3.yaml")
    orch.cfg.caps = Caps(wall_minutes=1, max_tokens=10**12, max_usd=100)
    t0 = time.time()
    # every worker call "takes" 40 s of wall clock
    monkeypatch.setattr("p2o.orchestrator.time.time", lambda: t0 + 40 * len(w.calls))
    rec = orch.run(T)
    assert rec.stop_reason == "cap_wall_time" and [c[:2] for c in w.calls] == [("rca", 1), ("poc", 1)]
    assert rec.failed_at.value == "poc"


# ---------------------------------------------------------------- worker errors

def test_worker_error_counts_as_rejection(make):
    script = dict(FakeWorker().script)
    script[("poc", 1)] = {"raise": True}
    script[("poc", 2)] = {"poc": b"CRASH-in-parse"}
    orch, _, w = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    poc = attempts(orch, "poc")
    assert [p["verdict"]["accept"] for p in poc] == [False, True]
    assert poc[0]["worker_error"].startswith("worker_error")
    assert poc[0]["verdict"]["guard"] == "orchestrator"
    # the error is fed to the next attempt like any rejection reason, and it uses up an attempt
    assert "worker_error" in [p for s, a, p in w.calls if (s, a) == ("poc", 2)][0]
    assert rec.attempts["poc"] == 2 and rec.claimed_success
    # the guard was only reached once
    assert rec.guard_counts["exec_poc@1"] == {"accept": 1, "reject": 0}
    assert rec.guard_counts["orchestrator"] == {"accept": 0, "reject": 1}


def test_worker_error_on_every_attempt_exhausts_stage(make):
    script = dict(FakeWorker().script)
    for a in (1, 2, 3):
        script[("poc", a)] = {"raise": True}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    assert rec.status == "failed" and rec.failed_at.value == "poc" and rec.stop_reason == "attempts_exhausted"
    assert "poc" not in rec.final_guard_accept   # guard never reached -> no guard verdict recorded


def test_final_guard_verdict_ignores_later_orchestrator_rejection(make):
    script = dict(FakeWorker().script)
    script[("poc", 1)] = {"poc": b"nope"}       # guard rejects
    script[("poc", 2)] = {"no_claim": True, "poc": b"x"}  # schema error, guard not called
    script[("poc", 3)] = {"raise": True}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    assert rec.final_guard_accept == {"rca": True, "poc": False}
    assert rec.guard_counts["exec_poc@1"] == {"accept": 0, "reject": 1}


# ---------------------------------------------------------------- claimed_success (FSR input)

def test_poc_claim_does_not_count_as_patch_claim(make):
    script = dict(FakeWorker().script)
    for a in (1, 2, 3):
        script[("patch", a)] = {"raise": True}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    assert rec.failed_at.value == "patch" and not rec.claimed_success


def test_cap_before_first_patch_attempt_is_not_a_claim(make):
    orch, _, w = make("configs/p3.yaml")
    per_call = FakeWorker().usage.total
    orch.cfg.caps = Caps(wall_minutes=45, max_tokens=3 * per_call - 1, max_usd=100)  # rca, poc1, poc2
    rec = orch.run(T)
    assert [c[:2] for c in w.calls] == [("rca", 1), ("poc", 1), ("poc", 2)]
    assert rec.status == "cap_hit" and rec.failed_at.value == "patch" and not rec.claimed_success


def test_patch_done_false_is_not_claimed(make):
    script = dict(FakeWorker().script)
    script[("patch", 1)] = {"patch": FIX, "done": False}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    assert rec.stop_reason == "completed" and rec.status == "failed" and not rec.claimed_success


def test_rejected_patch_with_done_true_is_claimed(make):
    # FSR counts what the worker *said*, independent of guard verdicts
    script = dict(FakeWorker().script)
    for a in (1, 2, 3):
        script[("patch", a)] = {"patch": "--- a\n+++ b\n+nothing\n"}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    assert rec.stop_reason == "attempts_exhausted" and rec.claimed_success


# ---------------------------------------------------------------- resume + CLI isolation

def _cli(*args):
    r = CliRunner().invoke(app, list(args))
    assert r.exit_code == 0, r.output
    return r.output


def test_resume_skips_finished_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(REPO)
    tasks = tmp_path / "tasks.txt"
    tasks.write_text("demo/fake_1,demo\ndemo/fake_2,demo\n")
    root = tmp_path / "res"
    args = ["batch", "--config", "configs/p3.yaml", "--tasks", str(tasks), "--fake",
            "--results", str(root), "--parallel", "2"]
    assert "2 tasks to run" in _cli(*args)
    runs = root / "runs" / "p3"
    run_ids = {d.name: json.loads((d / "run.json").read_text())["run_id"] for d in runs.iterdir()}
    spent = json.loads((root / "budget.json").read_text())["spent"]
    # an unfinished run (events but no run.json) is restarted; finished runs are left alone
    (runs / "demo__fake_3").mkdir()
    (runs / "demo__fake_3" / "events.jsonl").write_text(json.dumps({"event": "run_start"}) + "\n")
    tasks.write_text("demo/fake_1,demo\ndemo/fake_2,demo\ndemo/fake_3,demo\n")
    out = _cli(*args)
    assert "1 tasks to run" in out and "[done] demo/fake_3" in out and "demo/fake_1" not in out
    for d, rid in run_ids.items():
        assert json.loads((runs / d / "run.json").read_text())["run_id"] == rid
    ev = read_jsonl(runs / "demo__fake_3" / "events.jsonl")
    assert [e["event"] for e in ev].count("run_start") == 1 and ev[-1]["event"] == "run_end"
    assert json.loads((root / "budget.json").read_text())["spent"] > spent
    assert "0 tasks to run" in _cli(*args)


def test_fake_cli_never_touches_real_results(tmp_path, monkeypatch):
    shutil.copytree(os.path.join(REPO, "configs"), tmp_path / "configs")
    shutil.copytree(os.path.join(REPO, "p2o", "stages"), tmp_path / "p2o" / "stages")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("P2O_BUDGET_FILE", raising=False)
    _cli("run", "--config", "configs/p3.yaml", "--task", "FAKE", "--fake")
    (tmp_path / "t.txt").write_text("FAKE\n")
    _cli("grade", "--config", "configs/p3.yaml", "--tasks", "t.txt", "--fake")
    assert (tmp_path / "results/fake/runs/p3/FAKE/run.json").exists()
    assert (tmp_path / "results/fake/grades/p3/FAKE.json").exists()
    assert (tmp_path / "results/fake/budget.json").exists()
    assert sorted(p.name for p in (tmp_path / "results").iterdir()) == ["fake"]
    r = CliRunner().invoke(app, ["run", "--config", "configs/p3.yaml", "--task", "FAKE", "--fake",
                                 "--results", "results"])
    assert r.exit_code != 0
    assert sorted(p.name for p in (tmp_path / "results").iterdir()) == ["fake"]


def test_cli_reject_retry_accept(tmp_path, monkeypatch):
    # end-to-end CLI run on the fake harness, with an isolated results root
    monkeypatch.chdir(REPO)
    _cli("run", "--config", "configs/p3.yaml", "--task", "FAKE", "--fake", "--results", str(tmp_path))
    ev = read_jsonl(tmp_path / "runs" / "p3" / "FAKE" / "events.jsonl")
    seq = [(e["stage"], e["attempt"], e["verdict"]["accept"]) for e in ev if e["event"] == "stage_attempt"]
    assert ("poc", 1, False) in seq and ("poc", 2, True) in seq
    assert seq.index(("poc", 1, False)) + 1 == seq.index(("poc", 2, True))


def test_run_start_records_hashes(make):
    orch, _, _ = make("configs/p3.yaml")
    rec = orch.run(T)
    start = events(orch)[0]
    assert start["event"] == "run_start" and start["config_hash"] == rec.config_hash
    assert len(start["templates_hash"]) == 12 and rec.prompt_hash and rec.model and rec.provider


def test_varied_fake_worker_is_deterministic_and_mixed():
    from p2o.fakes import varied_script
    assert varied_script("p3", "a/1") == varied_script("p3", "a/1")
    outs = {varied_script("p3", f"a/{i}")[("patch", 1)]["patch"] for i in range(40)}
    assert len(outs) >= 3
