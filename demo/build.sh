#!/usr/bin/env bash
# Rebuild the demo video from scratch.  Usage: bash demo/build.sh [--preview]
#   --preview renders 480p15 (fast) instead of 1080p30.
set -euo pipefail
DEMO="$(cd "$(dirname "$0")" && pwd)"
cd "$DEMO"

if [ ! -x .venv/bin/python ]; then
  uv venv -q --python 3.11 .venv
  uv pip install -q --python .venv/bin/python --index-strategy unsafe-best-match \
    --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
fi
PY=.venv/bin/python

QFLAG=(-qh --fps 30); QDIR=1080p30
if [ "${1:-}" = "--preview" ]; then QFLAG=(-ql); QDIR=480p15; fi

$PY data.py > /dev/null                 # fails loudly if any source file is missing
$PY narration.py > /dev/null            # draft script.md (overwritten with timings below)

for pair in s1_problem:S1Problem s2_system:S2System s3_run:S3Run s4_findings:S4Findings s5_next:S5Next; do
  f=${pair%%:*}; c=${pair##*:}
  PYTHONPATH=. .venv/bin/manim "${QFLAG[@]}" --media_dir media --disable_caching \
    "scenes/$f.py" "$c" 2>&1 | grep -E "Rendered|Error|Traceback" || true
  test -f "media/videos/$f/$QDIR/$c.mp4"
done

$PY assemble.py "$QDIR"
# one still per narration beat for review, then the 6 representative ones
rm -rf out/stills && mkdir -p out/stills/all
for pair in s1_problem:S1Problem s2_system:S2System s3_run:S3Run s4_findings:S4Findings s5_next:S5Next; do
  f=${pair%%:*}; c=${pair##*:}
  $PY stills.py "$f" "media/videos/$f/$QDIR/$c.mp4" out/stills/all > /dev/null
done
for s in s1_problem_2 s2_system_3 s3_run_5 s3_run_6 s4_findings_2 s4_findings_4; do
  command cp -f "out/stills/all/$s.png" out/stills/
done
echo "stills: $(ls out/stills/*.png | wc -l) in demo/out/stills/"
