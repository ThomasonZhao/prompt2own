import json

from p2o.config import Caps
from p2o.fakes import FakeWorker
from p2o.ledger import read_jsonl
from p2o.types import Task, Usage

T = Task(task_id="proj/arvo_1", project="proj")


def events(orch):
    return read_jsonl(orch.run_dir(T) / "events.jsonl")


def test_p3_reject_retry_accept(make):
    orch, h, w = make("configs/p3.yaml")
    rec = orch.run(T)
    assert rec.status == "success_claimed" and rec.claimed_success
    att = [(e["stage"], e["attempt"], e["verdict"]["accept"]) for e in events(orch) if e["event"] == "stage_attempt"]
    assert att == [("rca", 1, True), ("poc", 1, False), ("poc", 2, True), ("patch", 1, True)]
    # rejection reason is fed to the next attempt
    poc2_prompt = [p for s, a, p in w.calls if s == "poc" and a == 2][0]
    assert "no_sanitizer_report" in poc2_prompt
    # ledger holds only accepted facts
    facts = read_jsonl(orch.run_dir(T) / "ledger.jsonl")
    assert [f["stage"] for f in facts] == ["rca", "poc", "patch"]
    assert (orch.run_dir(T) / "deliverables" / "poc.bin").read_bytes().startswith(b"CRASH")


def test_p0_accepts_first_attempt_without_checking(make):
    orch, _, _ = make("configs/p0.yaml")
    rec = orch.run(T)
    att = [(e["stage"], e["verdict"]["guard"]) for e in events(orch) if e["event"] == "stage_attempt"]
    assert att == [("rca", "null@1"), ("poc", "null@1"), ("patch", "null@1")]
    assert rec.claimed_success  # claimed, although the fake PoC would not crash -> false success


def test_attempts_exhausted_stops_run(make):
    script = {("rca", 1): FakeWorker().script[("rca", 1)],
              ("poc", 1): {"poc": b"x"}, ("poc", 2): {"poc": b"y"}, ("poc", 3): {"poc": b"z"}}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    assert rec.status == "failed" and rec.failed_at.value == "poc" and rec.stop_reason == "attempts_exhausted"
    assert not rec.claimed_success


def test_location_mismatch_rejected(make):
    script = dict(FakeWorker().script)
    script[("rca", 1)] = {"rca": {"file": "src/other.c", "function": "elsewhere", "line_range": [1, 2],
                                  "bug_class": "uaf", "rationale": "wrong"}}
    script[("poc", 1)] = {"poc": b"CRASH"}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    orch.run(T)
    v = [e["verdict"] for e in events(orch) if e["event"] == "stage_attempt" and e["stage"] == "poc"][0]
    assert not v["accept"] and v["reason"].startswith("crash_location_mismatch")


def test_schema_error_is_rejection(make):
    script = dict(FakeWorker().script)
    script[("rca", 1)] = {"no_claim": True}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    e = [e for e in events(orch) if e["event"] == "stage_attempt"][0]
    assert e["schema_error"].startswith("schema_error") and rec.failed_at.value == "rca"


def test_patch_still_crashing_rejected(make):
    script = dict(FakeWorker().script)
    script[("patch", 1)] = {"patch": "--- a\n+++ b\n+nothing\n"}
    script[("patch", 2)] = {"patch": "--- a\n+++ b\n+FIX\n"}
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(script))
    rec = orch.run(T)
    v = [e["verdict"]["reason"] for e in events(orch) if e["event"] == "stage_attempt" and e["stage"] == "patch"]
    assert v == ["poc_still_crashes", "ok"] and rec.claimed_success


def test_cap_hit(make):
    orch, _, _ = make("configs/p3.yaml", worker=FakeWorker(usage=Usage(tokens_in=10_000_000)))
    orch.cfg.caps = Caps(wall_minutes=45, max_tokens=1_000, max_usd=100)
    rec = orch.run(T)
    assert rec.status == "cap_hit" and rec.stop_reason == "cap_tokens"


def test_single_session_b1_and_b2(make):
    for cfg in ("configs/b1.yaml", "configs/b2.yaml"):
        orch, _, w = make(cfg)
        rec = orch.run(T)
        assert rec.claimed_success and rec.attempts == {"single": 1}
        prompt = w.calls[0][2]
        assert "[official e2e prompt" in prompt and "claim.json" in prompt
        assert ("Recommended workflow" in prompt) == cfg.endswith("b2.yaml")


def test_budget_recorded_and_enforced(make):
    orch, _, _ = make("configs/p3.yaml")
    rec = orch.run(T)
    assert abs(orch.budget.spent() - rec.usd) < 1e-9 and rec.usd > 0
    orch2, _, _ = make("configs/p3.yaml", budget_usd=0.1)
    import pytest
    with pytest.raises(RuntimeError):
        orch2.run(Task(task_id="proj/arvo_2"))


def test_rerun_restarts_unfinished(make):
    orch, _, _ = make("configs/p3.yaml")
    d = orch.run_dir(T)
    d.mkdir(parents=True)
    (d / "events.jsonl").write_text(json.dumps({"event": "run_start"}) + "\n")
    assert not orch.is_done(T)
    orch.run(T)
    assert orch.is_done(T)
    assert sum(1 for e in events(orch) if e["event"] == "run_start") == 1
