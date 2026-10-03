#!/usr/bin/env bash
# timebox.sh LEG BOUND_SECS MEASURED_SECS -- command...   (A14, Bucket C #5, 2026-10-03)
#
# Every `make check` leg runs under a bound of ~2× its measured worst, so a starved or hung leg
# FAILS with a reason instead of stalling silently for hours (`test_walkforward_matches_golden`
# stalled under RAM/disk pressure, 2026-08-12). SIGTERM at the bound, SIGKILL 30 s later.
set -uo pipefail
leg=$1 bound=$2 measured=$3
shift 3
[[ "${1:-}" == "--" ]] && shift
timeout --kill-after=30 "$bound" "$@"
rc=$?
if (( rc == 124 || rc == 137 )); then
  echo "⛔ timebox: '$leg' exceeded ${bound}s (measured worst ${measured}s) and was stopped."
  echo "   A stall here has been resource starvation before — check \`free -h\`, \`df -h\`, \`uptime\`"
  echo "   and stray uvicorn/vite/pytest processes. A per-test traceback dump (pytest"
  echo "   faulthandler_timeout) shows WHERE it stuck."
fi
exit $rc
