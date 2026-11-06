# CLAUDE.md — Prompt2Own

Prompt2Own is a research prototype for CS329Z. It runs vulnerability-repair tasks from
the CyberGym-E2E benchmark (C/C++, OSS-Fuzz projects) as a fixed stage graph
(RCA -> PoC -> Patch). Each stage is a fresh headless Claude Code session. Isolated
guards gate each transition on executable evidence. We compare it against plain
Claude Code (B1) and Claude Code given the same workflow as a prompt (B2).

**Deadline: 2026-11-06 23:59 PT.** Optimize for a working, measured system, not polish.

## Read first

| File | What it is |
| --- | --- |
| `docs/SPEC.md` | Research goal, scope, configurations, budget. The contract. |
| `docs/ARCHITECTURE.md` | Trust zones, control flow, module responsibilities. |
| `docs/INTERFACES.md` | Every data model, file format and directory layout. |
| `docs/HARNESS.md` | How we plug into the official CyberGym-E2E harness. Partly TODO: you fill it in. |
| `docs/MILESTONES.md` | Ordered milestones with acceptance commands. Work strictly in this order. |
| `docs/EVAL.md` | Metrics, statistics and the exact analysis outputs. |
| `PROGRESS.md` | Running log. Append one entry per milestone. |

The Python code in `p2o/` is a typed skeleton. Modules marked `# STATUS: implemented`
work and are tested. Modules marked `# STATUS: stub` raise `NotImplementedError` with a
pointer to the milestone that fills them. Do not change a public signature in
`p2o/types.py` or a Protocol in `p2o/harness.py` / `p2o/worker.py` / `p2o/guards/base.py`
without updating `docs/INTERFACES.md` in the same commit.

## Commands

```bash
uv venv && uv pip install -e '.[dev]'      # or: python -m venv .venv && pip install -e '.[dev]'
pytest -q                                   # unit tests, no Docker, must always pass
python -m p2o.cli run   --config configs/p3.yaml --task <task_id>
python -m p2o.cli batch --config configs/p3.yaml --tasks tasks/main30.txt --parallel 4
python -m p2o.cli grade --config configs/p3.yaml --tasks tasks/main30.txt
python -m p2o.cli budget                     # spend so far vs. cap
python scripts/analyze.py results/summary.csv --out results/figs/
```

Long jobs always run under tmux: `tmux new -s b1 'python -m p2o.cli batch ... 2>&1 | tee logs/b1.log'`.
Batches are resumable: a task with a `run_end` event is skipped.

## How to work

1. Pick the first milestone in `docs/MILESTONES.md` that is not done in `PROGRESS.md`.
2. Implement only what it lists. Run its acceptance command. Run `pytest -q`.
3. Commit with message `M<n>: <summary>`. Append to `PROGRESS.md`: done / verified how / open issues.
4. If blocked > 30 min, write the blocker in `PROGRESS.md` and move to the next milestone
   that does not depend on it. Never silently work around a blocker by weakening a rule below.

## Hard rules (breaking any of these invalidates the experiment)

Never:
- Modify, monkeypatch, wrap-to-override or bypass the official CyberGym-E2E grader.
- Let a worker or a guard see ground truth: the ground-truth PoC, fix commits, `-fix` images,
  `results/grades/`, the harness's grading code, or any other task's or run's files.
- Import from `tests/` into `p2o/`. Tests may use dev-task ground truth as controls; runtime code may not.
- Delete, skip, xfail or loosen a test to make it pass. If a test is wrong, say so in PROGRESS.md and fix it honestly.
- Edit `tasks/main30.txt` or `tasks/dev.txt` after the first main run. Never tune prompts or guards on main tasks.
- Change a config after its main batch has started (create a new config id instead).
- Give workers network access beyond the model endpoint. Keep the official firewall on.
- Expose the VM, the harness or any container port to the public internet.
- Launch a batch without `python -m p2o.cli budget` showing enough remaining budget.

Always:
- Remove leaked artifacts from task containers before a worker starts (see `docs/HARNESS.md`, "Leak cleanup").
- Run each guard check in a fresh container that the worker never touched.
- Record model id, provider, prompt hash and config hash in every run (the orchestrator does this; keep it that way).
- Reuse the harness's own build / run / test commands instead of reimplementing them.
- Keep the worker's task identical to the benchmark's task. This project studies verification,
  not new attack techniques; do not add offensive capability beyond what the benchmark asks for.

## Conventions

- Python 3.11, pydantic v2, typer CLI, no other frameworks. Keep dependencies minimal.
- All run outputs under `results/`; logs under `logs/`. Both are gitignored except
  `results/summary.csv`, `results/figs/`, and `results/runs/**/events.jsonl|ledger.jsonl`.
- Times in UTC ISO-8601 in logs. Money in USD floats, computed from token counts and the
  price table in the config (do NOT trust Claude Code's `total_cost_usd` when using a
  non-Anthropic endpoint; it is priced at Anthropic rates).
- Small, boring code. No async unless the batch runner needs it; prefer `concurrent.futures`.
