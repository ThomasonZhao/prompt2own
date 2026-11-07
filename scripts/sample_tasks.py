"""Deterministic, stratified task sampling.

Usage: python scripts/sample_tasks.py --seed 329

Strata (pre-registered before any run; metadata only, never model results):
  easy    = ground-truth fix touches 1 file (E1) and changes <= 20 lines (E2); build <= 10 min (E3)
            is measured after sampling and enforced by replacement from the same stratum's reserve.
  uniform = any task.
main30 = 20 easy + 10 uniform; dev = 2 easy + 1 uniform; one task per project overall.

GROUND-TRUTH ISOLATION: this script is the only code that reads `patch.diff`. It records only
derived counts (files, changed lines). Nothing in p2o/ may import this module.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

import tomli

CRITERIA = {
    "E1": "ground-truth fix (projects/<p>/<t>/patch.diff) touches exactly 1 file",
    "E2": "ground-truth fix changes <= 20 lines (added + removed hunk body lines)",
    "E3": "task builds in the official harness in <= 10 min wall clock (measured after sampling on the "
          "pilot VM; failing tasks are replaced from the same stratum's reserve, logged in replacements)",
    "max_files": 1, "max_changed_lines": 20, "max_build_minutes": 10,
    "main": {"easy": 20, "uniform": 10}, "dev": {"easy": 2, "uniform": 1},
    "one_task_per_project": True,
}


_HUNK = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")


def diff_stats(patch: Path) -> tuple[int, int]:
    """(files touched, changed lines) of a unified / git format-patch diff. Hunk bodies are consumed
    using the line counts in each @@ header, so commit-message text, the format-patch '---'
    separator and the '-- ' signature are never counted."""
    files: set[str] = set()
    changed = 0
    lines = patch.read_text(errors="replace").splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("--- ") and i + 1 < len(lines) and lines[i + 1].startswith("+++ "):
            minus = line[4:].split("\t")[0].strip()
            plus = lines[i + 1][4:].split("\t")[0].strip()
            files.add(minus if plus == "/dev/null" else plus)
            i += 2
            continue
        m = _HUNK.match(line)
        if m:
            old_n = int(m.group(1)) if m.group(1) is not None else 1
            new_n = int(m.group(2)) if m.group(2) is not None else 1
            i += 1
            while (old_n > 0 or new_n > 0) and i < len(lines):
                body = lines[i]
                if body.startswith("\\"):           # "\ No newline at end of file"
                    pass
                elif body.startswith("-"):
                    old_n -= 1
                    changed += 1
                elif body.startswith("+"):
                    new_n -= 1
                    changed += 1
                else:                               # context line (" " or empty)
                    old_n -= 1
                    new_n -= 1
                i += 1
            continue
        i += 1
    return len(files), changed


def load_index(harness_root: Path) -> list[dict]:
    """All tasks from the harness: projects/<project>/<task>/config.toml.
    Returns [{"task_id": "curl/arvo_66012", "project": "curl", "build_image": ..., "fix_files": n,
    "fix_lines": n}, ...]. fix_* are derived from ground truth and stay in this script's outputs."""
    projects = harness_root / "projects"
    out = []
    for cfg in sorted(projects.glob("*/*/config.toml")):
        tdir = cfg.parent
        proj = tdir.parent.name
        merged = tomli.loads((tdir.parent / "project.toml").read_text())
        merged.update(tomli.loads(cfg.read_text()))
        files, lines = diff_stats(tdir / "patch.diff") if (tdir / "patch.diff").exists() else (-1, -1)
        out.append({"task_id": f"{proj}/{tdir.name}", "project": proj,
                    "build_image": merged.get("build_image",
                                              "gcr.io/oss-fuzz-base/base-builder@sha256:8eda74a11e800aead5a041ee479a65b33dab3150d6e89e5694e2b6eb27be98fc"),
                    "fix_files": files, "fix_lines": lines})
    if not out:
        raise FileNotFoundError(f"no tasks under {projects}")
    return out


def is_easy(t: dict) -> bool:
    return 0 < t["fix_files"] <= CRITERIA["max_files"] and 0 < t["fix_lines"] <= CRITERIA["max_changed_lines"]


def stratified_sample(index: list[dict], seed: int, n_reserve: int = 10) -> dict[str, list[dict]]:
    """Deterministic. Projects are shuffled once; for every project (in shuffled order) one easy and
    one uniform candidate are pre-drawn so the RNG stream does not depend on the allocation. Slots are
    then filled in a fixed order (dev easy, dev uniform, main easy, main uniform, reserves), never
    reusing a project."""
    by_proj: dict[str, list[dict]] = defaultdict(list)
    for t in sorted(index, key=lambda t: t["task_id"]):
        by_proj[t["project"]].append(t)
    rng = random.Random(seed)
    projects = sorted(by_proj)
    rng.shuffle(projects)
    easy_pick, any_pick = {}, {}
    for p in projects:
        easy = [t for t in by_proj[p] if is_easy(t)]
        easy_pick[p] = rng.choice(easy) if easy else None
        any_pick[p] = rng.choice(by_proj[p])
    used: set[str] = set()

    def take(n: int, stratum: str) -> list[dict]:
        got = []
        for p in projects:
            if len(got) == n:
                break
            if p in used:
                continue
            t = easy_pick[p] if stratum == "easy" else any_pick[p]
            if t is None:
                continue
            used.add(p)
            got.append({**t, "stratum": stratum})
        if len(got) < n:
            raise RuntimeError(f"not enough projects for {n} {stratum} tasks")
        return got

    c = CRITERIA
    return {
        "dev": take(c["dev"]["easy"], "easy") + take(c["dev"]["uniform"], "uniform"),
        "main": take(c["main"]["easy"], "easy") + take(c["main"]["uniform"], "uniform"),
        "reserve_easy": take(n_reserve, "easy"),
        "reserve_uniform": take(n_reserve, "uniform"),
    }


def _line(t: dict) -> str:
    return f"{t['task_id']},{t['project']}\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=329)
    ap.add_argument("--reserve", type=int, default=10, help="tasks kept per stratum for replacements")
    ap.add_argument("--harness-root", type=Path, default=Path("third_party/cybergym-e2e"))
    ap.add_argument("--out", type=Path, default=Path("tasks"))
    a = ap.parse_args()
    idx = load_index(a.harness_root)
    s = stratified_sample(idx, a.seed, a.reserve)
    a.out.mkdir(exist_ok=True)
    (a.out / "dev.txt").write_text("".join(map(_line, s["dev"])))
    (a.out / "main30.txt").write_text("".join(map(_line, s["main"])))
    (a.out / "sample_manifest.json").write_text(json.dumps({
        "seed": a.seed, "n_index": len(idx), "n_projects": len({t["project"] for t in idx}),
        "n_easy_eligible": sum(map(is_easy, idx)), "criteria": CRITERIA,
        "stratum": {t["task_id"]: t["stratum"] for k in ("dev", "main") for t in s[k]},
        **s, "replacements": [], "build_minutes": {}}, indent=2))
    print(f"dev={len(s['dev'])} main={len(s['main'])} from {len(idx)} tasks "
          f"({sum(map(is_easy, idx))} meet E1+E2)")


if __name__ == "__main__":
    main()
