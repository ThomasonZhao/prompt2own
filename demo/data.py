"""Single source of every number and event shown in the demo video.

Every scene does `from data import D`. Nothing on screen or in the narration is typed by hand:
it is read here from the real result files. A missing file or field raises immediately.

Sources
- Aggregate tables: results/figs/*.csv and false_accepts.md in this checkout (committed by the
  main sessions at 21ed361, "B2 main complete").
- Per-run events: results/runs/p3/libspng__arvo_14935/{events,ledger,run}.jsonl and its grade.
  These live on the `results` git branch (results/runs is not in the code branches), so they are
  read with `git show <ref>:<path>`. Override with P2O_RESULTS_REF (default: results). If the file
  exists in the working tree it is used instead (same content when synced).
- Paper reference numbers: the "Reference numbers" line of docs/EVAL.md.

Safety: this module never loads PoC bytes, patch diffs or worker free-text notes. From the guard
evidence it keeps only crash type, function names, booleans and short artifact hashes.

Run `python demo/data.py` to print the dict and the provenance of each source.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
REF = os.environ.get("P2O_RESULTS_REF", "results")
DEMO_RUN = "results/runs/p3/libspng__arvo_14935"
DEMO_GRADE = "results/grades/p3/libspng__arvo_14935.json"
MAIN_CONFIGS = ("b1", "b2", "p3")

PROVENANCE: dict[str, str] = {}


class DataError(RuntimeError):
    pass


def _read(rel: str) -> str:
    """Working-tree file if present, else `git show REF:rel`. Fails loudly."""
    p = REPO / rel
    if p.exists():
        PROVENANCE[rel] = f"worktree:{rel}"
        return p.read_text()
    try:
        out = subprocess.run(["git", "-C", str(REPO), "show", f"{REF}:{rel}"],
                             check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError as e:
        raise DataError(f"missing source file {rel!r} (not in worktree, not in git ref {REF!r}): "
                        f"{e.stderr.strip()}") from None
    PROVENANCE[rel] = f"git:{REF}:{rel}"
    return out


def _csv(rel: str) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(_read(rel))))
    if not rows:
        raise DataError(f"{rel} is empty")
    return rows


def _jsonl(rel: str) -> list[dict]:
    rows = [json.loads(l) for l in _read(rel).splitlines() if l.strip()]
    if not rows:
        raise DataError(f"{rel} is empty")
    return rows


def _one(rows: list[dict], **kw) -> dict:
    hit = [r for r in rows if all(r.get(k) == v for k, v in kw.items())]
    if len(hit) != 1:
        raise DataError(f"expected exactly one row with {kw}, got {len(hit)}")
    return hit[0]


def _f(x) -> float:
    if x in (None, ""):
        raise DataError("empty numeric field")
    return float(x)


def _fn(frame: str) -> str:
    """'#3 spng_decode_image /src/.../spng.c:1825:11' -> 'spng_decode_image'."""
    parts = frame.split()
    if len(parts) < 2:
        raise DataError(f"unparseable frame {frame!r}")
    return parts[1]


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


# ---------------------------------------------------------------- paper reference

def _paper() -> dict:
    txt = _read("docs/EVAL.md")
    m = re.search(r"## 4\. Reference numbers \(paper, (\d+) tasks.*?\)\s*\n\s*\n"
                  r"(.+?): patch-only ([\d.]+); S1 ([\d.]+); S2 ([\d.]+); S3 ([\d.]+); S4 ([\d.]+)"
                  r"\s*\n\((https?://\S+?)(?:,|\))", txt, re.S)
    if not m:
        raise DataError("could not parse the paper reference line in docs/EVAL.md")
    n, who, po, s1, s2, s3, s4, url = m.groups()
    return {"n_tasks": int(n), "setup": who.strip(), "patch_only": float(po),
            "s1": float(s1), "s2": float(s2), "s3": float(s3), "s4": float(s4), "url": url}


# ---------------------------------------------------------------- aggregate tables

def _main() -> dict:
    rows = _csv("results/figs/table_main.csv")
    out: dict = {}
    for cfg in MAIN_CONFIGS:
        out[cfg] = {}
        for stratum in ("all", "easy", "uniform"):
            r = _one(rows, config=cfg, stratum=stratum)
            d = {"n": int(r["n"]), "n_claimed": int(r["n_claimed"]),
                 "n_false_success": int(r["n_false_success"])}
            for k in ("s1", "s2", "s3", "s4", "claimed", "fsr", "check_pass_gap"):
                d[k] = _f(r[k])
                d[k + "_lo"] = _f(r[k + "_lo"])
                d[k + "_hi"] = _f(r[k + "_hi"])
            d["usd_total"] = _f(r["usd_total"])
            d["usd_per_s4"] = _f(r["usd_per_s4"])
            out[cfg][stratum] = d
    return out


def _guards() -> dict:
    rows = _csv("results/figs/table_guards.csv")
    out = {}
    for g in ("exec_poc", "exec_patch"):
        r = _one(rows, config="p3", stratum="all", guard=g)
        out[g] = {"truth": r["truth"], "accepts": int(r["accepts"]), "rejects": int(r["rejects"]),
                  "false_accepts": int(r["false_accepts"]), "false_rejects": int(r["false_rejects"]),
                  "precision": _f(r["precision"]), "precision_lo": _f(r["precision_lo"]),
                  "precision_hi": _f(r["precision_hi"]), "recall": _f(r["recall"]),
                  "checks": int(r["checks"]), "check_rejects": int(r["check_rejects"])}
    return out


def _paired() -> dict:
    rows = _csv("results/figs/table_paired.csv") + _csv("results/figs/table_paired_b2_vs_b1.csv")
    out = {}
    for a, b in (("p3", "b1"), ("p3", "b2"), ("b2", "b1")):
        r = _one(rows, a=a, b=b, stratum="all", metric="s4")
        out[f"{a}_vs_{b}"] = {"n": int(r["n"]), "both": int(r["both"]), "only_a": int(r["only_a"]),
                              "only_b": int(r["only_b"]), "neither": int(r["neither"]),
                              "p": _f(r["mcnemar_p"])}
    return out


def _false_accepts() -> dict:
    txt = _read("results/figs/false_accepts.md")
    m = re.search(r"\(P3 main, n = (\d+)\)", txt)
    c = re.search(r"\*\*Counts:\*\* masks the crash at the PoC's path (\d+) · "
                  r"fixes a different location (\d+) · other (\d+)", txt)
    if not (m and c):
        raise DataError("could not parse counts in results/figs/false_accepts.md")
    n, masks, different, other = int(m.group(1)), *map(int, c.groups())
    if masks + different + other != n:
        raise DataError("false_accepts.md counts do not add up")
    all_s1_s3 = "All 7 pass S1-S3 and fail only" in txt if n == 7 else None
    return {"n": n, "masks": masks, "different_location": different, "other": other,
            "all_pass_s1_s3_fail_s4": bool(all_s1_s3)}


def _task_ids(rel: str) -> set[str]:
    """tasks/*.txt lines are 'task_id,project'."""
    return {l.split(",")[0].strip() for l in _read(rel).splitlines()
            if l.strip() and not l.startswith("#")}


def _graded_runs() -> dict:
    main = _task_ids("tasks/main30.txt")
    rows = _csv("results/summary.csv")
    graded = [r for r in rows if r["config"] in MAIN_CONFIGS and r["task_id"] in main
              and r["s1"] != ""]
    per = {c: sum(1 for r in graded if r["config"] == c) for c in MAIN_CONFIGS}
    model = {r["model"] for r in graded}
    provider = {r["provider"] for r in graded}
    if len(model) != 1 or len(provider) != 1:
        raise DataError(f"expected one model/provider, got {model} / {provider}")
    strata = {s: sum(1 for t in main if any(r["task_id"] == t and r["stratum"] == s for r in rows))
              for s in ("easy", "uniform")}
    return {"n_tasks": len(main), "per_config": per, "total": sum(per.values()),
            "model": model.pop(), "provider": provider.pop(), "strata": strata}


# ---------------------------------------------------------------- the demo run

def _run() -> dict:
    ev = _jsonl(f"{DEMO_RUN}/events.jsonl")
    led = _jsonl(f"{DEMO_RUN}/ledger.jsonl")
    grade = json.loads(_read(DEMO_GRADE))
    start = _one(ev, event="run_start")
    end = _one(ev, event="run_end")
    t0 = _ts(start["ts"])
    dev = _task_ids("tasks/dev.txt")

    attempts = []
    for e in (x for x in ev if x["event"] == "stage_attempt"):
        v, claim, u = e["verdict"], e.get("claim"), e["usage"]
        a = {
            "stage": e["stage"], "attempt": e["attempt"],
            "claim_done": None if claim is None else bool(claim["done"]),
            "claim_conf": None if claim is None else float(claim["confidence"]),
            "accept": bool(v["accept"]), "reason": v["reason"], "guard": v["guard"],
            "worker_seconds": float(e["seconds"]), "guard_seconds": float(v["seconds"]),
            "usd": float(e["usd"]),
            "tokens": int(u["tokens_in"]) + int(u["tokens_out"]) + int(u["tokens_cached"]),
            "t_end": (_ts(e["ts"]) - t0).total_seconds(),
            "clock": _ts(e["ts"]).strftime("%H:%M:%S"),
        }
        evd = v.get("evidence") or {}
        if e["stage"] == "poc" and v["accept"]:
            frames = evd["top_frames"]
            a["crash_type"] = evd["crash_type"]
            a["crash_fn"] = _fn(frames[0])
            a["frames_fn"] = [_fn(f) for f in frames[:3]]
            a["matches_rca"] = bool(evd["matches_rca"])
        if e["stage"] == "patch" and v["accept"]:
            a["build_ok"] = bool(evd["build"])  # an image tag exists only if apply+rebuild succeeded
            a["verified_poc_fixed"] = bool(evd["verified_poc_fixed"])
            a["tests_passed"] = bool(evd["tests_passed"])
        attempts.append(a)
    if not attempts:
        raise DataError("no stage_attempt events in demo run")

    facts = []
    for f in led:
        d = f["data"]
        fact = {"stage": f["stage"], "attempt": f["attempt"], "guard": f["guard"]}
        if f["stage"] == "rca":
            fact.update(file=d["file"], function=d["function"], unchecked=bool(d.get("unchecked")))
        elif f["stage"] == "poc":
            fact.update(file=Path(d["poc_path"]).name, crash_type=d["crash_type"],
                        function=_fn(d["top_frames"][0]), sha=f["artifact_sha256"][:8])
        elif f["stage"] == "patch":
            fact.update(file=Path(d["patch_path"]).name, sha=f["artifact_sha256"][:8],
                        tests_passed=bool(d["tests_passed"]))
        facts.append(fact)

    # cumulative cost within the run (sum of attempts) must equal run_end
    tot = sum(a["usd"] for a in attempts)
    if abs(tot - float(end["usd"])) > 1e-6:
        raise DataError(f"attempt usd {tot} != run_end usd {end['usd']}")

    return {
        "run_id": start["run_id"], "config": start["config"], "task_id": start["task_id"],
        "is_dev_task": start["task_id"] in dev, "model": start["model"],
        "provider": start["provider"], "config_hash": start["config_hash"],
        "attempts": attempts, "facts": facts,
        "status": end["status"], "claimed_success": bool(end["claimed_success"]),
        "usd": float(end["usd"]), "seconds": float(end["seconds"]),
        "tokens": sum(a["tokens"] for a in attempts),
        "grade": {k: bool(grade[k]) for k in ("s1", "s2", "s3", "s4")},
        "grade_seconds": float(grade["raw"]["seconds"]),
    }


REJECT_TASK = "htslib/arvo_18196"   # P3 PoC rejected 3x, and S1 really failed: a correct reject


def _reject_example() -> dict:
    """A run where the PoC guard said no and the grader agreed, next to B1's claim on the same task."""
    d = REJECT_TASK.replace("/", "__")
    ev = _jsonl(f"results/runs/p3/{d}/events.jsonl")
    pocs = [{"attempt": e["attempt"], "claim_done": bool(e["claim"]["done"]),
             "claim_conf": float(e["claim"]["confidence"]), "accept": bool(e["verdict"]["accept"]),
             "reason": e["verdict"]["reason"]}
            for e in ev if e["event"] == "stage_attempt" and e["stage"] == "poc"]
    rows = _csv("results/summary.csv")
    p3 = _one(rows, config="p3", task_id=REJECT_TASK)
    b1 = _one(rows, config="b1", task_id=REJECT_TASK)
    out = {"task_id": REJECT_TASK, "pocs": pocs,
           "p3": {k: p3[k] == "1" for k in ("claimed_success", "s1", "s2", "s3", "s4")},
           "b1": {k: b1[k] == "1" for k in ("claimed_success", "s1", "s2", "s3", "s4")}}
    if any(p["accept"] for p in pocs) or out["p3"]["s1"]:
        raise DataError(f"{REJECT_TASK} is no longer a correct-reject example; pick another")
    return out


CACHE = Path(__file__).resolve().parent / "cache"


def _trace(config: str, task: str, width: int = 80) -> list[str]:
    """Run the project's own scripts/trace.py on a copy of the run files, return its output lines.

    results/runs is not on the code branches, so the run's events/ledger/run.json and its grade are
    copied from the results ref into demo/cache/results/... (same layout trace.py expects).
    """
    d = task.replace("/", "__")
    names = ("events.jsonl", "run.json") + (() if config in ("b1", "b2") else ("ledger.jsonl",))
    files = [f"results/runs/{config}/{d}/{n}" for n in names]   # single-session runs have no ledger
    files.append(f"results/grades/{config}/{d}.json")
    for rel in files:
        dst = CACHE / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(_read(rel))
    import sys
    out = subprocess.run([sys.executable, str(REPO / "scripts/trace.py"),
                          str(CACHE / f"results/runs/{config}/{d}"), "--width", str(width)],
                         check=True, capture_output=True, text=True).stdout
    # The cache holds no PoC/patch bytes (on purpose), so trace.py would print a false
    # "deliverables: (none)"; drop that one line rather than show it.
    return [l for l in out.rstrip("\n").splitlines() if not l.startswith("deliverables:")]


def load() -> dict:
    d = {"paper": _paper(), "main": _main(), "guards": _guards(), "paired": _paired(),
         "false_accepts": _false_accepts(), "graded": _graded_runs(), "run": _run(),
         "reject": _reject_example()}
    d["trace"] = {"libspng": _trace("p3", "libspng/arvo_14935"),
                  "htslib_p3": _trace("p3", REJECT_TASK),
                  "htslib_b1": _trace("b1", REJECT_TASK)}
    m = d["main"]
    d["handoff"] = {c: {"s1": m[c]["all"]["s1"], "s2": m[c]["all"]["s2"]} for c in MAIN_CONFIGS}
    d["provenance"] = dict(PROVENANCE)
    return d


D = load()


# ---------------------------------------------------------------- formatting helpers

def f2(x: float) -> str:
    return f"{x:.2f}"


def pct(x: float, nd: int = 1) -> str:
    """Fraction or percent value -> '43.3%'. Values > 1 are taken as already in percent."""
    return f"{(x if x > 1 else 100 * x):.{nd}f}%"


if __name__ == "__main__":
    import pprint
    pprint.pprint({k: v for k, v in D.items() if k != "provenance"}, width=110, sort_dicts=False)
    print("\nprovenance:")
    for k, v in D["provenance"].items():
        print(f"  {v}")
