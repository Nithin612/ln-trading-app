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
# stdin from /dev/null, NOT --foreground (2026-10-03). Without --foreground, `timeout` runs the
# command in a BACKGROUND process group; in an interactive terminal anything in it that reads the
# TTY is frozen by SIGTTIN (state `T`) until the bound kills it. Every pytest leg did exactly that
# — `uv run pytest` touches stdin — so `make replay` "timed out" at 300 s in a terminal while
# passing in 19 s anywhere without one. --foreground would fix the freeze but signals only the
# direct child (`uv`), leaving a hung python grandchild alive past the bound — the opposite of a
# timebox. No leg is interactive; output still goes to the terminal (colours kept).
timeout --kill-after=30 "$bound" "$@" </dev/null
rc=$?
if (( rc == 124 || rc == 137 )); then
  echo "⛔ timebox: '$leg' exceeded ${bound}s (measured worst ${measured}s) and was stopped."
  echo "   A stall here has been resource starvation before — check \`free -h\`, \`df -h\`, \`uptime\`"
  echo "   and stray uvicorn/vite/pytest processes. A per-test traceback dump (pytest"
  echo "   faulthandler_timeout) shows WHERE it stuck."
fi
exit $rc
