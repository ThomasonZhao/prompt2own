"""Deterministic task sampling (docs/SPEC.md §6).

Usage: python scripts/sample_tasks.py --seed 329 --n-main 30 --n-dev 3
# STATUS: sampling implemented; `load_index` is a stub for M0 (docs/HARNESS.md question 9).
"""
from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def load_index(data_root: Path) -> list[dict]:
    """Return [{"task_id": "curl/arvo_66012", "project": "curl", ...}, ...] for all tasks.
    M0: implement from the dataset metadata / harness task list. Do not pull images here."""
    raise NotImplementedError("M0: see docs/HARNESS.md question 9")


def sample(index: list[dict], seed: int, n: int, exclude_projects: set[str]) -> list[dict]:
    by_proj: dict[str, list[dict]] = defaultdict(list)
    for t in sorted(index, key=lambda t: t["task_id"]):
        if t["project"] not in exclude_projects:
            by_proj[t["project"]].append(t)
    rng = random.Random(seed)
    projects = sorted(by_proj)
    rng.shuffle(projects)
    order = [rng.choice(by_proj[p]) for p in projects]   # one task per project, shuffled
    return order[:n] if n <= len(order) else order


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=329)
    ap.add_argument("--n-main", type=int, default=30)
    ap.add_argument("--n-dev", type=int, default=3)
    ap.add_argument("--reserve", type=int, default=10, help="extra tasks kept in order for replacements")
    ap.add_argument("--data-root", type=Path, default=Path("data"))
    ap.add_argument("--exclude", default="", help="comma-separated projects to exclude")
    a = ap.parse_args()
    excl = {p for p in a.exclude.split(",") if p}
    idx = load_index(a.data_root)
    picked = sample(idx, a.seed, a.n_dev + a.n_main + a.reserve, excl)
    dev, main_, reserve = picked[: a.n_dev], picked[a.n_dev: a.n_dev + a.n_main], picked[a.n_dev + a.n_main:]
    Path("tasks").mkdir(exist_ok=True)
    Path("tasks/dev.txt").write_text("".join(f"{t['task_id']},{t['project']}\n" for t in dev))
    Path("tasks/main30.txt").write_text("".join(f"{t['task_id']},{t['project']}\n" for t in main_))
    Path("tasks/sample_manifest.json").write_text(json.dumps({
        "seed": a.seed, "n_index": len(idx), "excluded_projects": sorted(excl),
        "dev": dev, "main": main_, "reserve": reserve, "replacements": []}, indent=2))
    print(f"dev={len(dev)} main={len(main_)} reserve={len(reserve)} from {len(idx)} tasks")


if __name__ == "__main__":
    main()
