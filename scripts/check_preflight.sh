#!/usr/bin/env bash
# `make check` preflight (A14, Bucket C #5, 2026-10-03).
#
# The full gate has stalled at test_walkforward_matches_golden[gainer_925] — diagnosed as RAM/disk
# STARVATION, not a code hang (~768 MiB free + a full disk, 2026-08-12). The recorded remedy was a
# human remembering `free -h` / `df -h`; this does it every time, before the long legs start.
#   refuse: available RAM < 1 GiB, or free disk < 2 GiB      (the observed stall regime)
#   warn:   available RAM < 3 GiB, or another pytest is running (shared test DB → phantom failures)
# CHECK_PREFLIGHT=warn downgrades a refusal to a warning.
set -euo pipefail

avail_kib=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
disk_free_kib=$(df -Pk "$(dirname "$0")/.." | awk 'NR==2 {print $4}')
avail_gib=$(awk -v k="$avail_kib" 'BEGIN {printf "%.1f", k/1048576}')
disk_gib=$(awk -v k="$disk_free_kib" 'BEGIN {printf "%.1f", k/1048576}')
load=$(cut -d' ' -f1 /proc/loadavg)
echo "preflight: RAM available ${avail_gib} GiB · disk free ${disk_gib} GiB · load ${load}"

problems=()
(( avail_kib < 1048576 )) && problems+=("available RAM ${avail_gib} GiB < 1 GiB")
(( disk_free_kib < 2097152 )) && problems+=("free disk ${disk_gib} GiB < 2 GiB")
(( avail_kib < 3145728 && avail_kib >= 1048576 )) && \
  echo "⚠ preflight: available RAM ${avail_gib} GiB is low — the walk-forward golden stalled under pressure before"
if pgrep -f "[p]ytest" >/dev/null; then
  echo "⚠ preflight: another pytest is running — the shared test DB makes concurrent runs fail spuriously"
fi

if (( ${#problems[@]} )); then
  for p in "${problems[@]}"; do echo "✗ preflight: $p"; done
  if [[ "${CHECK_PREFLIGHT:-refuse}" == "warn" ]]; then
    echo "⚠ preflight: CHECK_PREFLIGHT=warn — continuing anyway"
  else
    echo "  free memory/disk first (stray uvicorn/vite/pytest?), or CHECK_PREFLIGHT=warn to override"
    exit 1
  fi
fi
