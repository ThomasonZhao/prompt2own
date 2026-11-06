# PROGRESS

One entry per milestone: `## M<n> — <time PT>` then Done / Verified by / Open issues.

## Skeleton — provided
Done: docs, types, config, ledger, budget, pricing, orchestrator, guards logic, fakes, CLI, analysis script.
Verified by: `pytest -q` (fake harness + fake worker).
Open: harness adapter, Claude Code worker verification, official grading, task index loader (M0–M3).

## Pre-registration — task sampling strata (written 2026-11-06 ~02:50 PT, before any sampling or run)

Requested by the user before any main batch. Selection uses task metadata only, never model results.

**Easy stratum: a task is "easy" iff all of:**
- E1: the ground-truth fix (`third_party/cybergym-e2e/projects/<project>/<task>/patch.diff`) touches exactly 1 file
  (counted as distinct `+++ b/<path>` targets, ignoring `/dev/null`).
- E2: that fix changes <= 20 lines (added + removed body lines, excluding `---`/`+++`/`@@` headers).
- E3: the task builds in the official harness in <= 10 min wall clock (harness `compile.sh` via the official
  `validate.py` path on the task's own build image, 30 vCPU VM, cold container, measured once per sampled task during the
  M0/M4 pilot build checks). E1/E2 are checked by the sampler; E3 is measured after sampling, and a task that fails E3,
  or fails to build or start at all, is replaced by the next task of the same stratum in the shuffled reserve order.
  Every replacement is logged in `tasks/sample_manifest.json` with its reason and measured build time.

**Sampling (seed 329, one task per project overall):**
- dev (3, tuning only, never reported): 2 easy + 1 uniform, same 2:1 mix as main. This is my choice, made so the pilot
  looks like main. Dev projects are excluded from main.
- main30: 20 easy (one per project, projects shuffled with the seed, one easy task drawn per project) + 10 uniformly
  random tasks drawn one per project from the remaining projects. The uniform draw ignores difficulty, so it may include
  easy-qualifying tasks.
- Each task's stratum (`easy` | `uniform`), its E1/E2 values and the criteria text are recorded in
  `tasks/sample_manifest.json`. `summary.csv` gets a `stratum` column. All results are reported per stratum
  and pooled, and the pooled numbers are labeled as not representative of the full benchmark.

**Ground-truth isolation:** only `scripts/sample_tasks.py` reads `patch.diff`, and it stores only the derived counts
(files, lines). The diff itself never goes into task containers, prompts, guards or `p2o/` runtime code. The adapter
copies only `prepare.sh`, `compile.sh`, `run_poc.sh`, `test.sh` and a sanitized config, through the official
`setup_workspace`.
