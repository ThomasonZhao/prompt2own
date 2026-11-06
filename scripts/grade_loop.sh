#!/usr/bin/env bash
# Grade newly finished runs every 5 min until stopped. Grading happens strictly after run_end
# (grade() refuses runs without run.json), so workers/guards never see grades.
# Usage: bash scripts/grade_loop.sh <tasks_file> <config> [<config> ...]
set -u
tasks=$1; shift
while true; do
  for c in "$@"; do
    /root/prompt2own/.venv/bin/python -m p2o.cli grade --config "configs/$c.yaml" --tasks "$tasks" \
      --parallel 3 --only-new 2>&1 | grep -v "^skip " | sed "s/^/[$(date -u +%H:%M) $c] /"
  done
  sleep 300
done
