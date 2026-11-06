# EVAL

## 1. Metrics

| Metric | Definition (over tasks with status != infra_error) |
| --- | --- |
| S1..S4 | Official grader stages; S4 = true success |
| Claimed success | Final `claim.json` says `done: true` (patch stage for P*, whole task for B*) |
| FSR | (claimed and not S4) / claimed |
| Check-pass gap | (S3 and not S4) / S3 — needs no claim |
| Stage FSR (P3) | PoC stage: claimed done and not S1; patch stage: claimed done and not S4 |
| Guard precision/recall | exec_poc final verdict vs S1; exec_patch final verdict vs S4 |
| Cost per true success | sum(usd) / count(S4) |
| Minutes | median wall clock |

Guard precision = P(grader true | guard accepted); recall = P(guard accepted | grader true).
Computed over runs where the guard was reached.

## 2. Statistics

- Wilson 95% CI for every rate.
- Paired comparison on shared tasks: McNemar exact test on S4 (and on claimed-but-false).
- Label as preliminary: 30 tasks, 1 seed, low-cost model, 45 min cap (paper: $10 / 90 min).

## 3. Outputs (`python scripts/analyze.py results/summary.csv --out results/figs/`)

| File | Content |
| --- | --- |
| `table_main.csv`, `table_main.tex` | Per config: n, S1-S4 (with CI), claimed, FSR, check-pass gap, USD, cost/S4, median min |
| `fig_funnel.pdf` | S1->S4 funnel per config, grouped bars |
| `table_guards.csv`, `.tex` | P3 per guard: reached, accepts, rejects, precision, recall |
| `table_paired.csv` | B1 vs P3 (and B2 vs P3): both/only-A/only-B/neither on S4, McNemar p |
| `fig_retries.pdf` | Attempts per stage in P3, split by final S4 |
| `failures.md` | Tasks where configs disagree: per-config outcome, P3 rejection reasons in order |

## 4. Reference numbers (paper, 615 tasks, $10 / 90 min)

Opus 4.5 + Claude Code: patch-only 82.3; S1 24.9; S2 21.9; S3 19.2; S4 7.6
(https://arxiv.org/html/2606.04460v2, Table 3). Use only as context; our setup differs.
