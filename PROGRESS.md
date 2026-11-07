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

## M0 — 03:50 PT (Session A, branch worktree-session-a)
Done:
- Setup: `scripts/vast_setup.sh` stopped at step 2 (apt: an unrelated nvidia dkms kernel package fails to
  configure, exit 100). tmux/git/uv/node were already installed, so steps 3-5 were run by hand: harness deps
  installed into .venv, `ubuntu/squid` pulled. `vm.mmap_rnd_bits`=28, Docker 28.1.1 OK, 30 vCPU / 148 GB / 966 GB.
  Firewall: `python -m firewall start --domain openrouter.ai` (internal network `cybergym-internal`).
- docs/HARNESS.md: all 9 questions answered with file:line, plus the exact leak-cleanup list.
- Sampler (`scripts/sample_tasks.py`): index = 920 tasks / 139 projects from `projects/*/*/config.toml`.
  Stratified per the pre-registration above: 614 tasks meet E1+E2. Seed 329.
- E3 (`scripts/build_check.py`): compile.sh timed for all 33 tasks in guard-zone containers, 4 builds
  concurrently (so the times are conservative). All passed except **ffmpeg/oss-fuzz_377642312 (easy): 19.9 min > 10**,
  replaced by the next reserve_easy task **libidn2/arvo_12420** (0.62 min). Max main build time after
  replacement: 3.52 min (zeek). Times are logged in `tasks/sample_manifest.json` (`build_minutes`, `replacements`) and
  `results/guard_cache/builds.jsonl`. Incident: the first pass stopped the ffmpeg build at 17.8 min. Reserve
  tasks then "failed" because their data had not been fetched yet (a script bug, not a build failure), and the
  script exited before writing anything. The bogus entries were removed from builds.jsonl (backup `builds.jsonl.bak-1124`),
  and ffmpeg was re-measured unstopped (19.9 min).
- Data and images for the 33 tasks only (`scripts/fetch_sampled.py`): 22 unique images. 3 tasks have no crash.log
  (patch-only input, not used).
- `p2o/grade.py`: wraps the official `run_agent.run_final_validation` unmodified, with a log per task in results/grades/.
- B1 runs through our adapter, which reuses the harness's functions (start_container, setup_workspace, install,
  switch_network, get_prompt_iterative) and the official claude command and flags. We do not call run_agent.py as a CLI
  because it has no OpenRouter provider and does not pin the small/fast and subagent models (HARNESS.md Q1).
- **Frozen for all configs (before any main batch):** model `z-ai/glm-5.3-flash` (prices re-checked against
  /api/v1/models, they match the table); `P2O_TOKEN_CAP=20000000`; an in-session USD cap = `caps.max_usd` ($0.75),
  priced from metered usage. The 3M default would have cut the B1 dev run (2.43M tokens, $0.087) at about $0.10, because
  cached reads count as tokens. 20M tokens is about $0.75 at the observed mix, and the USD cap bounds the worst case. The
  deepseek pilot was skipped: the milestone order launches B1 main at M0, so the model must be frozen now.
Verified by: `cat results/grades/b1/libspng__arvo_14935.json` -> s1..s4 all true (official grader, 110 s).
  `pytest -q` -> 45 passed. The init event shows model z-ai/glm-5.3-flash, Claude Code 2.1.91 and no WebFetch/WebSearch/Task tools.
  `modelUsage` lists only the frozen model, so every alias is pinned.
Bugs found and fixed:
- Usage undercount: a Claude Code session emits one `result` event per turn (agents' background tasks trigger extra
  turns), and `result.usage` covers only that turn. Via OpenRouter, `assistant` events carry zero usage. The fix uses the last
  result's cumulative `modelUsage`, or the summed raw `message_delta` usage (`--include-partial-messages`, an output-only
  flag), whichever is larger. The B1 and P0 dev runs were corrected with `scripts/recompute_usage.py` ($0.0019 -> $0.0865 and
  $0.034 -> $0.069), each adding a `usage_correction` event; the budget was updated.
- P3 templates leaked the task id (`{task_id}` in common.md) into worker prompts. Removed, with a regression test.
  They also pointed at `git diff`, which can't work because the harness deletes the repo's .git. Replaced with a
  /src_backup diff recipe. They now name the harness scripts (compile.sh/run_poc.sh/test.sh), worded like the official prompt.
Decisions needing a human look (no hard rule broken as far as I can tell, but flagging):
- B1/B2 keep `/scripts/validate.py` in the worker container because the official prompt tells the agent to use it.
  It cannot run stage 4 (no ground-truth PoC in /data). P0/P3 workers get `/scripts` removed (CLAUDE.md: workers never
  see grading code). If you read the rule as covering B1 too, B1 deviates from the official harness instead.
