"""Sampler: diff stats parsing and deterministic stratified sampling (no Docker, no ground truth)."""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "sample_tasks", Path(__file__).resolve().parent.parent / "scripts" / "sample_tasks.py")
st = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(st)

FORMAT_PATCH = """From abc Mon Sep 17 00:00:00 2001
Subject: [PATCH] fix
- a bullet in the commit message
---
 src/a.c | 3 ++-
 1 file changed

diff --git a/src/a.c b/src/a.c
index 1..2 100644
--- a/src/a.c
+++ b/src/a.c
@@ -10,4 +10,5 @@ int f()
 ctx
-  old;
+  new;
+  check;

 ctx2
--\x20
2.30.0
"""

TWO_FILES = """--- a/x.c
+++ b/x.c
@@ -1 +1 @@
-a
+b
--- /dev/null
+++ b/new.h
@@ -0,0 +1,2 @@
+x
+y
"""


def test_diff_stats_ignores_message_and_signature(tmp_path):
    p = tmp_path / "p.diff"
    p.write_text(FORMAT_PATCH)
    assert st.diff_stats(p) == (1, 3)


def test_diff_stats_counts_files_and_new_files(tmp_path):
    p = tmp_path / "p.diff"
    p.write_text(TWO_FILES)
    assert st.diff_stats(p) == (2, 4)


def _index():
    idx = []
    for i in range(60):
        for j in range(3):
            easy = (i % 3 != 0) and j == 0
            idx.append({"task_id": f"p{i}/t{j}", "project": f"p{i}", "build_image": "img",
                        "fix_files": 1 if easy else 3, "fix_lines": 5 if easy else 50})
    return idx


def test_stratified_sample_is_deterministic_and_one_per_project():
    a = st.stratified_sample(_index(), 329)
    b = st.stratified_sample(_index(), 329)
    assert a == b
    main, dev = a["main"], a["dev"]
    assert [t["stratum"] for t in main].count("easy") == 20
    assert [t["stratum"] for t in main].count("uniform") == 10
    assert [t["stratum"] for t in dev] == ["easy", "easy", "uniform"]
    assert all(st.is_easy(t) for t in main + dev if t["stratum"] == "easy")
    projs = [t["project"] for k in a for t in a[k]]
    assert len(projs) == len(set(projs))
    assert st.stratified_sample(_index(), 330) != a
