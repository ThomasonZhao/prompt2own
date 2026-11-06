# MILESTONES

Two Claude Code sessions run in parallel from the start (see `KICKOFF.md`):
- **Session A (infra):** M0 -> M2 -> M3 -> M4 -> M5
- **Session B (core):** M1 -> M6 -> M7, then helps A

Target times are Pacific, 2026-11-06. **Hard gate: P3 main batch launched by 15:00 PT.**

## M0 — Environment + official B1 (Session A, target 03:30)

Do:
1. `bash scripts/vast_setup.sh` on the VM. Confirm `sysctl vm.mmap_rnd_bits` = 28 and Docker works.
2. Clone the harness to `third_party/cybergym-e2e`; download dataset metadata; answer all
   questions in `docs/HARNESS.md`.
3. Implement the index loader in `scripts/sample_tasks.py`; run with `--seed 329`; commit
   `tasks/dev.txt`, `tasks/main30.txt`, `tasks/sample_manifest.json`.
4. Pull images for the 33 tasks only.
5. Implement `p2o/grade.py` (wrap the official grading entry point).
6. Run official B1 (harness's own Claude Code agent, our model/endpoint, our caps, claim suffix)
   on 1 dev task; grade it.

Accept: `cat results/grades/b1/<dev_task>.json` shows s1..s4. Then **immediately launch B1 on
`main30` in tmux** and move on. B1 runs while everything else is built.

## M1 — Core loop with fakes (Session B, target 05:00)

Already implemented in the skeleton: types, config, ledger, budget, pricing, orchestrator,
NullGuard, CLI wiring, tests with fakes. Do:
1. Read the code; run `pytest -q`; fix anything that fails honestly.
2. Add tests for: cap_hit stops the run; worker_error counts as a rejection; resume skips finished runs.

Accept: `pytest -q` green; `python -m p2o.cli run --config configs/p3.yaml --task FAKE --fake`
writes `events.jsonl` containing a reject -> retry -> accept sequence.

## M2 — Real worker (Session A, target 08:00)

Do: implement `CyberGymE2EAdapter.prepare_task / exec_worker / copy_out / write_deliverables /
teardown` and `ClaudeCodeWorker` per INTERFACES.md §4-5, reusing the harness's container
and Claude Code installation path.

Accept: `python -m p2o.cli run --config configs/p0.yaml --task <dev_task>` produces
`deliverables/poc.bin` + `deliverables/fix.patch`; `p2o.cli grade` writes a grade file;
`events.jsonl` has non-zero token usage and a USD figure from `pricing.py`.

## M3 — Executable guards (Session A, target 11:00)

Do: implement `run_poc`, `apply_patch_and_build`, `run_tests` in the adapter (fresh container
each call, from the *vulnerable* image, using the harness's commands). Guard decision logic
in `exec_poc.py` / `exec_patch.py` is already written; adjust only if the adapter's outputs require it.

Accept: `pytest -q -m docker tests/test_guards_docker.py` passes:
dev ground-truth PoC -> `exec_poc` accept (positive control, test-only);
empty file -> reject `no_sanitizer_report`; empty patch -> `exec_patch` reject.

## M4 — P3 pilot (Session A, target 13:00)

Do: run P3 and B1 on the 3 dev tasks. Pick the model (pilot both if cheap). Set
`P2O_TOKEN_CAP` so a run is <= $0.75. Freeze `.env` and configs; commit.

Accept: 3/3 P3 runs reach `run_end` with complete events; `p2o.cli budget` spend matches the
sum of run USD within 1%.

## M5 — Main batches (Session A, by 15:00 hard gate)

Do: `p2o.cli batch --config configs/p3.yaml --tasks tasks/main30.txt --parallel 4` in tmux.
If budget allows, launch B2 at the same time (`--parallel 2` each if CPU-bound). Then P0.

Accept: batches running; `p2o.cli budget` projection under $150.

## M6 — Analysis (Session B, target 20:00)

Do: `p2o.cli summarize` builds `results/summary.csv` from runs + grades; run
`scripts/analyze.py`; check numbers against a few raw runs by hand.

Accept: one command regenerates every file listed in EVAL.md §3.

## M7 — Reproducibility + demo trace (Session B, target 22:00)

Do: README "Quickstart" works in a fresh shell on one dev task; `scripts/trace.py <run_dir>`
prints a readable timeline (stage, attempt, claim, verdict, reason, cost) for the demo video.

Accept: following README from a clean clone reaches a grade file for one dev task.

## Cut order if behind

B2 -> P0 -> tests step in `exec_patch` (keep apply + build + PoC-no-longer-crashes) ->
P3 on first 15 tasks of main30 only. If P3 cannot run at all: ship full B1 analysis + P3 pilot.