- Grading a PoC without a patch: we still grade S1 (ARCHITECTURE §3). The official loop would not
  (`raw.official_loop_s1` keeps the official convention).
Open issues:
- Session B's commits were brought in as patches (git 2.34 rejects the global `merge.conflictstyle=zdiff3`, so
  cherry-pick fails). Merge the two branches by hand at the end; expect PROGRESS.md and cli.py conflicts.

## M2 — 03:50 PT (Session A)
Done: adapter worker zone (prepare_task / exec_worker / copy_out / write_deliverables / teardown, official_prompt),
`ClaudeCodeWorker` (stream-json parsing, token and USD caps inside the session, wall_minutes timeout for single sessions).
Verified by: `python -m p2o.cli run --config configs/p0.yaml --task libspng/arvo_14935` -> rca/poc/patch accepted (null
guards), deliverables/poc.bin + fix.patch written, `p2o.cli grade` -> S1-S4 true, events have non-zero usage and USD
($0.069 after the correction). OpenRouter's own key counter moved +$0.12 over a window that covered P0 plus the tail
of B1 dev: consistent. A precise per-request cross-check (the `cost` field in message_delta) is planned for M4.

## M3 — 03:50 PT (Session A)
Done: `run_poc` / `apply_patch_and_build` / `run_tests`. A guard-zone vulnerable build per task (official setup_workspace
with copy_gt_poc=False + compile.sh, committed to a local `p2o-guardcache:*` image, never touched by a worker). Each
check runs in a fresh container from it: the PoC with `--network none`, build and tests on the default bridge like the
official stage containers. A patch is applied to the pristine `/src_backup` tree with the harness's own
`validate.apply_patch`. Crash = exit not in {0,71}, as in validate.py:210. Compile timeout = the official 3600 s;
guard `timeout_s` applies to run_poc.sh / test.sh.
Verified by: `pytest -q -m docker tests/test_guards_docker.py` -> 9 passed (Session B's tests: GT PoC accepted,
empty input -> no_sanitizer_report, wrong RCA -> crash_location_mismatch, empty or non-applying patch rejected).
The GT PoC report's top frame is `validate_past_idat spng.c:1152`; runtime and libc frames are dropped.

## M4 — 04:25 PT (Session A)
Done:
- P3 pilot 1 on dev (results/runs/p3-pilot1/, archived): libspng and gdbm success_claimed. wireshark failed: the RCA
  worker spent 15 min fuzzing and was killed by the stage timeout before writing rca.json; with rca max_attempts=1
  that ended the run. Dev-only tuning: `common.md` now states the hard 15-min stage limit ("write required files
  early"), and rca max_attempts = 2 in p3 and p0 (p0 mirrors p3 except guards).
- P3 pilot 2 on dev with the final templates and config: 3/3 success_claimed, all stages accepted on attempt 1
  ($0.12 / $0.33 / $0.26). Guard evidence is real: an ASan report with top frames matching the RCA; a patched build;
  the verified PoC no longer crashes; tests pass.
- B1 dev: 3/3 S1-S4 = True (libspng, gdbm, wireshark). P3 dev libspng S1-S4 = True (the others are being graded).
  B2 dev libspng S1-S4 = True.
- Model: z-ai/glm-5.3-flash, frozen at M0 (see there). deepseek was not piloted.
- Usage accuracy: Claude Code's `modelUsage` double-counts input via OpenRouter (246,558 vs 138,773 per-request input
  on the same stage; cached and output equal). Usage is now the exact per-request `message_delta` sum; modelUsage
  is only a fallback. The B1 main runs that started before this fix (03:48 PT) used max(modelUsage, stream) and will be
  re-priced with `scripts/recompute_usage.py` after they finish (each correction is logged as a `usage_correction` event).
