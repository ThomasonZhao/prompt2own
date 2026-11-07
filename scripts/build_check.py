"""E3 build check + infra replacement (pre-registered sampling rule E3).

For every dev/main task: build the guard-zone vulnerable image (official setup_workspace + compile.sh,
p2o.harness.CyberGymE2EAdapter.vulnerable_build) and time compile.sh. Replacement rule (pre-registered):
  easy stratum:    compile > 10 min, or build/setup fails -> next task of reserve_easy
  uniform stratum: build/setup fails                       -> next task of reserve_uniform
Replacements are themselves checked. Writes tasks/{dev,main30}.txt and updates the manifest
(build_minutes, replacements). Sampling-time tool: it ran once, before any main run. Do not rerun it
to reproduce: the task lists are frozen, and guard images are built on demand by the harness adapter.

Usage: python scripts/build_check.py [--parallel 6] [--only dev|main]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from p2o.harness import CyberGymE2EAdapter  # noqa: E402
from p2o.types import Task  # noqa: E402

MANIFEST = Path("tasks/sample_manifest.json")


def logged_minutes(ad: CyberGymE2EAdapter) -> dict[str, dict]:
    out = {}
    if ad.BUILD_LOG.exists():
        for line in ad.BUILD_LOG.read_text().splitlines():
            r = json.loads(line)
            out[r["task_id"]] = r          # last entry wins
    return out


def check(ad: CyberGymE2EAdapter, t: dict) -> dict:
    task = Task(task_id=t["task_id"], project=t["project"])
    tag = ad.guard_cache_tag(task)
    rec = logged_minutes(ad).get(t["task_id"])
    if ad._image_exists(tag) and rec is None:     # built before timings were logged: rebuild for E3
        subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)
    if rec is None or (rec["exit_code"] == 0 and not ad._image_exists(tag)):   # logged failures are final
        try:
            ad.vulnerable_build(task)
        except Exception as e:  # build failures are logged by vulnerable_build; setup failures here
            if t["task_id"] not in logged_minutes(ad):
                ad._log_build(task, tag, -1, 0.0, f"setup: {type(e).__name__}: {str(e)[:300]}")
        rec = logged_minutes(ad)[t["task_id"]]
    return {"task_id": t["task_id"], "ok": rec["exit_code"] == 0,
            "minutes": round(rec["compile_seconds"] / 60, 2), "exit_code": rec["exit_code"], "tail": rec["tail"]}


def passes(t: dict, r: dict, max_min: float) -> tuple[bool, str]:
    # E3 first: a build stopped after exceeding the limit is an E3 failure, not a build failure
    if t["stratum"] == "easy" and r["minutes"] > max_min:
        return False, f"E3: compile {r['minutes']} min > {max_min}" + ("" if r["ok"] else " (stopped)")
    if not r["ok"]:
        return False, f"build_failed (exit {r['exit_code']})"
    return True, "ok"


def fetch(task_id: str) -> None:
    """Reserve tasks are not pre-fetched: download their data and pull their image first."""
    subprocess.run([sys.executable, "scripts/fetch_sampled.py", "--tasks", task_id], check=True,
                   capture_output=True, text=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parallel", type=int, default=6)
    ap.add_argument("--only", choices=["dev", "main"], default=None)
    a = ap.parse_args()
    m = json.loads(MANIFEST.read_text())
    max_min = float(m["criteria"]["max_build_minutes"])
    ad = CyberGymE2EAdapter(use_firewall=False)
    sets = [a.only] if a.only else ["dev", "main"]
    reserves = {"easy": list(m["reserve_easy"]), "uniform": list(m["reserve_uniform"])}
    used_reserve = {r["task_id"] for r in m.get("replacements", [])} | {
        r["replacement"]["task_id"] for r in m.get("replacements", []) if r.get("replacement")}
    for s in sets:
        todo = list(m[s])
        with ThreadPoolExecutor(max_workers=a.parallel) as ex:
            results = list(ex.map(lambda t: check(ad, t), todo))
        final = []
        for t, r in zip(todo, results):
            m["build_minutes"][t["task_id"]] = r["minutes"] if r["ok"] else None
            ok, why = passes(t, r, max_min)
            cur, cur_why = t, why
            while not ok:
                pool = [x for x in reserves[cur["stratum"]] if x["task_id"] not in used_reserve]
                if not pool:
                    raise SystemExit(f"reserve_{t['stratum']} exhausted while replacing {t['task_id']}")
                nxt = pool[0]
                used_reserve.add(nxt["task_id"])
                fetch(nxt["task_id"])
                rr = check(ad, nxt)
                m["build_minutes"][nxt["task_id"]] = rr["minutes"] if rr["ok"] else None
                ok, why = passes(nxt, rr, max_min)
                m["replacements"].append({"set": s, "replaced": cur["task_id"], "reason": cur_why,
                                          "replacement": {"task_id": nxt["task_id"], "stratum": nxt["stratum"]},
                                          "replacement_minutes": rr["minutes"], "replacement_ok": ok})
                print(f"[replace] {s}: {cur['task_id']} ({cur_why}) -> {nxt['task_id']} ({why})", flush=True)
                cur, cur_why = nxt, why
            final.append(cur)
            print(f"{s} {cur['stratum']:7s} {cur['task_id']:40s} {m['build_minutes'].get(cur['task_id'])} min", flush=True)
        m[s] = final
    m["stratum"] = {t["task_id"]: t["stratum"] for k in ("dev", "main") for t in m[k]}
    MANIFEST.write_text(json.dumps(m, indent=2))
    Path("tasks/dev.txt").write_text("".join(f"{t['task_id']},{t['project']}\n" for t in m["dev"]))
    Path("tasks/main30.txt").write_text("".join(f"{t['task_id']},{t['project']}\n" for t in m["main"]))
    print("replacements:", len(m["replacements"]))


if __name__ == "__main__":
    main()
