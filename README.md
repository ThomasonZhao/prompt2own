# Prompt2Own

A multi-agent system for end-to-end vulnerability repair on CyberGym-E2E in which
stage transitions (root cause -> reproduction -> patch) are gated by executable guards
that the worker agents cannot reach. CS329Z (Stanford, Fall 2026) course project.

## Layout

See `docs/ARCHITECTURE.md`. Configurations: `configs/b1.yaml` (Claude Code as shipped),
`configs/b2.yaml` (workflow as a prompt), `configs/p0.yaml` (stages, no guards),
`configs/p3.yaml` (stages + executable guards).

## Quickstart (no Docker, fake harness)

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e '.[dev]'
pytest -q
echo "demo/fake_1,demo" > /tmp/fake.txt
python -m p2o.cli batch --config configs/p3.yaml --tasks /tmp/fake.txt --fake
python -m p2o.cli grade --config configs/p3.yaml --tasks /tmp/fake.txt --fake
python -m p2o.cli summarize && python scripts/analyze.py results/summary.csv
python scripts/trace.py results/runs/p3/demo__fake_1
```

## Real runs (Linux VM with Docker)

1. Requirements: Docker, `sysctl vm.mmap_rnd_bits=28`, ~800 GB disk, 32+ cores.
   `bash scripts/vast_setup.sh` does the setup on a vast.ai VM instance.
2. `cp .env.example .env` and fill in `OPENROUTER_API_KEY`, `P2O_MODEL` (an OpenRouter slug
   listed in `prices_per_mtok` of `configs/*.yaml`) and `HF_TOKEN`.
3. Sample tasks: `python scripts/sample_tasks.py --seed 329` (task lists are committed in `tasks/`).
4. One task: `python -m p2o.cli run --config configs/p3.yaml --task <task_id>`
5. Evaluation: `python -m p2o.cli batch --config configs/<cfg>.yaml --tasks tasks/main30.txt --parallel 4`,
   then `python -m p2o.cli grade ...`, `python -m p2o.cli summarize`, `python scripts/analyze.py results/summary.csv`.

(M7 completes this section with exact, tested commands.)
