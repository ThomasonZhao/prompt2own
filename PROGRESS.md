# PROGRESS

One entry per milestone: `## M<n> — <time PT>` then Done / Verified by / Open issues.

## Skeleton — provided
Done: docs, types, config, ledger, budget, pricing, orchestrator, guards logic, fakes, CLI, analysis script.
Verified by: `pytest -q` (fake harness + fake worker).
Open: harness adapter, Claude Code worker verification, official grading, task index loader (M0–M3).

## M1 — 02:50 PT (Session B, branch worktree-session-b)
Done:
- Skeleton tests were already green (11 passed). Code review found three real bugs, fixed:
  1. `claimed_success` could inherit the PoC stage's `done: true` when the patch stage produced
     no claim (worker error / missing claim.json on every attempt) or the cap hit before patch#1.
     That inflates "claimed" and FSR. Now = PATCH stage's own last claim (`Orchestrator._patch_claimed`).
  2. `final_guard_accept[stage]` was overwritten by orchestrator rejections (schema/worker errors),
     so a run whose guard was never reached counted as a guard reject in precision/recall.
     Now only verdicts of the stage's guard are recorded.
  3. `--fake` CLI runs wrote into the real `results/` (runs, budget.json, and `grade --fake` into
     `results/grades/`), which would have mixed synthetic rows into the real summary.csv.
     All commands now take `--results`; `--fake` defaults to `results/fake/` and refuses `results/`.
- `run_start` now logs `templates_hash` (hash of all prompt templates) so a template change
  between runs is detectable; rendered-prompt hashes differ per task and cannot show that.
- `FakeWorker(vary=cfg_id)` (used by `batch --fake`) gives deterministic, mixed outcomes per
  (config, task); FakeHarness tests fail for patches containing "BREAKS" (gives guard recall < 1).
- New `tests/test_m1.py` (15 tests): cap_hit stops the run (tokens / usd / wall), worker_error is
  a rejection (fed to next attempt, uses an attempt, not a guard verdict), resume via `cli batch`
  skips finished runs and restarts unfinished ones, fake isolation, and regressions for 1-2.
Verified by: `pytest -q` -> 26 passed; `python -m p2o.cli run --config configs/p3.yaml --task FAKE --fake`
  -> events: rca#1 ACCEPT, poc#1 REJECT no_sanitizer_report, poc#2 ACCEPT, patch#1 ACCEPT.
Open issues (for Session A / later):
- Caps are only checked *between* attempts; one 15-min attempt can overshoot `max_usd` / token cap.
  The worker (`--max-turns`, stage timeout) is the only intra-attempt limit. Worth a check after the M4 pilot.
- `budget.can_start` is per run; with `--parallel 4` up to 4 runs can start on the last $0.75*4.
  Negligible at $150 but keep >= $3 headroom before launching a batch.
- `p2o/grade.py` fake grading sets s3 = s4 = s2, so check-pass gap is always 0 on fake data
  (grade.py is Session A's file; not changed). Unit tests cover the gap metric directly.
