"""Readable timeline of one run, for debugging and the demo video.

Usage: python scripts/trace.py results/runs/p3/<task_dir>
# STATUS: implemented
"""
import json
import sys
from pathlib import Path

d = Path(sys.argv[1])
for e in map(json.loads, (d / "events.jsonl").read_text().splitlines()):
    ts = e["ts"][11:19]
    if e["event"] == "stage_attempt":
        c = e.get("claim") or {}
        v = e.get("verdict") or {}
        mark = "ACCEPT" if v.get("accept") else "REJECT"
        print(f"{ts}  {e['stage']:<6} #{e['attempt']}  claim done={c.get('done')} conf={c.get('confidence')}"
              f"  -> {mark if v else '-'} {v.get('guard', '')} {v.get('reason', e.get('schema_error') or '')}"
              f"  ${e.get('usd', 0):.3f}  {e.get('seconds', 0):.0f}s")
    else:
        rest = {k: v for k, v in e.items() if k not in ("ts", "event", "run_id", "config", "task_id", "seed", "model", "provider")}
        print(f"{ts}  [{e['event']}] {rest}")
grade = d.parent.parent.parent / "grades" / d.parent.name / f"{d.name}.json"
if grade.exists():
    g = json.loads(grade.read_text())
    print(f"grader: S1={g['s1']} S2={g['s2']} S3={g['s3']} S4={g['s4']}")
