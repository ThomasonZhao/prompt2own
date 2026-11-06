# ARCHITECTURE

## 1. Big picture

```
                 +-------------------------- host (VM) ---------------------------+
                 |                                                                |
 configs/*.yaml  |   p2o.cli ──> Orchestrator ──────────────> Ledger / EventLog   |
 tasks/*.txt ───>|       |            |   ^                    (results/runs/...) |
                 |       |            |   | Verdict                    |           |
                 |       |   Worker.run   Guard.check                  |           |
                 |       |            v   |                            v           |
                 |       |   +-----------------+   +----------------+  summary.csv |
                 |       |   | task container  |   | guard container|      ^       |
                 |       |   | (worker zone)   |   | (fresh, per    |      |       |
                 |       |   | claude -p ...   |   |  check)        |   Grader     |
                 |       |   +-----------------+   +----------------+ (official,   |
                 |       |        via HarnessAdapter (p2o/harness.py)  after run)  |
                 +----------------------------------------------------------------+
```

Prompt2Own is a second agent type *inside* the official CyberGym-E2E harness: same task
images, same deliverables (`poc.bin`, `fix.patch`), same grader. All Docker and
harness-specific calls go through one class, `HarnessAdapter` (`p2o/harness.py`).
Everything else is harness-agnostic and unit-testable with fakes.

## 2. Trust zones

| Zone | Where | Can read | Can write | Never sees |
| --- | --- | --- | --- | --- |
| Worker | Task container, one fresh Claude Code session per stage attempt | Source tree, its rendered prompt (verified facts + last rejection reason) | Its stage workspace `/p2o/work/<stage>/<attempt>/` | Ground truth, grader, guards' containers, other runs |
| Orchestrator | Host process | Configs, ledger, worker outputs, verdicts | Ledger, events, workspaces, deliverables | Grader output (until the run has ended) |
| Guard | Fresh container from the task's *vulnerable* image, started per check | Candidate artifact + claim + verified facts | Its `Verdict` only | Ground truth, grader, worker's container state |
| Grader | Official harness, after `run_end` | Ground truth | `results/grades/` | — |

Why this matters: false success and guard accuracy are only measurable because guards
and grader are separate. A guard that peeks at ground truth turns P3 into an oracle and
destroys the result.

## 3. Control flow

### stage_graph (P0, P3)

```
run_start
ws = harness.prepare_task(task)            # start container, leak cleanup, copy source
for stage in [RCA, POC, PATCH]:
    reason = None
    for attempt in 1..cfg.stages[stage].max_attempts:
        if caps exceeded: emit cap_hit; stop(failed_at=stage, stop_reason=cap)
        out = worker.run(StageRequest(stage, attempt, facts=ledger.facts(), last_reason=reason))
        if out.schema_error: verdict = reject("schema_error: ...")
        else:                verdict = guards[stage].check(GuardInput(...))
        emit stage_attempt(out, verdict, cost)
        if verdict.accept: ledger.append(Fact(stage, verdict.evidence)); break
        reason = verdict.reason
    else:
        stop(failed_at=stage, stop_reason=attempts_exhausted)
harness.write_deliverables(ws, poc=best_poc, patch=best_patch)
run_end(status, claimed_success, cost, seconds)
```

Notes:
- RCA's guard in P3 is `null`; its claim is checked when `exec_poc` compares the crash
  location with the RCA's claimed function/file.
- If a stage stops, the run still writes whatever deliverables exist (a PoC without a patch
  can still earn S1). `claimed_success` = the last stage's claim `done` *as the worker
  stated it*, independent of guard verdicts. This is what FSR is computed from.
- In P0 (`null` everywhere) every schema-valid attempt is accepted on the first try.

### single_session (B1, B2)

```
run_start
ws = harness.prepare_task(task)
out = worker.run_single(prompt = official_or_b2_prompt + CLAIM_SUFFIX)
harness.write_deliverables(ws, poc=out.poc, patch=out.patch)   # usually already in place
run_end(...)
```

For B1, prefer the harness's own Claude Code launch path (see HARNESS.md) with only the
claim suffix appended, so B1 matches the paper's setup as closely as possible.

## 4. Modules

| Module | Status | Responsibility |
| --- | --- | --- |
| `p2o/types.py` | implemented | All pydantic models. Single source of truth for schemas. |
| `p2o/config.py` | implemented | Load YAML with `${ENV}` expansion -> `RunConfig`; config hash. |
| `p2o/ledger.py` | implemented | `Ledger` (facts) and `EventLog` (events), append-only JSONL with fsync. |
| `p2o/budget.py` | implemented | Global spend file with file lock; `can_start`, `record`. |
| `p2o/pricing.py` | implemented | Token counts -> USD from the config's price table. |
| `p2o/orchestrator.py` | implemented | Stage-graph state machine and single-session runner, against Protocols. |
| `p2o/prompts.py` | implemented | Render stage templates; prompt hash. |
| `p2o/guards/base.py` | implemented | `Guard` Protocol, registry, `NullGuard`. |
| `p2o/guards/exec_poc.py` | logic implemented, needs adapter | PoC guard decision logic on top of `HarnessAdapter.run_poc`. |
| `p2o/guards/exec_patch.py` | logic implemented, needs adapter | Patch guard logic on top of `apply_patch_and_build`, `run_poc`, `run_tests`. |
| `p2o/guards/llm_judge.py` | stub | Final report only. |
| `p2o/harness.py` | **stub (M0/M2/M3)** | `HarnessAdapter` Protocol + `CyberGymE2EAdapter` (Docker + official scripts). |
| `p2o/worker.py` | **stub (M2)** | `ClaudeCodeWorker`: run `claude -p` inside the task container, collect outputs, parse usage. |
| `p2o/grade.py` | **stub (M0)** | Call the official grader, write `results/grades/<config>/<task>.json`. |
| `p2o/cli.py` | implemented (wiring) | `run`, `batch`, `grade`, `summarize`, `budget`. |
| `scripts/sample_tasks.py` | needs index loader (M0) | Deterministic sampling. |
| `scripts/analyze.py` | implemented | All tables/figures in EVAL.md from `summary.csv`. |

## 5. Failure handling

- Worker crash / non-zero exit: counts as a rejected attempt, reason `worker_error: <short>`.
- Guard crash: rejected attempt, reason `guard_error`; logged as `error` event too (so we
  can separate infrastructure failures from agent failures in analysis).
- Infrastructure failure before the first stage (image missing, container won't start):
  `run_end(status="infra_error")`; excluded from metrics, reported as a count.
- Host restart: batch is resumable; runs without `run_end` are deleted and restarted.
