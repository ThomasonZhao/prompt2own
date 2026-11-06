"""All tables/figures in docs/EVAL.md §3 from results/summary.csv.

Usage: python scripts/analyze.py results/summary.csv --out results/figs/
       python scripts/analyze.py results/fake/summary.csv --out results/fake/figs --all-tasks

Metrics use rows with status != infra_error that have a grade (s1..s4 present); both
exclusions are reported as counts. By default rows are restricted to tasks/main30.txt so
dev-task pilot runs (M4) are never reported. Every rate carries a Wilson 95% CI.
# STATUS: implemented
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from statsmodels.stats.proportion import proportion_confint

CONFIG_ORDER = ["b1", "b2", "p0", "p3"]
# Fixed config -> hue (validated categorical slots; color follows the config, never its rank).
COLORS = {"b1": "#2a78d6", "p3": "#eb6834", "b2": "#1baf7a", "p0": "#eda100"}
OTHER = "#8a8984"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
GUARDS = (("exec_poc", "poc", "s1"), ("exec_patch", "patch", "s4"))   # guard, stage, grader truth
PRELIM = "Preliminary: {n} tasks, 1 seed, low-cost model, 45 min / \\$0.75 cap (paper: \\$10 / 90 min)."
OUTPUTS = ["table_main.csv", "table_main.tex", "fig_funnel.pdf", "table_guards.csv", "table_guards.tex",
           "table_paired.csv", "fig_retries.pdf", "failures.md"]


# ------------------------------------------------------------------ helpers

def ci(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    lo, hi = proportion_confint(k, n, method="wilson")
    return float(lo), float(hi)


def _rate(num: float, den: float) -> float:
    return num / den if den else float("nan")


def _put(row: dict, name: str, k: int, n: int) -> None:
    """row[name] = k/n with Wilson CI in name_lo / name_hi."""
    row[name] = _rate(k, n)
    row[f"{name}_lo"], row[f"{name}_hi"] = ci(k, n)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def _configs(df: pd.DataFrame) -> list[str]:
    present = list(dict.fromkeys(df["config"]))
    return [c for c in CONFIG_ORDER if c in present] + sorted(c for c in present if c not in CONFIG_ORDER)


def metric_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows that count for metrics: not infra_error and graded. s*/claimed as int."""
    g = df[(df["status"] != "infra_error") & _num(df["s1"]).notna()].copy()
    for c in ("s1", "s2", "s3", "s4", "claimed_success"):
        g[c] = _num(g[c]).fillna(0).astype(int)
    return g


# ------------------------------------------------------------------ tables

def main_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for cfg in _configs(df):
        allr = df[df["config"] == cfg]
        g = metric_rows(allr)
        n = len(g)
        row: dict = {"config": cfg, "n": n,
                     "n_infra_error": int((allr["status"] == "infra_error").sum()),
                     "n_ungraded": int(((allr["status"] != "infra_error") & _num(allr["s1"]).isna()).sum())}
        for s in ("s1", "s2", "s3", "s4"):
            _put(row, s, int(g[s].sum()), n)
        claimed = int(g["claimed_success"].sum())
        false = int(((g["claimed_success"] == 1) & (g["s4"] == 0)).sum())
        s3 = int(g["s3"].sum())
        gap = int(((g["s3"] == 1) & (g["s4"] == 0)).sum())
        _put(row, "claimed", claimed, n)
        row["n_claimed"] = claimed
        _put(row, "fsr", false, claimed)
        row["n_false_success"] = false
        _put(row, "check_pass_gap", gap, s3)
        usd = float(g["usd"].sum())
        row.update({"usd_total": usd, "usd_mean": _rate(usd, n),
                    "usd_per_s4": _rate(usd, int(g["s4"].sum())),
                    "median_minutes": float(g["minutes"].median()) if n else float("nan")})
        rows.append(row)
    return pd.DataFrame(rows)


