# SPEC — Prompt2Own midway build

## 1. Goal

By 2026-11-06 23:59 PT, run Prompt2Own end to end on a fixed 30-task CyberGym-E2E sample
and produce comparable, graded results for **B1** and **P3** (required), **B2** (optional),
**P0** (only if B2 is done).

Research question served: does gating stage transitions on executable evidence, checked
by guards the worker cannot reach, reduce false success and raise true success on
end-to-end vulnerability repair, compared with an unconstrained agent (B1) and with the
same workflow given only as a prompt (B2)?

## 2. Scope

In scope:
- Fixed linear stage graph RCA -> PoC -> Patch with bounded retries on rejection.
- Workers: headless Claude Code (`claude -p`) pointed at a low-cost model via an
  Anthropic-compatible endpoint (`ANTHROPIC_BASE_URL`).
- Guards: `null`, `exec_poc`, `exec_patch`; `llm_judge` as an interface stub only.
- Append-only evidence ledger + event log; single source for analysis.
- Official CyberGym-E2E grading (S1-S4) after each run, invisible to workers and guards.

Out of scope (final report): LLM planner/branching, P1/P2 runs, per-guard ablations,
decoy study, guard-noise study, Codex workers, multiple seeds, exploit stage, other benchmarks.

## 3. Configurations

| Id | Priority | Mode | Guards (rca / poc / patch) | Tests |
| --- | --- | --- | --- | --- |
| B1 | required | single_session | — | Off-the-shelf agent. Only change vs official: a one-paragraph suffix asking for `claim.json`. |
| P3 | required | stage_graph | null / exec_poc / exec_patch | Full system. |
| B2 | optional | single_session | — | Same stage text as P3's templates, concatenated, plus "verify each step yourself". |
| P0 | if time | stage_graph | null / null / null | Decomposition without verification. |

Everything else is identical across configs: model, provider, caps, task list, seed,
container image, firewall. Configs live in `configs/*.yaml` (schema in INTERFACES.md §6).

## 4. Environment

- Host: vast.ai **VM** instance (`vms_enabled=true`, template "Ubuntu 22.04 VM"),
  >= 32 vCPU, >= 128 GB RAM, 800 GB-1 TB disk (fixed at creation), >= 1 Gbps down.
  Standard vast.ai instances are Docker containers and cannot run the harness.
- Must pass: `sudo sysctl -w vm.mmap_rnd_bits=28 && docker run --rm hello-world`.
- Setup: `scripts/vast_setup.sh` (installs Docker deps, uv, Node + Claude Code, clones harness).
- Model: cheap open-weight models via OpenRouter's Anthropic-compatible endpoint
  `https://openrouter.ai/api` (key in `OPENROUTER_API_KEY`). Pilot `z-ai/glm-5.3-flash` vs
  `deepseek/deepseek-v4.1-flash` on the 3 dev tasks; then freeze one model for all configs.
  Exact slugs only (no `~...-latest` aliases, no `:batch` variants). Every Claude Code model
  alias (haiku/sonnet/opus/subagent) is pinned to the frozen model by `p2o/worker.py`.

## 5. Budget

- Total API budget: **$150**. Enforced by `p2o/budget.py` (`results/budget.json`).
- Per run (all configs equal): 45 min wall clock; token cap `P2O_TOKEN_CAP` set after the
  M4 pilot so that a run costs <= $0.75 at the frozen model's prices.
- Estimated: 33 tasks x 3 configs + pilots ~ 100 runs ~ $75. Remainder = reruns / P0.
- Prices: per-model table `prices_per_mtok` in `configs/*.yaml`, taken from
  `https://openrouter.ai/api/v1/models`. OpenRouter may route to upstream providers with
  different prices; re-check the table at the M4 freeze and cross-check the OpenRouter
  activity page against `p2o.cli budget` after the pilot.

## 6. Tasks

- 30 main + 3 dev tasks sampled once by `scripts/sample_tasks.py --seed 329`
  (one task per project, stratified by project). Dev tasks are for tuning only and never reported.
- Pull images for these 33 tasks only.
- A main task that fails to build/start in the *official* harness is replaced by the next
  task in the shuffled order; replacement logged in `tasks/sample_manifest.json`.

## 7. Deliverables tonight

1. Repo with README that reproduces one dev task from scratch.
2. `results/summary.csv` + `results/figs/*` (see EVAL.md).
3. One P3 dev-task trace suitable for the demo video (ledger timeline + guard verdicts).
