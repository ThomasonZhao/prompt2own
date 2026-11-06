"""Readable timeline of one run, for debugging and the demo video.

Usage: python scripts/trace.py results/runs/p3/<task_dir> [--no-grade] [--width 100]
Shows: header (config, model, hashes), one row per stage attempt (claim, guard verdict,
reason, key evidence, tokens, cost, time), the guard-verified ledger facts, the run end,
and the official grade if it exists (pass --no-grade to hide it while recording the run).
# STATUS: implemented
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []


def _short(s: str, n: int) -> str:
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1] + "…"


def _evidence(v: dict) -> str:
    ev = v.get("evidence") or {}
    bits = []
    if ev.get("crash_type"):
        bits.append(ev["crash_type"])
    if ev.get("top_frames"):
        bits.append("top: " + ev["top_frames"][0])
    if "matches_rca" in ev:
        bits.append(f"matches_rca={ev['matches_rca']}")
    if ev.get("verified_poc_fixed"):
        bits.append("verified PoC no longer crashes")
    if ev.get("tests_passed"):
        bits.append("tests pass")
    if ev.get("error"):
        bits.append("error: " + ev["error"])
    if ev.get("log_tail"):
        bits.append("log: " + ev["log_tail"].strip().splitlines()[-1] if ev["log_tail"].strip() else "")
    return "; ".join(b for b in bits if b)


def _fmt_secs(s: float) -> str:
    return f"{s:.0f}s" if s < 120 else f"{s / 60:.1f}m"


def trace(d: Path, show_grade: bool = True, width: int = 100) -> str:
    ev = _jsonl(d / "events.jsonl")
    if not ev:
        return f"no events.jsonl in {d}"
    out: list[str] = []
    w = out.append
    s = ev[0]
    w(f"run {s.get('run_id')}  config={s.get('config')}  task={s.get('task_id')}  seed={s.get('seed')}")
    w(f"model={s.get('model')} via {s.get('provider')}  config_hash={s.get('config_hash')}"
      + (f"  templates_hash={s['templates_hash']}" if s.get("templates_hash") else ""))
    w("-" * width)
    w(f"{'time':8}  {'stage':<6}{'#':>2}  {'claim':<12} {'verdict':<7} {'guard':<13} reason")
    tok_total = 0
    for e in ev:
        ts = e.get("ts", "")[11:19]
        kind = e.get("event")
        if kind == "stage_attempt":
            c = e.get("claim") or {}
            claim = "-" if not c else f"done={'Y' if c.get('done') else 'N'} {c.get('confidence', 0):.2f}"
            v = e.get("verdict")
            if v:
                verdict = "ACCEPT" if v.get("accept") else "REJECT"
                guard, reason = v.get("guard", ""), v.get("reason", "")
            else:  # single-session runs have no verdict
                verdict, guard = "-", "-"
                reason = e.get("worker_error") or e.get("schema_error") or "(no guard: single session)"
            u = e.get("usage") or {}
            tok = sum(u.get(k, 0) for k in ("tokens_in", "tokens_out", "tokens_cached"))
            tok_total += tok
            w(f"{ts:8}  {e['stage']:<6}{e['attempt']:>2}  {claim:<12} {verdict:<7} {guard:<13} "
              + _short(reason, max(width - 52, 20)))
            extra = _evidence(v or {})
            if c.get("expected_crash_location"):
                extra = f"claimed crash in {c['expected_crash_location']}" + ("; " + extra if extra else "")
            w(f"{'':8}  {'':8}  ${e.get('usd', 0):.3f}  {tok / 1000:.0f}k tok  {_fmt_secs(e.get('seconds', 0))}"
              + (f"  | {_short(extra, width - 32)}" if extra else ""))
        elif kind == "cap_hit":
            w(f"{ts:8}  {e.get('stage', ''):<6}    CAP HIT: {e.get('cap')}")
        elif kind == "error":
            w(f"{ts:8}  [error] {e.get('where', '')}: {_short(e.get('error', ''), width - 30)}")
        elif kind == "run_end":
            w("-" * width)
            fa = f" at {e['failed_at']}" if e.get("failed_at") else ""
            w(f"{ts:8}  run_end: {e.get('status')} ({e.get('stop_reason')}{fa})  "
              f"claimed_success={e.get('claimed_success')}  ${e.get('usd', 0):.3f}  "
              f"{tok_total / 1000:.0f}k tok  {_fmt_secs(e.get('seconds', 0))}")
        elif kind != "run_start":
            rest = {k: v for k, v in e.items() if k not in ("ts", "event", "run_id", "config", "task_id",
                                                             "seed", "model", "provider")}
            w(f"{ts:8}  [{kind}] {_short(json.dumps(rest, default=str), width - 20)}")
    if not any(e.get("event") == "run_end" for e in ev):
        w("-" * width + "\n(run has not ended: no run_end event)")
    facts = _jsonl(d / "ledger.jsonl")
    if facts:
        w("\nverified facts (ledger):")
        for f in facts:
            data = {k: v for k, v in f.get("data", {}).items() if k not in ("rationale", "log_tail")}
            w(f"  {f['stage']:<6}#{f['attempt']} by {f['guard']:<13} {_short(json.dumps(data, default=str), width - 30)}")
    deliv = d / "deliverables"
    have = [p.name for p in (deliv / "poc.bin", deliv / "fix.patch") if p.exists()]
    w(f"deliverables: {', '.join(have) if have else '(none)'}")
    grade = d.parent.parent.parent / "grades" / d.parent.name / f"{d.name}.json"
    if show_grade:
        if grade.exists():
            g = json.loads(grade.read_text())
            w("official grade: " + "  ".join(f"S{i}={'PASS' if g[f's{i}'] else 'fail'}" for i in (1, 2, 3, 4)))
        else:
            w("official grade: (not graded yet: python -m p2o.cli grade ...)")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--no-grade", action="store_true", help="hide the official grade")
    ap.add_argument("--width", type=int, default=100)
    a = ap.parse_args()
    if not a.run_dir.is_dir():
        sys.exit(f"not a run directory: {a.run_dir}")
    print(trace(a.run_dir, show_grade=not a.no_grade, width=a.width))


if __name__ == "__main__":
    main()