def guard_table(df: pd.DataFrame) -> pd.DataFrame:
    """Per config with executable guards, per guard: final verdict vs grader truth, over runs
    where the guard was reached; plus the stage FSR (claimed done and grader says no)."""
    m = metric_rows(df)
    rows = []
    for cfg in _configs(m):
        c = m[m["config"] == cfg]
        for guard, stage, truth in GUARDS:
            acc_c, rej_c = f"{stage}_guard_accepts", f"{stage}_guard_rejects"
            if acc_c not in c or (_num(c[acc_c]).fillna(0) + _num(c[rej_c]).fillna(0)).sum() == 0:
                continue          # guard not used by this config (null guard / single session)
            calls = _num(c[acc_c]).fillna(0) + _num(c[rej_c]).fillna(0)
            g = c[calls > 0]
            acc = _num(g[f"final_{stage}_guard_accept"]).fillna(0).astype(int) == 1
            t = g[truth] == 1
            tp, fp, fn = int((acc & t).sum()), int((acc & ~t).sum()), int((~acc & t).sum())
            row: dict = {"config": cfg, "guard": guard, "truth": truth.upper(), "reached": len(g),
                         "accepts": int(acc.sum()), "rejects": int((~acc).sum()),
                         "false_accepts": fp, "false_rejects": fn,
                         "checks": int(calls.sum()), "check_rejects": int(_num(c[rej_c]).fillna(0).sum())}
            _put(row, "precision", tp, int(acc.sum()))
            _put(row, "recall", tp, int(t.sum()))
            st = c[_num(c[f"attempts_{stage}"]).fillna(0) > 0]
            cl = _num(st.get(f"claimed_{stage}", pd.Series(dtype=float))).fillna(0).astype(int) == 1
            row["stage_reached"], row["stage_claimed"] = len(st), int(cl.sum())
            _put(row, "stage_fsr", int((cl & (st[truth] == 0)).sum()), int(cl.sum()))
            rows.append(row)
    return pd.DataFrame(rows)


def _mcnemar_p(only_a: int, only_b: int) -> float:
    if only_a + only_b == 0:
        return 1.0
    from statsmodels.stats.contingency_tables import mcnemar
    return float(mcnemar([[0, only_a], [only_b, 0]], exact=True).pvalue)


def paired_table(df: pd.DataFrame, ref: str = "p3") -> pd.DataFrame:
    """ref vs every other config on shared tasks: S4 and false success (claimed and not S4)."""
    m = metric_rows(df)
    m["false_success"] = ((m["claimed_success"] == 1) & (m["s4"] == 0)).astype(int)
    cols = ["a", "b", "metric", "n", "both", "only_a", "only_b", "neither", "mcnemar_p"]
    rows = []
    if ref not in set(m["config"]):
        return pd.DataFrame(columns=cols)
    for other in [c for c in _configs(m) if c != ref]:
        for metric in ("s4", "false_success"):
            piv = m[m["config"].isin([ref, other])].pivot_table(
                index="task_id", columns="config", values=metric, aggfunc="first")
            if other not in piv:
                continue
            p = piv[[ref, other]].dropna().astype(int)
            a, b = p[ref] == 1, p[other] == 1
            oa, ob = int((a & ~b).sum()), int((~a & b).sum())
            rows.append({"a": ref, "b": other, "metric": metric, "n": len(p), "both": int((a & b).sum()),
                         "only_a": oa, "only_b": ob, "neither": int((~a & ~b).sum()),
                         "mcnemar_p": _mcnemar_p(oa, ob)})
    return pd.DataFrame(rows, columns=cols)


def _pct(r, k: str) -> str:
    v = r[k]
    if pd.isna(v):
        return "--"
    return f"{100 * v:.0f} [{100 * r[k + '_lo']:.0f}, {100 * r[k + '_hi']:.0f}]"


