# Prompt2Own

**Does enforcing a workflow with executable verification make coding agents better at end-to-end vulnerability repair?**

Prompt2Own runs vulnerability-repair tasks from [CyberGym-E2E](https://github.com/sunblaze-ucb/cybergym-e2e)
(C/C++ OSS-Fuzz projects) as a fixed stage graph: **root-cause analysis → proof-of-concept → patch**.
Each stage is a fresh headless Claude Code session. An orchestrator moves to the next stage only when an
*isolated guard* accepts executable evidence. The guard runs in a fresh container the worker never touched.
We compare this system against the same agent with no workflow, and against the same agent given the workflow as a prompt.
All runs are graded by the benchmark's official grader, unmodified.

| Config | What the worker gets | Stages enforced in code | Guards |
| --- | --- | --- | --- |
| **B1** | the official CyberGym-E2E prompt, one session | – | – |
| **B2** | B1 plus the RCA → PoC → patch workflow as a prompt, one session | – | – |
| **P0** | one session per stage, no verification (ablation; not run in the main study) | ✓ | – |
| **P3** | one session per stage, transitions gated by guards | ✓ | `exec_poc`, `exec_patch` |

The guards (`p2o/guards/`):
- **`exec_poc`** accepts a PoC only if it produces a sanitizer report in a fresh vulnerable container, and one
  of the top-5 stack frames matches the function or file named in the RCA.
- **`exec_patch`** accepts a patch only if it applies to the pristine tree, the project rebuilds, the worker's
  verified PoC no longer crashes, and the project's tests pass.

## Results

30 main tasks × 3 configurations, one seed, model `z-ai/glm-5.3-flash`. Each run is capped at 45 min and $0.75.
Official stages: **S1** the agent's PoC crashes the vulnerable build; **S2** the agent's PoC no longer crashes with the
agent's patch; **S3** the project tests pass with the patch; **S4** the *ground-truth* PoC no longer crashes with the patch
(the patch fixes the target bug). **FSR** (false-success rate) is P(S4 fails | the agent claimed success).
Brackets are Wilson 95% CIs.

| Config | S1 | S2 | S3 | **S4** | Claimed | **FSR** | USD / S4 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B1 | 0.77 | 0.70 | 0.70 | 0.43 [0.27, 0.61] | 0.67 | 0.40 [0.22, 0.61] | 0.42 |
| B2 | 0.73 | 0.73 | 0.73 | **0.53** [0.36, 0.70] | 0.73 | **0.27** [0.13, 0.48] | **0.29** |
| P3 | 0.70 | 0.57 | 0.57 | 0.33 [0.19, 0.51] | 0.60 | 0.44 [0.25, 0.66] | 0.57 |

Per stratum (S4 / FSR): easy (n=20): B1 0.25 / 0.58, B2 0.45 / 0.31, P3 0.25 / 0.55. Uniform (n=10): B1 0.80 / 0.13,
B2 0.70 / 0.22, P3 0.50 / 0.29.

**Paired S4, McNemar (n=30):**

| Pair | Both pass | Only first passes | Only second passes | p |
| --- | --- | --- | --- | --- |
| P3 vs B1 | 6 | 4 | 7 | 0.55 |
| P3 vs B2 | 8 | 2 | 8 | 0.11 |
| B2 vs B1 | 11 | 5 | 2 | 0.45 |

**P3 guards against the official grader:**

| Guard | Reached | Accepted | Precision | Recall |
| --- | --- | --- | --- | --- |
| `exec_poc` (vs S1) | 26 | 18 | 1.00 | 0.86 |
| `exec_patch` (vs S4) | 18 | 17 | 0.59 | 1.00 |

**Findings.**
- No difference is significant at n = 30. The workflow given as a prompt (B2) has the best point estimates on S4,
  FSR and cost per solved task. The enforced, guarded graph (P3) does not beat either baseline.
- `exec_poc` never accepted a PoC that the grader rejected. All 7 `exec_patch` false accepts pass S1–S3 and fail only S4.
- In each of those 7 cases, the worker reproduced and correctly fixed a *real but different* memory-safety bug. The
  ground-truth PoC crashes at another site: add vs. multiply path, encode vs. decode, another parser.
- The guards verify that a run is self-consistent: the RCA, the PoC's crash and the patch agree. They cannot check that
  the worker found the *target* bug, since only the ground-truth PoC (S4) can establish that, and guards may not see it.
  Per-task analysis: [`results/figs/false_accepts.md`](results/figs/false_accepts.md).
- All outputs are in [`results/figs/`](results/figs/): `table_main`, `table_guards` and `table_paired` (CSV and LaTeX),
  `table_paired_b2_vs_b1.csv`, `fig_funnel.pdf`, `fig_retries.pdf`, and `failures.md` (tasks where configs disagree).

## Reproducing

### 1. Tables and figures from the committed run records (about 1 minute, no Docker, no API key)

`results/runs/<config>/<task>/{run.json,events.jsonl,ledger.jsonl}` and `results/grades/<config>/<task>.json`
hold every run's record and official grade.

```bash
uv venv --python 3.11 && . .venv/bin/activate && uv pip install -e '.[dev]'
pytest -q                                             # unit tests (fake harness + fake worker)
python -m p2o.cli summarize                           # -> results/summary.csv
python scripts/analyze.py results/summary.csv --out results/figs/
python scripts/trace.py results/runs/p3/libspng__arvo_14935   # timeline of one P3 run
```

### 2. The whole pipeline on synthetic tasks (no Docker, no API key)

```bash
python -m p2o.cli run --config configs/p3.yaml --task demo/fake_1 --fake   # writes under results/fake/ only
bash scripts/fake_pipeline.sh                         # 30 synthetic tasks x 4 configs -> results/fake/figs/
```

### 3. Real runs

You need an Ubuntu 22.04 **VM** (the harness does not run inside a container) with Docker; we used 30–61 vCPU,
≥128 GB RAM and ≥500 GB disk. You also need an OpenRouter key and a Hugging Face token with the CyberGym-E2E
dataset terms accepted.

```bash
bash scripts/setup.sh                                  # sysctl, Docker check, uv, Claude Code, harness @ d0ae0f0, tests
cp .env.example .env && $EDITOR .env                   # OPENROUTER_API_KEY, HF_TOKEN
python scripts/fetch_sampled.py                        # data + images for the 33 frozen tasks only
(cd third_party/cybergym-e2e/scripts && python -m firewall start --domain openrouter.ai)

python -m p2o.cli budget                               # global spend vs. P2O_BUDGET_USD
python -m p2o.cli batch --config configs/p3.yaml --tasks tasks/main30.txt --parallel 3   # resumable
python -m p2o.cli grade --config configs/p3.yaml --tasks tasks/main30.txt                # official grader
```

Repeat the last two commands for `b1` and `b2`, then follow step 1. Every run records the model id, provider, config hash
and templates hash. With no `.env` overrides, the committed configs reproduce the recorded hashes
(`b1 f58ddb8f09a3`, `b2 21157656666c`, `p3 fb41ddb16869`; templates `9d83d8024cc9`).

## Protocol

**Task sampling** (pre-registered before any run; it uses task metadata only, never model results). The index has
920 tasks across 139 projects; seed 329; at most one task per project. A task is *easy* iff (E1) the ground-truth fix touches one file,
(E2) it changes ≤ 20 lines, and (E3) the task builds in ≤ 10 min in the official harness. The main set is 20 easy tasks
plus 10 drawn uniformly at random, and a 3-task dev set (2 easy + 1 uniform) was the only data used for tuning. Tasks that failed E3
were replaced from the same stratum's reserve in a fixed order. One replacement happened (ffmpeg → libidn2, build time 19.9 min).
See `tasks/sample_manifest.json` and `scripts/sample_tasks.py`. Pooled numbers mix strata and are **not representative of
the full benchmark**.

**Isolation.**
- **Workers** never see ground truth: the official leak cleanup removes the prebuilt `/src` and `/out`, the
  ground-truth PoC and the repository history, and `/data` is emptied. Our stage templates never include the task id (regression-tested).
- **Network:** workers reach only the model endpoint, through the official Squid firewall.
- **Guards** run every check in a fresh container built from a vulnerable image that no worker touched. PoCs run with
  `--network none`, and builds and tests use the harness's own scripts and its `apply_patch`.
- **Grading** goes through `run_agent.run_final_validation` at harness commit `d0ae0f0`, called unmodified
  (`p2o/grade.py`). It runs only after a run is finished.

**Model and cost.** One model for every config: `z-ai/glm-5.3-flash` via OpenRouter's Anthropic-compatible endpoint,
with every Claude Code model alias pinned to it. USD is computed from metered token counts and the price table in
`configs/*.yaml`, frozen before any main run. It is conservative: 7–60% above what OpenRouter billed for the same runs.
The reported runs, plus one dev smoke run, cost $16.07 at table prices.

## Deviations and disclosures

- **B1/B2 keep the official `/scripts/validate.py`** in the worker container, because the official prompt tells the agent to use it.
  It cannot run S4, since the container holds no ground-truth PoC. P0/P3 workers have `/scripts` removed.
- **S1 without a patch:** a run that delivers a PoC but no patch is still graded for S1. The official loop would score it
  S1 = false; that convention is kept in each grade file as `raw.official_loop_s1`.
- **Dev-set tuning:** before the main runs, P3's prompts gained a statement of the 15-min stage limit, and the RCA stage got 2 attempts.
  Both changes were made on the dev set only.
- **Re-run after host loss:** the original host was lost during the main batches. All main runs were restarted from
  scratch on a new host with identical code, configs, tasks and model. Guard images were rebuilt, every easy task still met E3
  (max 5.9 min), and no new replacements were made.
- **Concurrency differs:** B1 and P3 ran concurrently (4 + 3 runs at a time); B2 ran afterwards at 6 at a time on an otherwise idle host.
  Per-run caps were identical, but wall-clock minutes are not comparable across configs.
- **Not run:** P0 (stages without guards) and repeated seeds.

## Layout

```
p2o/               orchestrator (stage graph + single session), guards, harness adapter, Claude Code worker,
                   evidence ledger, budget, CLI
p2o/stages/        prompt templates (hashed into every run record; do not edit)
configs/           b1, b2, p0, p3
tasks/             dev.txt, main30.txt, sample_manifest.json (frozen)
scripts/           analyze.py, trace.py, sample_tasks.py, build_check.py (sampling-time E3 check; do not rerun),
                   fetch_sampled.py, fake_pipeline.sh, setup.sh
tests/             unit tests; tests/test_guards_docker.py needs Docker + the harness (pytest -m docker)
results/           runs/, grades/, summary.csv, figs/
```

## License

MIT (see `LICENSE`). CyberGym-E2E and its dataset are under their own licenses.
