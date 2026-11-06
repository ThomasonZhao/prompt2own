"""Build results/summary.csv from run.json + grade files. # STATUS: implemented"""
from __future__ import annotations

import csv
import json
from pathlib import Path

COLUMNS = ["config", "task_id", "project", "seed", "status", "stop_reason", "failed_at",
           "claimed_success", "s1", "s2", "s3", "s4", "usd", "tokens_in", "tokens_out",
           "tokens_cached", "minutes", "attempts_rca", "attempts_poc", "attempts_patch",
           "poc_guard_accepts", "poc_guard_rejects", "patch_guard_accepts", "patch_guard_rejects",
           "final_poc_guard_accept", "final_patch_guard_accept", "model", "provider",
           "prompt_hash", "config_hash"]


def _guard(counts: dict, prefix: str, key: str) -> int:
    return sum(v[key] for g, v in counts.items() if g.startswith(prefix))


def summarize(results_root: Path = Path("results")) -> Path:
    rows = []
    for run_json in sorted((results_root / "runs").glob("*/*/run.json")):
        r = json.loads(run_json.read_text())
        cfg, tdir = run_json.parent.parent.name, run_json.parent.name
        gpath = results_root / "grades" / cfg / f"{tdir}.json"
        g = json.loads(gpath.read_text()) if gpath.exists() else {}
        gc, fa = r.get("guard_counts", {}), r.get("final_guard_accept", {})
        u = r.get("usage", {})
        rows.append({
            "config": cfg, "task_id": r["task"]["task_id"], "project": r["task"].get("project", ""),
            "seed": r["seed"], "status": r["status"], "stop_reason": r["stop_reason"],
            "failed_at": r.get("failed_at") or "", "claimed_success": int(r["claimed_success"]),
            **{k: (int(g[k]) if k in g else "") for k in ("s1", "s2", "s3", "s4")},
            "usd": round(r["usd"], 4), "tokens_in": u.get("tokens_in", 0),
            "tokens_out": u.get("tokens_out", 0), "tokens_cached": u.get("tokens_cached", 0),
            "minutes": round(r["seconds"] / 60, 2),
            "attempts_rca": r["attempts"].get("rca", 0), "attempts_poc": r["attempts"].get("poc", 0),
            "attempts_patch": r["attempts"].get("patch", 0),
            "poc_guard_accepts": _guard(gc, "exec_poc", "accept"),
            "poc_guard_rejects": _guard(gc, "exec_poc", "reject"),
            "patch_guard_accepts": _guard(gc, "exec_patch", "accept"),
            "patch_guard_rejects": _guard(gc, "exec_patch", "reject"),
            "final_poc_guard_accept": "" if "poc" not in fa else int(fa["poc"]),
            "final_patch_guard_accept": "" if "patch" not in fa else int(fa["patch"]),
            "model": r["model"], "provider": r["provider"], "prompt_hash": r["prompt_hash"],
            "config_hash": r["config_hash"],
        })
    out = results_root / "summary.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return out