def main_tex(tab: pd.DataFrame, path: Path) -> None:
    t = pd.DataFrame({
        "Config": tab["config"].str.upper(), "n": tab["n"],
        **{f"S{i} (%)": [_pct(r, f"s{i}") for _, r in tab.iterrows()] for i in (1, 2, 3, 4)},
        "Claimed (%)": [_pct(r, "claimed") for _, r in tab.iterrows()],
        "FSR (%)": [_pct(r, "fsr") for _, r in tab.iterrows()],
        "Gap (%)": [_pct(r, "check_pass_gap") for _, r in tab.iterrows()],
        "USD": tab["usd_total"].map(lambda v: f"{v:.2f}"),
        "USD/S4": tab["usd_per_s4"].map(lambda v: "--" if pd.isna(v) else f"{v:.2f}"),
        "Min": tab["median_minutes"].map(lambda v: "--" if pd.isna(v) else f"{v:.1f}"),
    })
    n = int(tab["n"].max()) if len(tab) else 0
    cap = ("Main results, rates with Wilson 95\\% CI. FSR = claimed and not S4 over claimed; "
           "Gap = S3 and not S4 over S3. " + PRELIM.format(n=n))
    path.write_text(t.to_latex(index=False, escape=False, caption=cap, label="tab:main",
                               column_format="l" + "r" * (len(t.columns) - 1))
                    .replace("%)", "\\%)"))


def guards_tex(gt: pd.DataFrame, path: Path) -> None:
    if gt.empty:
        path.write_text("% no executable guards in this summary\n")
        return
    t = pd.DataFrame({
        "Config": gt["config"].str.upper(), "Guard": gt["guard"].str.replace("_", "\\_"),
        "Truth": gt["truth"], "Reached": gt["reached"], "Accepts": gt["accepts"], "Rejects": gt["rejects"],
        "Precision (%)": [_pct(r, "precision") for _, r in gt.iterrows()],
        "Recall (%)": [_pct(r, "recall") for _, r in gt.iterrows()],
        "Stage FSR (%)": [_pct(r, "stage_fsr") for _, r in gt.iterrows()],
    })
    cap = ("Guard final verdict vs.\\ official grader over runs where the guard was reached. "
           "Stage FSR = stage claimed done and grader truth false, over stage claims.")
    path.write_text(t.to_latex(index=False, escape=False, caption=cap, label="tab:guards",
                               column_format="lll" + "r" * (len(t.columns) - 3))
                    .replace("%)", "\\%)"))


# ------------------------------------------------------------------ figures

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 8, "axes.edgecolor": INK_2, "axes.labelcolor": INK,
                         "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK,
                         "pdf.fonttype": 42})
    return plt


