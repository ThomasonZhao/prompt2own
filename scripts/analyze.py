"""All tables/figures in docs/EVAL.md §3 from results/summary.csv.

Usage: python scripts/analyze.py results/summary.csv --out results/figs/
# STATUS: implemented
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from statsmodels.stats.proportion import proportion_confint


def ci(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    lo, hi = proportion_confint(k, n, method="wilson")
    return float(lo), float(hi)


def _rate(num: int, den: int) -> float:
    return num / den if den else float("nan")


def main_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["status"] != "infra_error"].copy()
    for c in ("s1", "s2", "s3", "s4", "claimed_success"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    rows = []
    for cfg, g in df.groupby("config", sort=True):
        n = len(g)
        row = {"config": cfg, "n": n}
        for s in ("s1", "s2", "s3", "s4"):
            k = int(g[s].sum())
            lo, hi = ci(k, n)
            row[s], row[f"{s}_lo"], row[f"{s}_hi"] = _rate(k, n), lo, hi
        claimed = int(g["claimed_success"].sum())
        false = int(((g["claimed_success"] == 1) & (g["s4"] == 0)).sum())
        s3 = int(g["s3"].sum())
        gap = int(((g["s3"] == 1) & (g["s4"] == 0)).sum())
        row.update({
            "claimed": _rate(claimed, n), "fsr": _rate(false, claimed),
            "check_pass_gap": _rate(gap, s3), "usd_total": float(g["usd"].sum()),
            "usd_per_s4": _rate(float(g["usd"].sum()), int(g["s4"].sum())),
            "median_minutes": float(g["minutes"].median()),
        })
        rows.append(row)
    return pd.DataFrame(rows)


def guard_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for guard, col, truth in (("exec_poc", "final_poc_guard_accept", "s1"),
                              ("exec_patch", "final_patch_guard_accept", "s4")):
        for cfg, g in df.groupby("config"):
            g = g[pd.to_numeric(g[col], errors="coerce").notna()]
            if g.empty or (g[f"{guard.split('_')[1]}_guard_accepts"].sum() + g[f"{guard.split('_')[1]}_guard_rejects"].sum()) == 0:
                continue
            acc = pd.to_numeric(g[col]).astype(int)
            t = pd.to_numeric(g[truth], errors="coerce").fillna(0).astype(int)
            tp = int(((acc == 1) & (t == 1)).sum())
            rows.append({"config": cfg, "guard": guard, "reached": len(g),
                         "accepts": int(acc.sum()), "rejects": int((acc == 0).sum()),
                         "precision": _rate(tp, int(acc.sum())), "recall": _rate(tp, int(t.sum()))})
    return pd.DataFrame(rows)


def paired_table(df: pd.DataFrame, ref: str = "p3") -> pd.DataFrame:
    from statsmodels.stats.contingency_tables import mcnemar
    piv = df.pivot_table(index="task_id", columns="config", values="s4", aggfunc="first")
    rows = []
    if ref not in piv:
        return pd.DataFrame()
    for other in [c for c in piv.columns if c != ref]:
        p = piv[[ref, other]].dropna().astype(int)
        both = int(((p[ref] == 1) & (p[other] == 1)).sum())
        only_ref = int(((p[ref] == 1) & (p[other] == 0)).sum())
        only_other = int(((p[ref] == 0) & (p[other] == 1)).sum())
        neither = int(((p[ref] == 0) & (p[other] == 0)).sum())
        pval = mcnemar([[both, only_ref], [only_other, neither]], exact=True).pvalue
        rows.append({"a": ref, "b": other, "n": len(p), "both": both, f"only_{ref}": only_ref,
                     "only_other": only_other, "neither": neither, "mcnemar_p": pval})
    return pd.DataFrame(rows)


def funnel(tab: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    stages = ["s1", "s2", "s3", "s4"]
    fig, ax = plt.subplots(figsize=(6, 3.2))
    w = 0.8 / max(len(tab), 1)
    for i, (_, r) in enumerate(tab.iterrows()):
        xs = [j + i * w for j in range(4)]
        ys = [r[s] * 100 for s in stages]
        err = [[(r[s] - r[f"{s}_lo"]) * 100 for s in stages], [(r[f"{s}_hi"] - r[s]) * 100 for s in stages]]
        ax.bar(xs, ys, w, yerr=err, capsize=2, label=r["config"].upper())
    ax.set_xticks([j + w * (len(tab) - 1) / 2 for j in range(4)], ["S1 PoC", "S2 PoC fixed", "S3 tests", "S4 true fix"])
    ax.set_ylabel("tasks (%)")
    ax.legend(frameon=False)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out)


def retries(df: pd.DataFrame, out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    g = df[df["config"] == "p3"]
    if g.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(6, 2.6), sharey=True)
    for ax, col in zip(axes, ("attempts_poc", "attempts_patch")):
        for s4, lab in ((1, "S4 true"), (0, "S4 false")):
            v = pd.to_numeric(g[g["s4"].astype(str) == str(s4)][col], errors="coerce").dropna()
            ax.hist(v, bins=[0.5, 1.5, 2.5, 3.5], alpha=0.6, label=lab)
        ax.set_title(col.replace("attempts_", "") + " attempts")
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out)


def failures(df: pd.DataFrame, runs_root: Path, out: Path) -> None:
    import json
    piv = df.pivot_table(index="task_id", columns="config", values="s4", aggfunc="first")
    lines = ["# Tasks where configurations disagree on S4\n"]
    for tid, r in piv.iterrows():
        if r.dropna().nunique() <= 1:
            continue
        lines.append(f"## {tid}\n" + ", ".join(f"{c}: S4={int(v)}" for c, v in r.dropna().items()))
        ev = runs_root / "p3" / tid.replace("/", "__") / "events.jsonl"
        if ev.exists():
            for e in map(json.loads, ev.read_text().splitlines()):
                if e.get("event") == "stage_attempt" and e.get("verdict"):
                    lines.append(f"- {e['stage']}#{e['attempt']}: {e['verdict']['reason']}")
        lines.append("")
    out.write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("summary", type=Path)
    ap.add_argument("--out", type=Path, default=Path("results/figs"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(a.summary)
    tab = main_table(df)
    tab.to_csv(a.out / "table_main.csv", index=False)
    tab.to_latex(a.out / "table_main.tex", index=False, float_format="%.2f")
    gt = guard_table(df)
    gt.to_csv(a.out / "table_guards.csv", index=False)
    gt.to_latex(a.out / "table_guards.tex", index=False, float_format="%.2f")
    paired_table(df).to_csv(a.out / "table_paired.csv", index=False)
    funnel(tab, a.out / "fig_funnel.pdf")
    retries(df, a.out / "fig_retries.pdf")
    failures(df, a.summary.parent / "runs", a.out / "failures.md")
    print(tab.to_string(index=False))


if __name__ == "__main__":
    main()
