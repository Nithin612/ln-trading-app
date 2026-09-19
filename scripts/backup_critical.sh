#!/usr/bin/env bash
#
# The IRREPLACEABLE slice of the database — small enough to put anywhere.
#
#   ./scripts/backup_critical.sh              # dump it
#   ./scripts/backup_critical.sh --list       # what is retained
#
# ── Why this exists, and why it is not just "a smaller backup" ───────────────
# Measured 2026-09-19: the database is 4,359 MB, and the part that CANNOT be
# recreated from any source is ~995 rows. Everything else — 3.17M price bars,
# 701k F&O rows, the stock master, the instrument dump — is re-fetchable from
# public archives. Slow, but recoverable.
#
# That matters because the full backup is on the SAME PARTITION as the database
# (/dev/nvme0n1p5), and this machine has one physical disk, no removable media
# and no network mount. "Get 4.4 GB off-box" needs hardware. "Get a few hundred
# KB off-box" needs an email. This makes the off-box problem tractable instead
# of expensive.
#
# ⭐⭐ THE EXCLUSION LIST IS THE INVERSE OF THE USUAL ALLOWLIST, DELIBERATELY.
# Wrongly INCLUDING a table costs a few KB. Wrongly EXCLUDING one costs the data
# permanently. So everything is critical BY DEFAULT and each exclusion must earn
# its place below — which also means a NEW table is protected automatically
# rather than silently missed, and `test_backup_critical.py` fails if an
# exclusion is added without a reason.
#
# ⚠ `cas_daily` is the reason this is urgent. 926 rows, real-time capture only
# (15:15-15:33 IST), and a missed window cannot be back-filled AT ANY PRICE.
# No backup protects it from the worker being down — only running the worker does.
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/home/nithin/code/back_ups/trading_platform}"
OUT_DIR="${CRITICAL_DIR:-${BACKUP_ROOT}/critical}"
CONTAINER="${PG_CONTAINER:-tp_postgres}"
PGUSER="${PGUSER:-tpuser}"
DB="${PGDATABASE:-trading_platform}"
KEEP="${CRITICAL_KEEP:-30}"     # tiny files — keep a month, not three days

# ── Excluded, each with the reason it can be recreated ───────────────────────
#   bars + public feeds : re-fetchable from the NSE archive / Kite
#   auth                : regenerated on next login
#   derived             : recomputed from bars
EXCLUDE=(
  ohlcv_1d ohlcv_1m ohlcv_5m ohlcv_15m ohlcv_1h   # bhavcopy + Kite history
  fo_bhavcopy                                      # NSE F&O archive
  kite_instruments                                 # public daily dump
  index_ohlcv_1d india_vix_daily indices index_constituents  # NSE indices CSV
  stocks                                           # seed_stocks.py, public CSVs
  corporate_filings bulk_block_deals               # NSE
  nse_holidays                                     # public calendar
  option_chain_snapshots                           # re-captured intraday
  sr_levels                                        # derived from bars
  strategy_profiles                                # seeded by migration
  alembic_version                                  # schema state, from migrations
  user_sessions broker_tokens                      # transient auth
)

log() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$*" >&2; }

if [[ "${1:-}" == "--list" ]]; then
  ls -lh "$OUT_DIR" 2>/dev/null | tail -n +2 || echo "(nothing retained)"
  exit 0
fi

mkdir -p "$OUT_DIR"
docker inspect "$CONTAINER" >/dev/null 2>&1 || { log "FATAL: container '$CONTAINER' not found"; exit 1; }

args=()
for t in "${EXCLUDE[@]}"; do args+=(--exclude-table="public.${t}"); done
# ⚠ TimescaleDB keeps hypertable rows in _timescaledb_internal chunks. Excluding the
# parent alone would still drag every chunk in, which is the whole 4.4 GB.
args+=(--exclude-schema=_timescaledb_internal)

stamp="$(date '+%Y%m%d_%H%M%S')"
target="${OUT_DIR}/critical_${stamp}.dump"
tmp="${target}.part"

