#!/usr/bin/env bash
# End-to-end analysis pipeline on synthetic data (no Docker, no API calls, no spend).
# Everything goes to results/fake/ (own budget.json); the real results/ is never touched.
# Usage: bash scripts/fake_pipeline.sh [n_tasks]      (default 30)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python}
N=${1:-30}
R=results/fake
rm -rf "$R"
mkdir -p "$R"
for i in $(seq 1 "$N"); do echo "fakeproj$i/arvo_$((1000 + i)),fakeproj$i"; done > "$R/tasks.txt"
# synthetic sampling strata like tasks/sample_manifest.json: 2/3 "easy", 1/3 "uniform"
$PY -c "import json,sys; ids=[l.split(',')[0] for l in open(sys.argv[1])]; \
json.dump({'stratum': {t: ('uniform' if i % 3 == 2 else 'easy') for i, t in enumerate(ids)}}, open(sys.argv[2], 'w'))" \
  "$R/tasks.txt" "$R/manifest.json"
for cfg in b1 b2 p0 p3; do
  $PY -m p2o.cli batch --config "configs/$cfg.yaml" --tasks "$R/tasks.txt" --fake --parallel 4 > "$R/batch_$cfg.log"
  $PY -m p2o.cli grade --config "configs/$cfg.yaml" --tasks "$R/tasks.txt" --fake > "$R/grade_$cfg.log"
done
$PY -m p2o.cli summarize --results "$R" --manifest "$R/manifest.json"
$PY scripts/analyze.py "$R/summary.csv" --out "$R/figs" --all-tasks
