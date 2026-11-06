"""Recompute token usage / USD of finished runs from their stored worker output with the current
parser (p2o.worker.parse_stream), e.g. after the multi-`result` undercount fix (PROGRESS M0).

Updates run.json (usage, usd), appends a `usage_correction` event (events.jsonl stays append-only;
the original stage_attempt events are kept) and records the USD delta in the budget.
Usage: python scripts/recompute_usage.py results/runs/<config>/<task> [...]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from p2o.budget import Budget  # noqa: E402
from p2o.config import load_config  # noqa: E402
from p2o.ledger import EventLog  # noqa: E402
from p2o.pricing import usd  # noqa: E402
from p2o.types import RunRecord, Usage  # noqa: E402
from p2o.worker import parse_stream  # noqa: E402


def main() -> None:
    for d in map(Path, sys.argv[1:]):
        rec = RunRecord(**json.loads((d / "run.json").read_text()))
        prices = load_config(f"configs/{rec.config}.yaml").prices
        per, total = {}, Usage()
        for f in sorted(d.glob("work/*/*/worker_stdout.json")):
            u = parse_stream(f.read_text())[0]
            per[f"{f.parent.parent.name}/{f.parent.name}"] = u.model_dump()
            total = total + u
        new_usd = usd(total, prices)
        delta = new_usd - rec.usd
        if abs(delta) < 1e-9 and total == rec.usage:
            print(f"{d}: unchanged ${rec.usd:.4f}")
            continue
        log = EventLog(d, {"run_id": rec.run_id, "config": rec.config, "task_id": rec.task.task_id,
                           "seed": rec.seed, "model": rec.model, "provider": rec.provider})
        log.emit("usage_correction", reason="parser fix: cumulative modelUsage / stream events",
                 old_usage=rec.usage.model_dump(), old_usd=rec.usd, new_usage=total.model_dump(),
                 new_usd=new_usd, per_attempt=per)
        rec.usage, rec.usd = total, new_usd
        (d / "run.json").write_text(rec.model_dump_json(indent=2))
        Budget().record(rec.config, delta)
        print(f"{d}: ${rec.usd - delta:.4f} -> ${new_usd:.4f} (budget += {delta:.4f})")


if __name__ == "__main__":
    main()