if ! docker exec "$CONTAINER" pg_dump -U "$PGUSER" -d "$DB" -Fc "${args[@]}" > "$tmp" 2>/dev/null; then
  log "FAIL: pg_dump failed — leaving existing backups untouched"; rm -f "$tmp"; exit 1
fi

# ⭐ Verified before it counts as a backup, and BEFORE anything is pruned — the same
# contract as backup_db.sh. pg_restore --list parses the archive's table of contents and
# fails on a truncated or corrupt file.
if ! pg_restore --list "$tmp" >/dev/null 2>&1; then
  log "FAIL: dump does not parse as a valid archive — discarding"; rm -f "$tmp"; exit 1
fi

mv "$tmp" "$target"
size="$(stat -c%s "$target")"
log "OK: $target ($(numfmt --to=iec "$size" 2>/dev/null || echo "${size}B"))"

# A plain-text manifest beside it: row counts you can eyeball without a restore.
#
# ⛔⛔ COUNTS COME FROM count(*), NOT pg_stat_user_tables.n_live_tup. Measured 2026-09-20:
# all ten `forensic_*` tables report n_live_tup = 0 while actually holding 771,585 rows.
# n_live_tup is an ESTIMATE maintained by autovacuum, and a table never analyzed reports
# zero — a manifest built on it would certify a backup as containing nothing.
#
# ⚠ And it does NOT swallow errors. The first version ended `2>/dev/null` and produced an
# EMPTY manifest in silence, which is the exact defect being removed elsewhere this week.
manifest="${target%.dump}.manifest.txt"
{
  echo "critical backup  $stamp"
  echo "database         $DB"
  echo "dump bytes       $size"
  echo "excluded         ${EXCLUDE[*]}"
  echo
  printf '  %-38s %10s\n' "table" "rows"
  for t in $(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$DB" -At -c "
      SELECT c.relname FROM pg_class c JOIN pg_namespace ns ON ns.oid=c.relnamespace
      WHERE ns.nspname='public' AND c.relkind='r'
        AND NOT (c.relname = ANY(string_to_array('${EXCLUDE[*]}',' ')))
      ORDER BY c.relname"); do
    n=$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$DB" -At -c "SELECT count(*) FROM \"$t\"")
    [[ "${n:-0}" -gt 0 ]] && printf '  %-38s %10s\n' "$t" "$n"
  done
} > "$manifest" 2>"${manifest}.err"
if [[ -s "${manifest}.err" ]]; then
  log "⚠ manifest generation reported errors — see ${manifest}.err"
else
  rm -f "${manifest}.err"
fi
listed=$(grep -c '^  ' "$manifest" 2>/dev/null || echo 0)
[[ "$listed" -gt 1 ]] || log "⚠ MANIFEST IS EMPTY — the dump may be fine, but that is unverified"
log "manifest: $manifest ($((listed - 1)) tables with rows)"

mapfile -t old < <(ls -1t "${OUT_DIR}"/critical_*.dump 2>/dev/null | tail -n +$((KEEP + 1)))
for f in "${old[@]:-}"; do
  [[ -n "$f" ]] || continue
  rm -f "$f" "${f%.dump}.manifest.txt"
  log "  pruned $(basename "$f")"
done

log "critical backup complete — small enough to copy anywhere (OFFBOX_DEST, email, cloud)"
log ""
log "⚠ RESTORE ORDER MATTERS — this is a COMPANION to the full backup, not a replacement."
log "   Measured: restoring this into an EMPTY database yields 16 ignored errors, all of them"
log "   foreign keys pointing at deliberately-excluded tables (15 -> stocks, 1 ->"
log "   strategy_profiles). The DATA lands correctly; the CONSTRAINTS cannot, because their"
log "   targets are not here. So:"
log "     1. restore or re-derive the public tables first (stocks, bars, instruments)"
log "     2. THEN restore this dump"
log "   Restoring it alone gives you the irreplaceable rows without referential integrity —"
log "   which is still far better than not having them, but is not a working database."
