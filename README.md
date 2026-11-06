# Prompt2Own

A multi-agent system for end-to-end vulnerability repair on CyberGym-E2E in which
stage transitions (root cause -> reproduction -> patch) are gated by executable guards
that the worker agents cannot reach. CS329Z (Stanford, Fall 2026) course project.

Configurations: `configs/b1.yaml` (Claude Code as shipped), `configs/b2.yaml` (the workflow
given as a prompt), `configs/p0.yaml` (stages, no guards), `configs/p3.yaml` (stages plus
executable guards). Design: `docs/ARCHITECTURE.md`. File formats: `docs/INTERFACES.md`.
Metrics: `docs/EVAL.md`.

## Quickstart 1: no Docker, no API key (about 1 minute)

This uses the fake harness and worker. Everything is written under `results/fake/`, which has
its own budget file. `--fake` refuses to write into the real `results/`.

```bash
git clone git@github.com:ThomasonZhao/prompt2own.git && cd prompt2own
uv venv --python 3.11 && . .venv/bin/activate && uv pip install -e '.[dev]'
# or: python3.11 -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
pytest -q                                                    # unit tests, all green

# one P3 run: rca accept -> poc reject (no_sanitizer_report) -> poc retry accept -> patch accept
python -m p2o.cli run --config configs/p3.yaml --task demo/fake_1 --fake
echo "demo/fake_1" > /tmp/one.txt
python -m p2o.cli grade --config configs/p3.yaml --tasks /tmp/one.txt --fake
python scripts/trace.py results/fake/runs/p3/demo__fake_1     # demo timeline

# full analysis pipeline on 30 synthetic tasks x 4 configs -> results/fake/figs/
bash scripts/fake_pipeline.sh
```

## Quickstart 2: one real dev task (Linux VM with Docker)

The harness needs a real VM, not a container. On vast.ai, use a VM instance
(`vms_enabled=true`, template "Ubuntu 22.04 VM") with at least 32 vCPU, 128 GB RAM and 800 GB disk.

```bash
# 0. setup: kernel/docker checks, uv, node + claude code, venv, harness clone, squid image
git clone git@github.com:ThomasonZhao/prompt2own.git && cd prompt2own
bash scripts/vast_setup.sh
. .venv/bin/activate

# 1. secrets: OPENROUTER_API_KEY, P2O_MODEL (a slug in prices_per_mtok), P2O_TOKEN_CAP, HF_TOKEN
cp .env.example .env && $EDITOR .env
#    (accept the gated dataset's terms on Hugging Face first)

# 2. data + images for the dev task only (task lists are committed in tasks/)
python scripts/fetch_sampled.py --tasks libspng/arvo_14935

# 3. firewall: Squid allowlist + the model endpoint
(cd third_party/cybergym-e2e/scripts && python -m firewall start --domain openrouter.ai)

# 4. check budget, run P3 on the dev task, grade it with the official grader, then trace it
python -m p2o.cli budget
python -m p2o.cli run --config configs/p3.yaml --task libspng/arvo_14935
echo "libspng/arvo_14935,libspng" > /tmp/dev1.txt
python -m p2o.cli grade --config configs/p3.yaml --tasks /tmp/dev1.txt
cat results/grades/p3/libspng__arvo_14935.json               # s1..s4
python scripts/trace.py results/runs/p3/libspng__arvo_14935
```

Success means `results/grades/p3/libspng__arvo_14935.json` exists with `s1` to `s4`. A run is
capped at 45 min and $0.75.

## Full evaluation

Run long jobs under tmux. Batches can be resumed: a task that already has a `run.json` is skipped.

```bash
python -m p2o.cli budget                                     # never launch without enough remaining
tmux new -s p3 'python -m p2o.cli batch --config configs/p3.yaml --tasks tasks/main30.txt --parallel 4 2>&1 | tee logs/p3.log'
python -m p2o.cli grade --config configs/p3.yaml --tasks tasks/main30.txt     # same for b1 / b2 / p0
python -m p2o.cli summarize                                  # -> results/summary.csv
python scripts/analyze.py results/summary.csv --out results/figs/
```

`analyze.py` writes every file listed in `docs/EVAL.md` §3:

| File | Content |
| --- | --- |
| `table_main.{csv,tex}` | S1 to S4, claimed success, FSR and check-pass gap, each with a Wilson CI, plus cost |
| `table_guards.{csv,tex}` | Guard precision and recall, and stage FSR |
| `table_paired.csv` | McNemar tests |
| `fig_funnel.pdf`, `fig_retries.pdf` | Figures |
| `failures.md` | Tasks where the configs disagree |

By default it reports only the tasks in `tasks/main30.txt`, so dev pilot runs are left out.

## Layout

```
p2o/            orchestrator, guards, harness adapter, worker, ledger, budget, CLI
p2o/stages/     prompt templates (common + per stage, B2 workflow, claim suffix)
configs/        one YAML per configuration (do not edit after its main batch starts)
scripts/        analyze.py, trace.py, fake_pipeline.sh, sample_tasks.py, fetch_sampled.py, vast_setup.sh
tasks/          dev.txt, main30.txt, sample_manifest.json (frozen)
results/        runs/<config>/<task>/{run.json,events.jsonl,ledger.jsonl,...}, grades/, summary.csv, figs/
```