- Prices: OpenRouter routed GLM to a provider charging less than the listed price (billed per request: about $0.03/M
  input, $0.22/M output vs the table's $0.15 / $0.50), so our USD is conservative: for the same runs, ours is 7-60%
  above OpenRouter's billed `cost`. The table stays as pre-registered (SPEC §5).
- Frozen: `.env` (model, token cap 20M), configs b1/b2/p0/p3 (identical model/caps/prices; p3/p0 rca=2).
Verified by: `python scripts/check_spend.py` -> sum(run usd) $2.4772 == budget spent $2.4772 (0.00%, <= 1%);
  3/3 P3 dev runs have complete events ending in run_end.
Open:
- CPU: load average 40+ on 30 vCPU while B1 main and builds run, so P3 main gets --parallel 3 and B2 --parallel 2 (M5 note).
- Session B has exited. Notes for M6/M7: results/runs/p3-pilot1 is an archived dev pilot (config column = dir
  name). The latest `usage_correction` event supersedes stage_attempt usage; run.json is always current. Use the P3 dev runs
  in results/runs/p3/ for the demo trace.

## M5 — 04:24 PT (Session A) — main batches launched before the 15:00 hard gate
Done: tmux `b1` (03:48 PT, --parallel 4), `p3` (04:23 PT, --parallel 3), `b2` (04:23 PT, --parallel 2), all on
tasks/main30.txt (20 easy + 10 uniform, after the E3 replacement). Grading: tmux `grade` runs
`scripts/grade_loop.py tasks/main30.txt b1 p3 b2` (grades only runs with run.json, every 5 min).
Verified by: `python -m p2o.cli budget` before launch -> $2.57 spent, $147.43 remaining. Projection: hard worst case
(all 90 runs at the $0.75 in-session cap) = $67.50 + $2.57 = $70 < $150. At pilot averages (B1 ~$0.10, P3 ~$0.24,
B2 ~$0.15 per run) it is about $15-20.
Next: P0 main after B1 finishes (CPU); re-price B1 runs (recompute_usage.py); summarize + analyze (M6, Session B's).

## Recovery — 2026-11-06 12:25 PT (Session A, branch worktree-session-a)
The previous VM went offline at an unknown time after M5. Every run, grade, budget and guard-cache file on it was lost
(results/ was never pushed). The main batches restart from scratch on a new host. Code, configs, templates, model, caps,
prices, tasks/*.txt and sample_manifest.json are unchanged since def8162. `git diff def8162 -- configs p2o tasks` is empty.
New host: 61 vCPU / 197 GB RAM / 497 GB disk, Ubuntu 22.04 VM, kernel 6.8.0-59, Docker 28.1.1, `vm.mmap_rnd_bits`=28.
Done:
- `scripts/vast_setup.sh`: apt succeeded this time. The script stopped at step 4: `uv venv` picked Python 3.15, and pytest
  ran before step 5 installs tomli. Fixed by hand: `.venv` recreated on Python 3.11 (project convention), harness deps
  installed, harness cloned at the same commit d0ae0f0, squid pulled. Host Claude Code is 2.1.319, but workers still get
  2.1.91 through the harness's own install. `pytest -q` -> 45 passed.
  Firewall: `python -m firewall start --domain openrouter.ai` (cybergym-internal).
- Data: `scripts/fetch_sampled.py --tasks <the 33 ids in tasks/dev.txt + tasks/main30.txt>` (data plus images only).
- Guard cache: rebuilt by calling `build_check.check()` directly for the 33 frozen tasks, 8 concurrently. This skips
  build_check's replacement loop and its manifest / tasks/*.txt rewrite. Log: logs/rebuild_frozen.log. **All 33 built,
  no failures, no replacements.** Times are 2-5x the M0 times (8 builds in parallel, load average up to ~110).
  Max easy time 5.86 min (libarchive), so all easy tasks still meet E3 (<= 10 min). The manifest's build_minutes keep
  the original M0 values.
- Budget: results/budget.json was lost, and the new one started at $0. OpenRouter's key counter at recovery start =
  **$11.94 actually billed** (logs/openrouter_usage.jsonl), which covers the dev pilots plus the lost main runs. Our table
  priced 7-60% above OpenRouter's billed cost (M4), so the ledger carries `lost_prior_vm_estimate` = $11.94 x 1.6 =
  **$19.10**. check_spend.py's sum(run usd) == budget check is therefore off by exactly that amount from now on.
- Smoke: P3 on libspng/arvo_14935 (dev): success_claimed, $0.330, 30.9 min. RCA attempt 1 was rejected
  (`schema_error: missing rca.json`): the worker fuzzed until the 15-min stage limit while the guard builds held load at
  ~100. RCA attempt 2, PoC and patch were all accepted on the first try. Official grade S1-S4 = PASS (175 s).
  config_hash fb41ddb16869, templates_hash 9d83d8024cc9.
- `scripts/sync_results.sh` (new): every 15 min it copies results/runs/**/{run.json,events.jsonl,ledger.jsonl},
  results/grades/** and results/summary.csv into a worktree at ../prompt2own-results on branch `results`, force-adds,
  commits, and pushes only `refs/heads/results`. It runs in tmux session `p2o`, window `sync` (logs/sync.log).
  The first push (b10ba71) was verified.
- Main batches (tmux session `p2o`), launched 12:05 PT after `p2o.cli budget` showed $130.57 remaining (worst case for
  b1+p3+b2 = $67.50): window `b1` (--parallel 4), `p3` (--parallel 3), `grade` (`scripts/grade_loop.py
  tasks/main30.txt b1 p3`). P0 skipped for this recovery.
- B2 not launched yet: once workers start compiling and fuzzing, load is 25-114, and the 5-min average holds at 30-44,
  above the ~28 threshold. I re-check it as batches progress.
Differences from the original M5 run: new host (2x vCPU); all main runs restart from scratch; the B1 runs now use the
per-request usage fix from the start, so no B1 re-pricing is needed; no P0 main; B2 is conditional on load.
Open: B2 launch decision; the main batches must finish before the 20:00 PT results deadline.

## Recovery results — 2026-11-06 16:05 PT (Session A)
Done: b1 and p3 main finished at 16:03 PT (started 12:05). 30/30 runs each have run_end and an official grade; no
infra errors, none ungraded. B2 was **not run**. Load never stayed below ~28 (the 5-min average was 25-85 from 12:35 to
14:00). At p3's rate, B2 at --parallel 2 (about 15 waves) could not have finished by 20:00, and it would have slowed p3.
P0 skipped as instructed.
`p2o.cli summarize` + `scripts/analyze.py results/summary.csv --out results/figs/`. Final sync -> results@86770e0.
Headline (pooled = not representative of the benchmark): S4 b1 0.433 vs p3 0.333; FSR b1 0.400 vs p3 0.444; paired
S4 McNemar p=0.549 (n=30). exec_poc precision 1.000 / recall 0.857; exec_patch precision 0.588 / recall 1.000.
All 7 exec_patch false accepts pass S1-S3 and fail only S4: the patch stops the worker's own PoC, builds and
passes tests, but the ground-truth PoC still crashes. The guard cannot see the GT PoC by design, so the patch guard
checks "fixes my PoC", not "fixes the bug".
Verified by: `python scripts/check_spend.py` -> sum(run usd) $11.42 vs budget $30.52. The difference is exactly the
$19.10 lost_prior_vm_estimate carry-over (Recovery entry). Per run, ours >= OpenRouter's billed cost, so recompute_usage
was not needed. OpenRouter's counter: $11.94 -> $21.54 (+$9.61 this session vs our $11.42).
A partial snapshot (15:01 PT) is in results/partial/ (local only, labeled PARTIAL). Demo trace: results/demo_trace.txt.
Open: B2/P0 main not run; the B2 comparison is missing from the main table.

## B2 main — launched 2026-11-06 16:21 PT (Session A)
On the user's instruction, b2 runs on tasks/main30.txt with **--parallel 6** (the original M5 plan was --parallel 2), because
the CPU is free now that b1/p3 are done. Per-run caps, model, prices and configs/b2.yaml are unchanged (`git diff def8162
-- configs p2o` empty). Parallelism changes only wall-clock contention, not the per-run budget; it may affect per-run
minutes, so b2's median_minutes is not directly comparable to b1/p3 (which ran at 4+3 concurrent).
Budget before launch: $119.48 remaining vs a $22.50 worst case. Grade loop restarted as `grade_loop.py tasks/main30.txt b1 p3 b2`.
**Hard stop 20:30 PT**: unfinished b2 runs are killed. Those runs have no run.json and drop out of summary.csv, so
partial b2 is biased toward tasks that finish fast. b2 paired comparisons cover completed tasks only.

## B2 main results — 2026-11-06 18:35 PT (Session A)
Done: b2 finished on its own at ~18:30 PT (started 16:21, --parallel 6). The 20:30 hard stop found nothing to kill, so
b2 is **complete**: 30/30 run_end, 30/30 graded, no infra errors, no fast-run bias. Re-ran summarize + analyze over all three
configs. b2-vs-b1 paired table from `analyze.paired_table(ref="b2")` -> results/figs/table_paired_b2_vs_b1.csv
(analyze.py itself pairs only against p3). Final sync -> results@be5c470.
Headline (pooled = not representative): S4 b2 0.533 / b1 0.433 / p3 0.333; FSR b2 0.273 / b1 0.400 / p3 0.444.
Paired S4: p3 vs b2 McNemar p=0.109 (only p3 2, only b2 8); b2 vs b1 p=0.453 (only b2 5, only b1 2). None significant at n=30.
b2's median_minutes (15.9) ran at 6 concurrent on an otherwise idle host vs 4+3 concurrent for b1/p3: not comparable.
Verified by: check_spend.py sum(run usd) $16.07 vs budget $35.17; the difference is the $19.10 carry-over. OpenRouter's counter
$21.54 -> $25.63 (+$4.09 for b2 vs our $4.65).
Classification of the 7 exec_patch false accepts: results/figs/false_accepts.md (all 7 fix a different bug than the target).
Open: P0 main not run.
