"""M4 spend checks. # STATUS: implemented (M4)

1. budget.json spent vs. sum of run.json usd over results/runs/*/* (must match within 1%).
2. Per run with partial-message streams: our USD (pricing.py on token counts) vs. OpenRouter's own
   per-request `cost` reported in message_delta usage (what we are actually billed).
Usage: python scripts/check_spend.py [--results results]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from p2o.budget import Budget  # noqa: E402


def openrouter_cost(run_dir: Path) -> float | None:
    total, seen = 0.0, False
    for f in run_dir.glob("work/*/*/worker_stdout.json"):
        for line in f.read_text().splitlines():
            if '"message_delta"' not in line:
                continue
            try:
                ev = json.loads(line).get("event") or {}
            except json.JSONDecodeError:
                continue
            c = (ev.get("usage") or {}).get("cost")
            if c is not None:
                total, seen = total + float(c), True
    return total if seen else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=Path("results"))
    a = ap.parse_args()
    runs = sorted(a.results.glob("runs/*/*/run.json"))
    s = 0.0
    print(f"{'run':45s} {'ours':>8s} {'openrouter':>10s}")
    for rj in runs:
        r = json.loads(rj.read_text())
        s += r["usd"]
        orc = openrouter_cost(rj.parent)
        print(f"{rj.parent.parent.name + '/' + rj.parent.name:45s} {r['usd']:8.4f} "
              f"{'' if orc is None else f'{orc:10.4f}'}")
    spent = Budget(a.results / "budget.json").spent()
    rel = abs(spent - s) / s if s else 0.0
    print(f"\nsum(run usd) = ${s:.4f}; budget spent = ${spent:.4f}; rel diff = {rel:.4%} "
          f"-> {'OK' if rel <= 0.01 else 'MISMATCH'} (<= 1%)")
    print("note: runs still in flight are in neither number; only finished runs are recorded")


if __name__ == "__main__":
    main()
