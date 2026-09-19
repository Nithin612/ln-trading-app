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

# ── ITEM 26: the OFF-BOX copy ────────────────────────────────────────────────
# ⛔⛔ Measured 2026-09-19: BACKUP_ROOT is on /dev/nvme0n1p5 — THE SAME PARTITION AS THE
# DATABASE. The existing backup survives exactly one failure mode, the logical wipe that
# actually happened on 2026-09-07, and none of the others: a disk failure, a filesystem
# corruption or an `rm -rf` on that partition takes the database and every backup together.
#
# ⭐ Set OFFBOX_DEST to a path on another device (a mounted NAS, an external disk). It is
# CHECKED, not trusted — `offbox_check.sh` refuses a destination on the same filesystem and
# warns on one sharing a physical disk, because "not really off-box" is otherwise invisible.
#
# ⚠ UNSET is reported LOUDLY on every run rather than passing quietly. A backup system whose
# gap you cannot see is the state this project was already in once.
OFFBOX_DEST="${OFFBOX_DEST:-}"
OFFBOX_KEEP="${OFFBOX_KEEP:-7}"
REQUIRE_OFFBOX="${REQUIRE_OFFBOX:-0}"

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

# ── ITEM 26 — the off-box copy, after every dump has been verified ───────────
# ⭐ Runs LAST and on verified files only, for the same reason pruning does: copying a dump
# that failed its integrity check off-box would propagate a corrupt archive and, worse, make
# the off-box copy look current.
offbox_script="$(dirname "$0")/offbox_check.sh"

if [[ -z "$OFFBOX_DEST" ]]; then
  log "⚠ NO OFF-BOX COPY: OFFBOX_DEST is unset. Backups live on $(df --output=source "$BACKUP_ROOT" 2>/dev/null | tail -1 | tr -d ' '), the same device as the database — a disk failure loses both."
  [[ "$REQUIRE_OFFBOX" == "1" ]] && { log "FATAL: REQUIRE_OFFBOX=1 and no destination set"; exit 1; }
  exit 0
fi

if [[ -x "$offbox_script" ]]; then
  verdict="$("$offbox_script" "$BACKUP_ROOT" "$OFFBOX_DEST" 2>&1)"; rc=$?
  log "off-box check: $verdict"
  case "$rc" in
    4) log "FATAL: OFFBOX_DEST is on the same filesystem as the backups — refusing to pretend"; exit 1 ;;
    2) log "FATAL: OFFBOX_DEST unusable"; exit 1 ;;
    3) log "⚠ proceeding, but this survives filesystem corruption only — not a disk failure" ;;
  esac
else
  log "⚠ offbox_check.sh not found beside this script — copying WITHOUT verifying the destination"
fi

copied=0
for db in "${!DATABASES[@]}"; do
  sub="${DATABASES[$db]}"
  mkdir -p "${OFFBOX_DEST}/${sub}"
  newest="$(ls -1t "${BACKUP_ROOT}/${sub}"/*.dump 2>/dev/null | head -1 || true)"
  [[ -n "$newest" ]] || { log "  off-box: nothing to copy for $db"; continue; }
  if cp -p "$newest" "${OFFBOX_DEST}/${sub}/$(basename "$newest").part" \
     && mv "${OFFBOX_DEST}/${sub}/$(basename "$newest").part" "${OFFBOX_DEST}/${sub}/$(basename "$newest")"; then
    # ⭐ Written to `.part` and renamed: a copy interrupted mid-flight must not be mistaken
    # for a complete backup by whatever reads this directory next.
    copied=$((copied + 1))
    log "  off-box: $(basename "$newest") -> ${OFFBOX_DEST}/${sub}/"
  else
    log "FAIL: off-box copy of $(basename "$newest") failed"
    exit 1
  fi
  mapfile -t oldoff < <(ls -1t "${OFFBOX_DEST}/${sub}"/*.dump 2>/dev/null | tail -n +$((OFFBOX_KEEP + 1)))
  for f in "${oldoff[@]:-}"; do
    [[ -n "$f" ]] && rm -f "$f" && log "  off-box pruned $(basename "$f")"
  done
done
log "off-box copies written: $copied (retaining $OFFBOX_KEEP per database)"
