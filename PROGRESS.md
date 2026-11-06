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

## M6 — 03:25 PT (Session B) — built and verified on fake data; rerun on real data after M5
Done:
- `scripts/analyze.py` rewritten; one command writes all 8 EVAL §3 files: table_main.{csv,tex},
  fig_funnel.pdf, table_guards.{csv,tex}, table_paired.csv, fig_retries.pdf, failures.md.
  Wilson CI on every rate; ungraded runs excluded and counted (were silently scored 0);
  default task filter `tasks/main30.txt` (keeps M4 dev pilots out); mixed config_hash/model warnings;
  guard table with false accepts/rejects and P3 stage FSR; paired McNemar on S4 and false success.
- `summary.csv` gains `claimed_poc`, `claimed_patch` (from events.jsonl) for stage FSR (INTERFACES §7 updated).
- **Bug fixed in `p2o/budget.py`:** `record` rewrote budget.json in place while `can_start` read it
  without the lock; under `batch --parallel 4` runs crashed with JSONDecodeError at start (25/30
  fake P3 runs lost on the first try). Now atomic write (tmp + os.replace, fsync) and locked reads.
  This would have hit the real B1/P3 batches too. Session A: pull this before M5.
- `scripts/fake_pipeline.sh`: 30 synthetic tasks x {b1,b2,p0,p3} -> grade -> summarize -> analyze, in results/fake/.
- Tests: `tests/test_analyze.py` (hand-computed guard precision/recall/stage FSR, paired counts +
  exact McNemar p, exclusions, task filter, one-command regeneration), `tests/test_budget.py` (16 threads).
Verified by: `pytest -q` -> 34 passed. `bash scripts/fake_pipeline.sh` -> 120/120 runs, all 8 files.
  Hand check: recomputed n / S4 / claimed / FSR / PoC-guard precision for b1 and p3 directly from
  run.json + grade files (not summary.csv): identical to table_main / table_guards. Figures inspected as PNG.
Open: real-data run of analyze after M5 (`python -m p2o.cli summarize && python scripts/analyze.py
  results/summary.csv --out results/figs/`). Fake grader has s3 = s4, so check-pass gap is 0 on fake data.
