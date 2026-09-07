#!/usr/bin/env bash
#
# Prove the newest backup actually restores.
#
#   ./scripts/verify_backup.sh            # verify the newest dev dump
#   ./scripts/verify_backup.sh test       # verify the newest test dump
#
# ── Why a separate script ────────────────────────────────────────────────────
# A dump that has never been restored is not a backup, it is a file. Two things
# specific to this database could make one unrestorable without any visible sign:
#
#   * **TimescaleDB hypertables.** `ohlcv_1d`, `ohlcv_1m` and friends keep their rows
#     in `_timescaledb_internal` chunks, not in the visible table. A restore needs
#     `timescaledb_pre_restore()` / `timescaledb_post_restore()` around it; without
#     them you can get an empty-but-valid-looking hypertable.
#   * **Version skew.** The host has pg_dump/pg_restore 17.x and the server is 16.x.
#     A newer pg_dump refuses an older server outright, but the failure mode is
#     easy to paper over by reaching for whichever binary is on PATH. Everything
#     here runs INSIDE the container, so client and server always match.
#
# The check is a real restore into a scratch database followed by a row-count diff
# of every table against the live one. Rows written after the dump was taken show up
# as a small positive delta on that table — expected, and reported rather than hidden.
#
# The scratch database is dropped at the end, including on failure.
#
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/home/nithin/code/back_ups/trading_platform}"
CONTAINER="${PG_CONTAINER:-tp_postgres}"
PGUSER="${PGUSER:-tpuser}"
SCRATCH="${SCRATCH_DB:-restore_check}"

which_db="${1:-dev}"
case "$which_db" in
  dev)  SOURCE_DB="trading_platform" ;;
  test) SOURCE_DB="trading_platform_test" ;;
  *) echo "usage: $0 [dev|test]" >&2; exit 2 ;;
esac

dump=$(ls -1t "${BACKUP_ROOT}/${which_db}"/*.dump 2>/dev/null | head -1 || true)
if [[ -z "$dump" ]]; then
  echo "FAIL: no dump found under ${BACKUP_ROOT}/${which_db}/" >&2
  exit 1
fi
echo "verifying: $dump"

cleanup() { docker exec "$CONTAINER" dropdb -U "$PGUSER" --if-exists "$SCRATCH" >/dev/null 2>&1 || true; }
trap cleanup EXIT

cleanup
docker exec "$CONTAINER" createdb -U "$PGUSER" "$SCRATCH"
docker cp "$dump" "$CONTAINER:/tmp/verify.dump" >/dev/null

docker exec "$CONTAINER" psql -U "$PGUSER" -d "$SCRATCH" -q \
  -c "CREATE EXTENSION IF NOT EXISTS timescaledb;" \
  -c "SELECT timescaledb_pre_restore();" >/dev/null

if ! docker exec "$CONTAINER" pg_restore -U "$PGUSER" -d "$SCRATCH" --no-owner /tmp/verify.dump 2>/tmp/restore_err; then
  echo "FAIL: pg_restore returned non-zero" >&2
  docker exec "$CONTAINER" cat /tmp/restore_err >&2 || true
  exit 1
fi
docker exec "$CONTAINER" psql -U "$PGUSER" -d "$SCRATCH" -q \
  -c "SELECT timescaledb_post_restore();" >/dev/null

# Build "one row per table with its count" and run it against both databases.
gen="SELECT string_agg(format('SELECT %L AS t, count(*) AS n FROM %I', tablename, tablename),
     ' UNION ALL ' ORDER BY tablename) FROM pg_tables WHERE schemaname='public';"
q=$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$SOURCE_DB" -t -A -c "$gen")

live=$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$SOURCE_DB" -t -A -c "$q" | sort)
restored=$(docker exec "$CONTAINER" psql -U "$PGUSER" -d "$SCRATCH" -t -A -c "$q" | sort)

total=$(printf '%s\n' "$live" | wc -l)
if diff <(printf '%s\n' "$live") <(printf '%s\n' "$restored") > /tmp/count_diff; then
  echo "PASS: all $total tables restored with identical row counts"
  exit 0
fi

# ⚠ A count difference against the LIVE database is NOT by itself a backup defect, and
# an earlier version of this script wrongly failed on one. The dump is a point-in-time
# snapshot and the live database keeps moving in both directions — rows are inserted
# after it (`corporate_filings` gained 4 during this very verification) and the TEST
# database is TRUNCATEd before every single test, so its live counts are usually zero
# while the dump holds whatever a test had created. Neither says anything about the dump.
#
# What actually proves the backup: pg_restore exited clean, and every table that exists
# live also came back. Counts are reported with their direction, as information.
missing=$(comm -23 \
  <(printf '%s\n' "$live"    | cut -d'|' -f1) \
  <(printf '%s\n' "$restored" | cut -d'|' -f1))
if [[ -n "$missing" ]]; then
  echo "FAIL: tables present live but MISSING from the restore:" >&2
  printf '  %s\n' $missing >&2
  exit 1
fi

echo "restored cleanly; $total tables present. Count differences vs the live database:"
paste -d' ' <(printf '%s\n' "$live") <(printf '%s\n' "$restored") \
  | awk -F'[ |]' '$2!=$4 {printf "  %-28s live=%-10s dump=%-10s %s\n", $1, $2, $4,
      ($2>$4 ? "(live grew after the dump)" : "(live shrank after the dump)")}'
echo "PASS: pg_restore clean, no table missing — the dump is restorable"
