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

## M7 — 04:00 PT (Session B)
Done:
- README: Quickstart 1 (no Docker / no key: tests, one fake P3 run + grade + trace, fake pipeline)
  and Quickstart 2 (one real dev task, libspng/arvo_14935: vast_setup -> .env -> fetch_sampled ->
  firewall with openrouter.ai -> budget -> run -> grade -> trace), full-evaluation commands, layout.
- `scripts/trace.py`: header (run id, config, model/provider, config + templates hash), aligned row
  per attempt (claim done/confidence, ACCEPT/REJECT, guard, reason), second line with $, tokens,
  time and key evidence (crash type, top frame, matches_rca, PoC fixed, tests pass, errors), cap
  hits, run_end totals, ledger facts, deliverables, official grade (`--no-grade` hides it for recording).
- Stratum (Session A's ask): `summary.csv` column `stratum` from tasks/sample_manifest.json
  (`summarize --manifest`); table_main / table_guards / table_paired give pooled rows (`all`) plus
  one block per stratum; fake pipeline writes a synthetic manifest. INTERFACES §7, EVAL §3 updated.
- M3 help: `tests/test_guards_docker.py` written against Session A's adapter API
  (`CyberGymE2EAdapter(use_firewall=False)`, dev task libspng/arvo_14935, GT PoC test-only):
  run_poc GT crashes with sanitizer report + frames; empty input no crash; candidate unchanged;
  exec_poc accepts GT PoC, rejects empty (`no_sanitizer_report`), mismatches a wrong RCA;
  exec_patch rejects empty patch and a non-applying patch (`patch_apply_failed`). Skips only when
  docker / harness / data are missing; NotImplementedError fails.
Verified by: `pytest -q` -> 36 passed. Quickstart 1 run step by step on a clean `git archive HEAD`
  export with a fresh venv: 36 passed, fake P3 trace + grade S1-S4 PASS, all 8 analysis files,
  only results/fake/ created. Quickstart 2 NOT verified: needs Session A's M2/M3 adapter on main.
  Docker tests collected (9) and skipped here (no harness in this worktree); not run against A's WIP
  adapter to avoid racing its guard image cache.

## Session B -> Session A
- What do you still need for M3/M4? I can take: running `pytest -m docker tests/test_guards_docker.py`
  once your guard methods land (tell me when, so we don't build the same cache tag concurrently),
  a dev-task P3 trace for the demo, or the real-data analysis after M5.
- Merge note: branch worktree-session-b touches p2o/cli.py (--results/--fake root, summarize
  --manifest); you also edited cli.py (adapter flags, grade --parallel). Expect a small conflict.
- Please run Quickstart 2 once on the VM after the merge, or tell me which step differs.
