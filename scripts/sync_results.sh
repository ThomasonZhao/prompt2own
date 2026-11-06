#!/usr/bin/env bash
# Periodically push run results to the `results` branch so a lost VM loses at most one interval.
# Copies results/runs/**/{run.json,events.jsonl,ledger.jsonl}, results/grades/** and results/summary.csv
# into a separate git worktree on branch `results`, force-adds them (past .gitignore), commits, pushes.
# Never touches main or the code branch.
#
# Usage (from the repo root): bash scripts/sync_results.sh [interval_s=900]   # loop
#                             bash scripts/sync_results.sh --once              # single sync
# Run in tmux: tmux new-window -t <session> -n sync 'bash scripts/sync_results.sh 2>&1 | tee -a logs/sync.log'
set -uo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
WT="${P2O_RESULTS_WT:-$REPO/../prompt2own-results}"
BRANCH=results
INTERVAL=900
ONCE=0
[ "${1:-}" = "--once" ] && ONCE=1
[[ "${1:-}" =~ ^[0-9]+$ ]] && INTERVAL="$1"

setup() {
  if [ ! -d "$WT/.git" ] && [ ! -f "$WT/.git" ]; then
    git -C "$REPO" fetch -q origin "$BRANCH" 2>/dev/null || true
    if git -C "$REPO" show-ref -q --verify "refs/heads/$BRANCH"; then
      git -C "$REPO" worktree add -q "$WT" "$BRANCH"
    elif git -C "$REPO" show-ref -q --verify "refs/remotes/origin/$BRANCH"; then
      git -C "$REPO" worktree add -q -b "$BRANCH" "$WT" "origin/$BRANCH"
    else
      git -C "$REPO" worktree add -q -b "$BRANCH" "$WT" HEAD
    fi
  fi
}

sync_once() {
  local cur
  cur="$(git -C "$WT" rev-parse --abbrev-ref HEAD)"
  if [ "$cur" != "$BRANCH" ]; then
    echo "$(date -u +%FT%TZ) REFUSING: worktree $WT is on '$cur', not '$BRANCH'" >&2
    return 1
  fi
  mkdir -p "$WT/results"
  # copy only the allowed files; never delete on the branch side (a lost local file must not erase history)
  [ -d "$REPO/results/runs" ] && rsync -a --prune-empty-dirs \
      --include='*/' --include='run.json' --include='events.jsonl' --include='ledger.jsonl' --exclude='*' \
      "$REPO/results/runs/" "$WT/results/runs/"
  [ -d "$REPO/results/grades" ] && rsync -a "$REPO/results/grades/" "$WT/results/grades/"
  [ -f "$REPO/results/summary.csv" ] && cp -p "$REPO/results/summary.csv" "$WT/results/summary.csv"

  local paths=()
  [ -d "$WT/results/runs" ] && paths+=(results/runs)
  [ -d "$WT/results/grades" ] && paths+=(results/grades)
  [ -f "$WT/results/summary.csv" ] && paths+=(results/summary.csv)
  [ ${#paths[@]} -eq 0 ] && { echo "$(date -u +%FT%TZ) nothing to sync yet"; return 0; }
  git -C "$WT" add -f -- "${paths[@]}"
  if git -C "$WT" diff --cached --quiet; then
    echo "$(date -u +%FT%TZ) no changes"
  else
    local n
    n="$(git -C "$WT" diff --cached --name-only | wc -l)"
    git -C "$WT" commit -q -m "results sync $(date -u +%FT%TZ) ($n files)"
    echo "$(date -u +%FT%TZ) committed $n files"
  fi
  # explicit refspec: only ever push the results branch
  if git -C "$WT" push -q origin "refs/heads/$BRANCH:refs/heads/$BRANCH"; then
    echo "$(date -u +%FT%TZ) pushed $BRANCH"
  else
    echo "$(date -u +%FT%TZ) push FAILED (will retry next interval)" >&2
  fi
}

setup || exit 1
if [ "$ONCE" = 1 ]; then sync_once; exit $?; fi
while true; do
  sync_once
  sleep "$INTERVAL"
done
