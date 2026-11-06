# KICKOFF — prompts to paste into Claude Code

Run on the VM from the repo root. Two sessions in two tmux windows, both with
`claude --dangerously-skip-permissions` (the VM is disposable and the firewall is on;
do not do this on your own laptop). Check in at each milestone's target time.

## Session A — infra (M0 -> M2 -> M3 -> M4 -> M5)

```
Read CLAUDE.md, then docs/SPEC.md, docs/ARCHITECTURE.md, docs/INTERFACES.md, docs/HARNESS.md
and docs/MILESTONES.md. You are Session A: you own M0, M2, M3, M4, M5, in that order.
Session B is working on M1/M6/M7 in parallel; do not edit p2o/orchestrator.py, p2o/summary.py
or scripts/analyze.py without writing why in PROGRESS.md.

Start with M0. Run scripts/vast_setup.sh. Then read the official harness in
third_party/cybergym-e2e and answer every question in docs/HARNESS.md with file:line
references before writing adapter code. Implement scripts/sample_tasks.py:load_index,
sample with --seed 329, pull images for the sampled tasks only, implement p2o/grade.py,
and get one graded official B1 run on the first dev task. As soon as that works, launch
B1 on tasks/main30.txt in a tmux window named b1 and continue to M2 while it runs.

Follow each milestone's acceptance command exactly. Commit after each milestone and
append to PROGRESS.md. Hard gate: the P3 main batch must be launched by 15:00 PT; if
you will miss it, apply the cut order in docs/MILESTONES.md and say so in PROGRESS.md.
```

## Session B — core (M1 -> M6 -> M7)

```
Read CLAUDE.md, then docs/SPEC.md, docs/ARCHITECTURE.md, docs/INTERFACES.md, docs/EVAL.md
and docs/MILESTONES.md. You are Session B: you own M1, M6, M7. Session A owns the
harness adapter, worker and guards' Docker code (p2o/harness.py, p2o/worker.py, p2o/grade.py);
do not edit those files.

M1: read all of p2o/ and tests/, run pytest -q, fix any failure honestly, then add the
tests listed in M1. Next, build M6 against fake data: generate a synthetic summary.csv
with the fake harness (python -m p2o.cli batch --fake ...; python -m p2o.cli grade --fake ...;
python -m p2o.cli summarize) and make scripts/analyze.py produce every output in
docs/EVAL.md §3. Then M7: README quickstart and scripts/trace.py polish.
When done, ask in PROGRESS.md what Session A needs and help with M3 tests.
```

## Check-in prompts (paste when you return)

- `Summarize PROGRESS.md, the state of every tmux window, budget (python -m p2o.cli budget), and what is blocked. Then continue.`
- `Run python -m p2o.cli summarize && python scripts/analyze.py results/summary.csv and show me table_main and table_guards.`
