#!/usr/bin/env bash
# shadow_day.sh — run the slice-3.7 shadow-compare for one or more trading
# days and append a PASS/FAIL verdict to a cumulative log. Thin wrapper over
# scripts/shadow_week.py (Rust vs frozen-Python 1d-close double-check).
#
# Usage:
#   scripts/shadow_day.sh                                   # today (IST)
#   scripts/shadow_day.sh 2026-07-23                        # one day
#   scripts/shadow_day.sh 2026-07-20 2026-07-21 2026-07-22  # backfilled days
#
# Run AFTER the evening EOD beats land the day's committed 1d close
# (~19:30 IST — equities EOD is 18:40, nightly generation 19:15). Running
# earlier scores an absent bar.
#
# Exit 0 iff EVERY requested day is clean (zero decision diffs, zero
# errors); nonzero if any day disagrees or the runner errors — so a daily
# run fails loudly. Each day's full artifact stays in
# backend/shadow/shadow-<day>.json; the one-line verdicts accumulate in
# backend/shadow/shadow_week.log.
set -uo pipefail

# This script lives in backend/scripts/; resolve backend/ so `uv run` works
# from any caller cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
cd "$BACKEND_DIR" || exit 2

SHADOW_DIR="$BACKEND_DIR/shadow"
LOG="$SHADOW_DIR/shadow_week.log"
mkdir -p "$SHADOW_DIR"

# No args → let shadow_week.py default to today IST (empty token below).
DAYS=("$@")
if [ ${#DAYS[@]} -eq 0 ]; then
  DAYS=("")
fi

overall=0
for day in "${DAYS[@]}"; do
  if [ -n "$day" ]; then
    run_args=(--day "$day")
    label="$day"
  else
    run_args=()
    label="today"
  fi

  echo "=== shadow_day: $label ==="
  uv run python scripts/shadow_week.py "${run_args[@]}"
  code=$?

  # Resolve the concrete report path. For the today-default case, derive
  # the date in IST exactly as shadow_week.py does.
  if [ -z "$day" ]; then
    day="$(TZ=Asia/Kolkata date +%F)"
  fi
  report="$SHADOW_DIR/shadow-$day.json"

  # Pull the summary counts for the log line (stdlib json only — no venv).
  counts="(no report written)"
  if [ -f "$report" ]; then
    parsed="$(python3 - "$report" <<'PY' 2>/dev/null
import json, sys
r = json.load(open(sys.argv[1]))
s = r.get("summary", {})
print("matched=%s/%s diffs=%s errors=%s both_emitted=%s skipped=%s" % (
    s.get("matched"), s.get("compared"),
    s.get("diffs"), s.get("errors"),
    s.get("both_emitted"), s.get("skipped_no_data"),
))
PY
)"
    [ -n "$parsed" ] && counts="$parsed"
  fi

  ts="$(TZ=Asia/Kolkata date +'%Y-%m-%d %H:%M:%S %Z')"
  if [ "$code" -eq 0 ]; then
    verdict="PASS"
  else
    verdict="FAIL(exit=$code)"
    overall=1
  fi
  echo "$ts  day=$day  $verdict  $counts" | tee -a "$LOG"
  echo
done

if [ "$overall" -ne 0 ]; then
  echo "shadow_day: at least one day FAILED — see $LOG and the per-day report(s)." >&2
  echo "Zero diffs are required to close Phase 3; investigate before continuing the week." >&2
fi
exit "$overall"
