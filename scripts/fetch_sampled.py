"""Download dataset files and pull Docker images for the sampled tasks only.

Usage: python scripts/fetch_sampled.py [--sets dev,main] [--list-only] [--tasks a/b,c/d]
Data lands in data/projects/<project>/<task>/ (the harness's default --data-dir layout).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import HfApi, snapshot_download

REPO = "sunblaze-ucb/cybergym-e2e"


def pull(image: str) -> str:
    r = subprocess.run(["docker", "pull", "-q", image], capture_output=True, text=True)
    return f"{'OK ' if r.returncode == 0 else 'FAIL'} {image} {r.stderr.strip()[-200:]}"


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="dev,main")
    ap.add_argument("--tasks", default="", help="explicit task ids (overrides --sets)")
    ap.add_argument("--manifest", type=Path, default=Path("tasks/sample_manifest.json"))
    ap.add_argument("--data-dir", type=Path, default=Path("data"))
    ap.add_argument("--list-only", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    ap.add_argument("--no-data", action="store_true")
    a = ap.parse_args()
    m = json.loads(a.manifest.read_text())
    every = {t["task_id"]: t for k in ("dev", "main", "reserve_easy", "reserve_uniform") for t in m[k]}
    if a.tasks:
        tasks = [every[t] for t in a.tasks.split(",")]
    else:
        tasks = [t for s in a.sets.split(",") for t in m[s]]
    if a.list_only:
        files = HfApi().list_repo_files(REPO, repo_type="dataset")
        for t in tasks[:2]:
            print(t["task_id"], [f for f in files if f"/{t['task_id']}/" in f])
        print("top-level:", sorted({f.split("/")[0] for f in files}))
        return
    if not a.no_data:
        patterns = [f"projects/{t['task_id']}/*" for t in tasks]
        path = snapshot_download(REPO, repo_type="dataset", local_dir=a.data_dir,
                                 allow_patterns=patterns, max_workers=8)
        print("data ->", path)
    if not a.no_images:
        images = sorted({t["build_image"] for t in tasks})
        with ThreadPoolExecutor(max_workers=4) as ex:
            for line in ex.map(pull, images):
                print(line, flush=True)


if __name__ == "__main__":
    main()
