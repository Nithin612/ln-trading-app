#!/usr/bin/env bash
#
# Daily Postgres backup for the trading platform.
#
#   ./scripts/backup_db.sh              # back up both databases
#   ./scripts/backup_db.sh --list       # show what is currently retained
#
# ── Why this exists ───────────────────────────────────────────────────────────
# On 2026-09-07 the dev database was destroyed: a pytest run was pointed at
# `trading_platform` instead of `trading_platform_test`, and the suite's autouse
# fixture TRUNCATEs every table before each test. 138 paper positions, every
# signal, and 1,664 `cas_daily` rows were lost. `archive_mode` was off, so there
# was no PITR, and there was no backup of any kind anywhere on the machine.
#
# Two guards came out of that: `tests/conftest.py` now refuses any database whose
# name does not end in `_test`, and this script exists so that the next mistake —
# whatever shape it takes — costs at most one day.
#
# ── Design decisions worth knowing ───────────────────────────────────────────
#  * Dumps run INSIDE the container (`docker exec`), which avoids two problems at
#    once: no password has to live in this file or the environment, and the
#    dumping binary always matches the server (host pg_dump is 17.x, the server
#    is 16.x, and a newer pg_dump refuses an older server).
#  * `-Fc` (custom format) — compressed, and restorable selectively with pg_restore.
#  * ⭐ PRUNING HAPPENS ONLY AFTER A VERIFIED SUCCESSFUL DUMP. Pruning first is the
#    classic way a backup system quietly destroys its own history: each failing run
#    deletes one more good copy while writing nothing. A failed dump here leaves
#    every existing backup untouched and exits non-zero.
#  * Each database gets its own directory so a restore cannot confuse them.
#
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/home/nithin/code/back_ups/trading_platform}"
CONTAINER="${PG_CONTAINER:-tp_postgres}"
PGUSER="${PGUSER:-tpuser}"
KEEP="${KEEP:-3}"

# database name -> directory under BACKUP_ROOT
declare -A DATABASES=(
  ["trading_platform"]="dev"
  ["trading_platform_test"]="test"
)

# A schema-only dump of this project is ~200 KB; anything below this means the
# dump was truncated or the server answered with an error page rather than data.
MIN_BYTES=50000

LOG="${BACKUP_ROOT}/backup.log"

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*" | tee -a "$LOG" >&2; }

list_backups() {
  for db in "${!DATABASES[@]}"; do
    dir="${BACKUP_ROOT}/${DATABASES[$db]}"
    printf '\n%s  (%s)\n' "$dir" "$db"
    ls -lh "$dir" 2>/dev/null | tail -n +2 || printf '  (empty)\n'
  done
}

if [[ "${1:-}" == "--list" ]]; then
  list_backups
  exit 0
fi

mkdir -p "$BACKUP_ROOT"
: > /dev/null

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  log "FATAL: container '$CONTAINER' not found — is the database up? (make up)"
  exit 1
fi

stamp="$(date '+%Y%m%d-%H%M%S')"
failures=0

for db in "${!DATABASES[@]}"; do
  dir="${BACKUP_ROOT}/${DATABASES[$db]}"
  mkdir -p "$dir"
  target="${dir}/${db}-${stamp}.dump"

  # Write to a .partial name first, so an interrupted run can never leave a file
  # that looks like a finished backup and gets counted by the retention pass.
  tmp="${target}.partial"

  if ! docker exec "$CONTAINER" pg_dump -U "$PGUSER" -Fc -d "$db" > "$tmp" 2>>"$LOG"; then
    log "FAIL: pg_dump of '$db' returned non-zero — keeping existing backups untouched"
    rm -f "$tmp"
    failures=$((failures + 1))
    continue
  fi

  size=$(stat -c %s "$tmp" 2>/dev/null || echo 0)
  if [[ "$size" -lt "$MIN_BYTES" ]]; then
    log "FAIL: dump of '$db' is only ${size}B (< ${MIN_BYTES}B) — treating as corrupt"
    rm -f "$tmp"
    failures=$((failures + 1))
    continue
  fi

  # pg_restore --list on the archive is a real integrity check: it parses the
  # custom-format table of contents and fails on a truncated or corrupt file.
  if ! pg_restore --list "$tmp" >/dev/null 2>>"$LOG"; then
    log "FAIL: dump of '$db' does not parse as a valid archive — discarding"
    rm -f "$tmp"
    failures=$((failures + 1))
    continue
  fi

  mv "$tmp" "$target"
  log "OK: $db -> $target ($(numfmt --to=iec "$size" 2>/dev/null || echo "${size}B"))"

  # ⭐ Prune ONLY now, having written a verified backup. Newest first, drop the rest.
  mapfile -t old < <(ls -1t "${dir}"/*.dump 2>/dev/null | tail -n +$((KEEP + 1)))
  for f in "${old[@]:-}"; do
    [[ -n "$f" ]] || continue
    rm -f "$f"
    log "  pruned $(basename "$f")"
  done
done

if [[ "$failures" -gt 0 ]]; then
  log "FINISHED WITH $failures FAILURE(S)"
  exit 1
fi

log "all backups OK (retaining $KEEP per database)"
