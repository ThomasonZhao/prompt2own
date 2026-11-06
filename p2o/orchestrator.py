"""Stage-graph state machine (P0, P3) and single-session runner (B1, B2).

# STATUS: implemented against Protocols; tested with p2o.fakes.
The graph is enforced here, in code. Workers cannot skip a stage or write the ledger.
"""
from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path

from .budget import Budget
from .config import RunConfig
from .guards.base import build_guard
from .harness import HarnessAdapter
from .ledger import EventLog, Ledger
from .pricing import usd
from . import prompts
from .stage_io import sha256
from .types import (STAGE_ORDER, Fact, GuardInput, RunRecord, Stage, StageOutput, Task,
                    Usage, Verdict, now)
from .worker import Worker

CONTAINER_WORK = "/p2o/work"


class Orchestrator:
    def __init__(self, cfg: RunConfig, harness: HarnessAdapter, worker: Worker,
                 results_root: Path = Path("results"), budget: Budget | None = None):
        self.cfg, self.h, self.w = cfg, harness, worker
        self.root = results_root
        self.budget = budget or Budget()
        self.guards = {s: build_guard(sc.guard, harness, cfg.guards.get(sc.guard, {}))
                       for s, sc in cfg.stages.items()}

    # ------------------------------------------------------------------ helpers
    def run_dir(self, task: Task) -> Path:
        return self.root / "runs" / self.cfg.id / task.task_id.replace("/", "__")

    def is_done(self, task: Task) -> bool:
        return (self.run_dir(task) / "run.json").exists()

    def _fresh_dir(self, task: Task) -> Path:
        d = self.run_dir(task)
        if d.exists():                      # unfinished previous attempt: restart cleanly
            shutil.rmtree(d)
        d.mkdir(parents=True)
        return d

    def _caps_hit(self, used: Usage, spent: float, t0: float) -> str | None:
        c = self.cfg.caps
        if time.time() - t0 > c.wall_minutes * 60:
            return "cap_wall_time"
        if used.total > c.max_tokens:
            return "cap_tokens"
        if spent > c.max_usd:
            return "cap_usd"
        return None

    # ------------------------------------------------------------------ entry
    def run(self, task: Task) -> RunRecord:
        if not self.budget.can_start(self.cfg.caps.max_usd):
            raise RuntimeError(f"budget: only ${self.budget.remaining():.2f} left")
        d = self._fresh_dir(task)
        rec = RunRecord(run_id=uuid.uuid4().hex[:10], config=self.cfg.id, task=task,
                        seed=self.cfg.seed, status="failed", model=self.cfg.model,
                        provider=self.cfg.provider, config_hash=self.cfg.hash, started=now())
        log = EventLog(d, {"run_id": rec.run_id, "config": self.cfg.id, "task_id": task.task_id,
                           "seed": self.cfg.seed, "model": self.cfg.model, "provider": self.cfg.provider})
        log.emit("run_start", config_hash=self.cfg.hash)
        t0 = time.time()
        try:
            ws = self.h.prepare_task(task, d)
        except Exception as e:
            rec.status, rec.stop_reason = "infra_error", f"prepare_task: {str(e)[:200]}"
            return self._finish(rec, log, d, t0)
        try:
            if self.cfg.mode == "stage_graph":
                self._run_graph(task, ws, d, rec, log, t0)
            else:
                self._run_single(task, ws, d, rec, log)
        finally:
            try:
                self.h.teardown(ws)
            except Exception as e:  # never lose the record because teardown failed
                log.emit("error", where="teardown", error=str(e)[:200])
        return self._finish(rec, log, d, t0)

    # ------------------------------------------------------------------ P0 / P3
    def _run_graph(self, task, ws, d: Path, rec: RunRecord, log: EventLog, t0: float) -> None:
        ledger = Ledger(d)
        best: dict[Stage, Path] = {}
        last_claim = None
        for stage in STAGE_ORDER:
            sc = self.cfg.stages[stage.value]
            guard = self.guards[stage.value]
            reason: str | None = None
            accepted = False
            for attempt in range(1, sc.max_attempts + 1):
                cap = self._caps_hit(rec.usage, rec.usd, t0)
                if cap:
                    log.emit("cap_hit", stage=stage.value, cap=cap)
                    rec.status, rec.stop_reason, rec.failed_at = "cap_hit", cap, stage
                    self._deliver(ws, best)
                    rec.claimed_success = bool(last_claim and last_claim.done and stage == Stage.PATCH)
                    return
                art = d / "work" / stage.value / str(attempt)
                art.mkdir(parents=True, exist_ok=True)
                text = prompts.render_stage(self.cfg.prompts.dir, stage, task_id=task.task_id,
                                            src_path=ws.src_path,
                                            workspace=f"{CONTAINER_WORK}/{stage.value}/{attempt}",
                                            facts=ledger.render(), last_reason=reason)
                ph = prompts.prompt_hash(text)
                (art / "prompt.md").write_text(text)
                out = self.w.run(ws, stage, attempt, text, art, ph)
                verdict = self._judge(task, stage, attempt, out, guard, ledger)
                cost = usd(out.usage, self.cfg.prices)
                rec.usage, rec.usd = rec.usage + out.usage, rec.usd + cost
                rec.prompt_hash = rec.prompt_hash or ph
                rec.attempts[stage.value] = attempt
                g = rec.guard_counts.setdefault(verdict.guard, {"accept": 0, "reject": 0})
                g["accept" if verdict.accept else "reject"] += 1
                rec.final_guard_accept[stage.value] = verdict.accept
                if out.claim is not None:
                    last_claim = out.claim
                log.emit("stage_attempt", stage=stage.value, attempt=attempt, prompt_hash=ph,
                         claim=out.claim.model_dump() if out.claim else None,
                         schema_error=out.schema_error, worker_error=out.worker_error,
                         verdict=verdict.model_dump(), usage=out.usage.model_dump(),
                         usd=cost, seconds=out.seconds)
                self._remember_best(stage, art, best)
                if verdict.accept:
                    data = dict(verdict.evidence)
                    if out.rca is not None:
                        data.update(out.rca.model_dump())
                    sha = None
                    for fn in ("poc.bin", "fix.patch", "rca.json"):
                        if (art / fn).exists():
                            sha = sha256(art / fn)
                            break
                    ledger.append(Fact(stage=stage, attempt=attempt, guard=verdict.guard,
                                       data=data, artifact_sha256=sha))
                    accepted = True
                    break
                reason = verdict.reason
            if not accepted:
                rec.status, rec.stop_reason, rec.failed_at = "failed", "attempts_exhausted", stage
                rec.claimed_success = bool(last_claim and last_claim.done and stage == Stage.PATCH)
                self._deliver(ws, best)
                return
        rec.claimed_success = bool(last_claim and last_claim.done)
        rec.status = "success_claimed" if rec.claimed_success else "failed"
        rec.stop_reason = "completed"
        self._deliver(ws, best)

    def _judge(self, task, stage, attempt, out: StageOutput, guard, ledger: Ledger) -> Verdict:
        if out.worker_error:
            return Verdict(accept=False, reason=out.worker_error, guard="orchestrator")
        if out.schema_error or out.claim is None:
            return Verdict(accept=False, reason=out.schema_error or "schema_error: no claim", guard="orchestrator")
        facts = ledger.facts()
        inp = GuardInput(task=task, stage=stage, attempt=attempt, artifact_dir=out.artifact_dir,
                         claim=out.claim, facts=facts)
        try:
            return guard.check(inp)
        except NotImplementedError:
            raise
        except Exception as e:
            return Verdict(accept=False, reason="guard_error", evidence={"error": str(e)[:200]},
                           guard=getattr(guard, "name", "?"))

    @staticmethod
    def _remember_best(stage: Stage, art: Path, best: dict[Stage, Path]) -> None:
        # latest attempt that produced the file; overwritten by accepted attempts (break follows)
        fn = {Stage.POC: "poc.bin", Stage.PATCH: "fix.patch"}.get(stage)
        if fn and (art / fn).exists():
            best[stage] = art / fn

    def _deliver(self, ws, best: dict[Stage, Path]) -> None:
        self.h.write_deliverables(ws, best.get(Stage.POC), best.get(Stage.PATCH))

    # ------------------------------------------------------------------ B1 / B2
    def _run_single(self, task, ws, d: Path, rec: RunRecord, log: EventLog) -> None:
        art = d / "work" / "single" / "1"
        art.mkdir(parents=True, exist_ok=True)
        base = self.h.official_prompt(task)
        if self.cfg.prompts.single:  # B2
            base = prompts.load(self.cfg.prompts.dir, self.cfg.prompts.single).format_map(
                prompts._Safe(official_prompt=base, workspace=f"{CONTAINER_WORK}/single/1"))
        text = prompts.render_single(self.cfg.prompts.dir, base, self.cfg.prompts.suffix,
                                     f"{CONTAINER_WORK}/single/1")
        ph = prompts.prompt_hash(text)
        (art / "prompt.md").write_text(text)
        out = self.w.run(ws, Stage.SINGLE, 1, text, art, ph)
        cost = usd(out.usage, self.cfg.prices)
        rec.usage, rec.usd, rec.prompt_hash = out.usage, cost, ph
        rec.attempts["single"] = 1
        rec.claimed_success = bool(out.claim and out.claim.done)
        rec.status = "success_claimed" if rec.claimed_success else "failed"
        rec.stop_reason = out.worker_error or out.schema_error or "completed"
        log.emit("stage_attempt", stage="single", attempt=1, prompt_hash=ph,
                 claim=out.claim.model_dump() if out.claim else None,
                 schema_error=out.schema_error, worker_error=out.worker_error,
                 usage=out.usage.model_dump(), usd=cost, seconds=out.seconds)
        poc = next(iter(art.rglob("poc.bin")), None)
        patch = next(iter(art.rglob("fix.patch")), None)
        self.h.write_deliverables(ws, poc, patch)

    # ------------------------------------------------------------------ finish
    def _finish(self, rec: RunRecord, log: EventLog, d: Path, t0: float) -> RunRecord:
        rec.seconds, rec.ended = time.time() - t0, now()
        self.budget.record(self.cfg.id, rec.usd)
        log.emit("run_end", status=rec.status, stop_reason=rec.stop_reason,
                 failed_at=rec.failed_at.value if rec.failed_at else None,
                 claimed_success=rec.claimed_success, usd=rec.usd, seconds=rec.seconds)
        (d / "run.json").write_text(rec.model_dump_json(indent=2))
        return rec