def _style(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def funnel(tab: pd.DataFrame, out: Path) -> None:
    plt = _plt()
    stages = ["s1", "s2", "s3", "s4"]
    fig, ax = plt.subplots(figsize=(6, 3.0))
    k = max(len(tab), 1)
    w = 0.8 / k
    for i, (_, r) in enumerate(tab.iterrows()):
        xs = [j + (i - (k - 1) / 2) * w for j in range(4)]
        ys = [0 if pd.isna(r[s]) else r[s] * 100 for s in stages]
        err = [[max(ys[j] - r[f"{s}_lo"] * 100, 0) if not pd.isna(r[s]) else 0 for j, s in enumerate(stages)],
               [max(r[f"{s}_hi"] * 100 - ys[j], 0) if not pd.isna(r[s]) else 0 for j, s in enumerate(stages)]]
        ax.bar(xs, ys, w, color=COLORS.get(r["config"], OTHER), edgecolor="white", linewidth=1.5,
               label=f"{r['config'].upper()} (n={int(r['n'])})")
        ax.errorbar(xs, ys, yerr=err, fmt="none", ecolor=INK_2, elinewidth=0.8, capsize=2)
    ax.set_xticks(range(4), ["S1\nPoC crashes", "S2\nPoC fixed", "S3\ntests pass", "S4\ntrue fix"])
    ax.set_ylabel("tasks (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Official grader funnel (Wilson 95% CI); preliminary", fontsize=8, color=INK_2, loc="left")
    ax.legend(frameon=False, ncol=min(k, 4))
    _style(ax)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


def retries(df: pd.DataFrame, out: Path, cfg: str = "p3") -> None:
    """Attempts used per stage in P3 (0 = stage not reached), split by final S4."""
    plt = _plt()
    g = metric_rows(df)
    g = g[g["config"] == cfg]
    fig, axes = plt.subplots(1, 2, figsize=(6, 2.6), sharey=True)
    for ax, stage in zip(axes, ("poc", "patch")):
        att = _num(g[f"attempts_{stage}"]).fillna(0).astype(int) if not g.empty else pd.Series(dtype=int)
        for off, s4, lab, col in ((-0.2, 1, "S4 true", COLORS.get(cfg, OTHER)), (0.2, 0, "S4 false", OTHER)):
            cnt = [int(((att == a) & (g["s4"] == s4)).sum()) for a in range(4)]
            ax.bar([a + off for a in range(4)], cnt, 0.4, color=col, edgecolor="white", linewidth=1.5, label=lab)
        ax.set_xticks(range(4), ["not\nreached", "1", "2", "3"])
        ax.set_title(f"{stage.upper()} stage: attempts used", fontsize=8, loc="left")
        _style(ax)
    axes[0].set_ylabel(f"{cfg.upper()} runs")
    axes[0].legend(frameon=False)
    if g.empty:
        fig.text(0.5, 0.5, f"no {cfg.upper()} runs", ha="center", color=INK_2)
    fig.tight_layout()
    fig.savefig(out)
    plt.close(fig)


# ------------------------------------------------------------------ failures.md

def _reasons(runs_root: Path, cfg: str, task_id: str) -> list[str]:
    ev = runs_root / cfg / task_id.replace("/", "__") / "events.jsonl"
    if not ev.exists():
        return [f"(no events.jsonl at {ev})"]
    out = []
    for e in map(json.loads, ev.read_text().splitlines()):
        v = e.get("verdict") or {}
        if e.get("event") == "stage_attempt" and v and not v.get("accept"):
            out.append(f"{e['stage']}#{e['attempt']} ({v.get('guard', '?')}): {v.get('reason', '')}")
        elif e.get("event") == "cap_hit":
            out.append(f"{e.get('stage')}: cap_hit {e.get('cap')}")
    return out


def failures(df: pd.DataFrame, runs_root: Path, out: Path, ref: str = "p3") -> int:
    m = metric_rows(df)
    cfgs = _configs(m)
    piv = m.pivot_table(index="task_id", columns="config", values="s4", aggfunc="first")
    dis = [t for t, r in piv.iterrows() if r.dropna().nunique() > 1]
    lines = ["# Tasks where configurations disagree on S4", "",
             f"{len(dis)} of {len(piv)} graded tasks. Per-config outcome, then the {ref.upper()} "
             "rejection reasons in order.", ""]
    for tid in dis:
        lines += [f"## {tid}", "", "| config | status | stop | claimed | S1 | S2 | S3 | S4 |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for c in cfgs:
            r = m[(m["task_id"] == tid) & (m["config"] == c)]
            if r.empty:
                continue
            r = r.iloc[0]
            stop = r["stop_reason"] + (f" @{r['failed_at']}" if isinstance(r.get("failed_at"), str) and r["failed_at"] else "")
            lines.append(f"| {c} | {r['status']} | {stop} | {int(r['claimed_success'])} | "
                         + " | ".join(str(int(r[s])) for s in ("s1", "s2", "s3", "s4")) + " |")
        if ref in cfgs:
            rs = _reasons(runs_root, ref, tid)
            lines += ["", f"{ref.upper()} rejections:"] + [f"{i}. {x}" for i, x in enumerate(rs, 1)]
            if not rs:
                lines.append("(none: every attempt accepted)")
        lines.append("")
    out.write_text("\n".join(lines))
    return len(dis)


# ------------------------------------------------------------------ main

def _task_filter(df: pd.DataFrame, tasks: Path | None) -> pd.DataFrame:
    if tasks is None:
        return df
    if not tasks.exists():
        print(f"WARNING: {tasks} not found; using every task in the summary (dev tasks included?)",
              file=sys.stderr)
        return df
    keep = {l.split(",")[0].strip() for l in tasks.read_text().splitlines() if l.strip() and not l.startswith("#")}
    dropped = sorted(set(df["task_id"]) - keep)
    if dropped:
        print(f"note: dropped {len(dropped)} task(s) not in {tasks}: {', '.join(dropped[:5])}"
              + (" ..." if len(dropped) > 5 else ""))
    return df[df["task_id"].isin(keep)]


def sanity(df: pd.DataFrame) -> list[str]:
    """Things that would invalidate a comparison; printed as warnings."""
    w = []
    for cfg, g in df.groupby("config"):
        for col in ("config_hash", "model", "provider"):
            vals = sorted(set(g[col].dropna().astype(str)))
            if len(vals) > 1:
                w.append(f"{cfg}: {len(vals)} different {col} values {vals}: config changed mid-batch?")
        if g["task_id"].duplicated().any():
            w.append(f"{cfg}: duplicate task rows (multiple seeds?) -- paired tables use the first")
    models = sorted(set(df["model"].dropna().astype(str)))
    if len(models) > 1:
        w.append(f"configs used different models {models}: comparisons are not like-for-like")
    n_ungraded = int(((df["status"] != "infra_error") & _num(df["s1"]).isna()).sum())
    if n_ungraded:
        w.append(f"{n_ungraded} run(s) have no grade file and are excluded: run `p2o.cli grade` first")
    return w


def run(summary: Path, out: Path, tasks: Path | None) -> dict[str, pd.DataFrame]:
    out.mkdir(parents=True, exist_ok=True)
    df = _task_filter(pd.read_csv(summary, dtype={"failed_at": str, "stop_reason": str}), tasks)
    df["failed_at"] = df["failed_at"].fillna("")
    df["stop_reason"] = df["stop_reason"].fillna("")
    for w in sanity(df):
        print("WARNING:", w, file=sys.stderr)
    tab = main_table(df)
    tab.to_csv(out / "table_main.csv", index=False)
    main_tex(tab, out / "table_main.tex")
    gt = guard_table(df)
    gt.to_csv(out / "table_guards.csv", index=False)
    guards_tex(gt, out / "table_guards.tex")
    pt = paired_table(df)
    pt.to_csv(out / "table_paired.csv", index=False)
    funnel(tab, out / "fig_funnel.pdf")
    retries(df, out / "fig_retries.pdf")
    n_dis = failures(df, summary.parent / "runs", out / "failures.md")
    return {"main": tab, "guards": gt, "paired": pt, "n_disagree": n_dis}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("summary", type=Path)
    ap.add_argument("--out", type=Path, default=Path("results/figs"))
    ap.add_argument("--tasks", type=Path, default=Path("tasks/main30.txt"),
                    help="only report these tasks (default: tasks/main30.txt)")
    ap.add_argument("--all-tasks", action="store_true", help="no task filter (fake data)")
    a = ap.parse_args()
    r = run(a.summary, a.out, None if a.all_tasks else a.tasks)
    pd.set_option("display.width", 200)
    show = ["config", "n", "n_infra_error", "n_ungraded", "s1", "s2", "s3", "s4", "claimed", "fsr",
            "check_pass_gap", "usd_total", "usd_per_s4", "median_minutes"]
    print("== table_main\n" + r["main"][show].to_string(index=False, float_format="%.3f"))
    if not r["guards"].empty:
        print("== table_guards\n" + r["guards"][["config", "guard", "reached", "accepts", "rejects",
              "false_accepts", "false_rejects", "precision", "recall", "stage_fsr"]]
              .to_string(index=False, float_format="%.3f"))
    if not r["paired"].empty:
        print("== table_paired\n" + r["paired"].to_string(index=False, float_format="%.3f"))
    print(f"== failures.md: {r['n_disagree']} disagreeing tasks")
    print("wrote " + ", ".join(str(a.out / f) for f in OUTPUTS))


if __name__ == "__main__":
    main()
