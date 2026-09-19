"""`make backup-critical` — the irreplaceable slice, and the list that must never shrink.

⭐ **Why a separate backup at all.** Measured: the database is 4,359 MB and almost all of it
is re-fetchable from public archives — 3.17M price bars, 701k F&O rows, the stock master, the
instrument dump. The part that cannot be recreated at any price is far smaller, and the full
backup lives on the SAME PARTITION as the database on a machine with one physical disk. "Get
4.4 GB off-box" needs hardware; "get 11 MB off-box" needs an email.

⛔⛔ **THE EXCLUSION LIST IS INVERTED ON PURPOSE.** Wrongly INCLUDING a table costs kilobytes.
Wrongly EXCLUDING one costs the data permanently. So everything is critical by DEFAULT and
each exclusion must earn its place — which also means a NEW table is protected automatically
instead of being silently missed.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "backup_critical.sh"

#: ⛔ These can NEVER be excluded. Each is either a record of something that happened
#: (irrecoverable by definition) or, in `cas_daily`'s case, a real-time-only capture whose
#: window cannot be back-filled at any price.
NEVER_EXCLUDE = (
    "positions", "orders", "order_events", "signals", "signal_outcomes",
    "cas_daily", "ledger_entries", "users", "journal_entries", "watchlists",
    "saved_screens", "gate_config_versions", "universe_rule_inputs", "symbol_history",
)


def _code() -> str:
    """The script with COMMENTS STRIPPED.

    ⛔⛔ Third occurrence of this defect in one week, so it gets a helper. An assertion like
    `"n_live_tup" not in source` matches the comment EXPLAINING why n_live_tup is not used —
    exactly as `"weekday" not in source` matched the note about removing the weekday filter,
    and as the backend wiring lint was satisfied by the words "correct" and "chain" in English
    prose and then by a comment containing `record()`. **Prose must not be able to vote.**
    """
    out = []
    for line in SCRIPT.read_text().splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue
        out.append(line.split("  #")[0] if "  #" in line else line)
    return "\n".join(out)


def _excluded() -> set[str]:
    """The table names in the script's EXCLUDE array, read from the script itself."""
    src = SCRIPT.read_text()
    block = re.search(r"^EXCLUDE=\((.*?)^\)", src, re.S | re.M)
    assert block, "EXCLUDE array not found — the script's shape changed"
    body = re.sub(r"#.*", "", block.group(1))          # strip the per-line reasons
    return {t for t in body.split() if t and not t.startswith("-")}


def test_the_script_exists_and_is_executable() -> None:
    import os

    assert SCRIPT.is_file()
    assert os.access(SCRIPT, os.X_OK)


def test_the_irreplaceable_tables_are_never_excluded() -> None:
    """⛔⛔ THE RATCHET. Adding any of these to EXCLUDE would silently drop the only copy of
    something that cannot be recreated — and would look like a harmless size optimisation."""
    excluded = _excluded()
    leaked = sorted(t for t in NEVER_EXCLUDE if t in excluded)
    assert not leaked, (
        f"{leaked} were added to the exclusion list. These cannot be re-fetched or "
        "regenerated from any source; excluding them makes the critical backup useless "
        "for the exact case it exists for."
    )


def test_cas_daily_is_protected_and_is_the_reason_this_exists() -> None:
    """⭐ 926 rows, captured live between 15:15 and 15:33 IST, and a missed window cannot be
    back-filled AT ANY PRICE. It is the single most irreplaceable thing in the database."""
    assert "cas_daily" not in _excluded()
    assert "cas_daily" in SCRIPT.read_text(), "the script should say why this one matters"


def test_every_exclusion_is_a_public_or_regenerable_source() -> None:
    """An exclusion is a claim that the data can be got back. Each one here is a public NSE
    feed, a public dump, transient auth, or something derived from bars."""
    allowed = {
        "ohlcv_1d", "ohlcv_1m", "ohlcv_5m", "ohlcv_15m", "ohlcv_1h",  # bhavcopy + Kite
        "fo_bhavcopy", "kite_instruments", "index_ohlcv_1d", "india_vix_daily",
        "indices", "index_constituents", "stocks", "corporate_filings",
        "bulk_block_deals", "nse_holidays", "option_chain_snapshots",
        "sr_levels", "strategy_profiles", "alembic_version",
        "user_sessions", "broker_tokens",
    }
    unexplained = _excluded() - allowed
    assert not unexplained, (
        f"{sorted(unexplained)} were excluded without being in the reviewed re-derivable "
        "set. Add them here WITH the source they can be recovered from, or stop excluding them."
    )


def test_the_timescale_internal_schema_is_excluded() -> None:
    """⚠ Without this the dump is 4.4 GB, not 11 MB: hypertable rows live in
    `_timescaledb_internal` chunks, so excluding the parent table alone drags every bar in."""
    assert "--exclude-schema=_timescaledb_internal" in SCRIPT.read_text()


def test_the_dump_is_verified_before_anything_is_pruned() -> None:
    """⭐ The contract `backup_db.sh` already gets right: pruning first is how a backup system
    eats its own history — each failing run deletes one more good copy while writing nothing."""
    src = SCRIPT.read_text()
    assert src.index("pg_restore --list") < src.index("tail -n +$((KEEP + 1))")


def test_the_dump_is_written_atomically() -> None:
    """An interrupted dump must not be mistaken for a complete one."""
    src = SCRIPT.read_text()
    assert ".part" in src and 'mv "$tmp" "$target"' in src


def test_the_manifest_uses_real_counts_not_n_live_tup() -> None:
    """⛔⛔ Measured 2026-09-20: all ten `forensic_*` tables report `n_live_tup = 0` while
    holding 771,585 rows, because the statistic is an autovacuum estimate and those tables
    were never analyzed. A manifest built on it would certify the backup as empty."""
    code = _code()
    assert "n_live_tup" not in code, "the manifest must count rows, not read an estimate"
    assert "count(*)" in code


def test_the_manifest_does_not_swallow_its_own_errors() -> None:
    """⚠ The first version ended `2>/dev/null` and produced an EMPTY manifest in silence."""
    src = SCRIPT.read_text()
    assert "MANIFEST IS EMPTY" in src, "an empty manifest must announce itself"


def test_the_restore_order_limitation_is_documented() -> None:
    """⭐ Measured: restoring this alone into an empty database yields 16 ignored errors, all
    foreign keys pointing at deliberately-excluded tables (15 → stocks, 1 → strategy_profiles).
    The DATA lands; the CONSTRAINTS cannot. It is a COMPANION to the full backup, and saying
    so is the difference between a limitation and a surprise."""
    src = SCRIPT.read_text()
    assert "RESTORE ORDER MATTERS" in src
    assert "COMPANION" in src


def test_make_exposes_it() -> None:
    mk = (ROOT / "Makefile").read_text()
    assert "backup-critical:" in mk
    assert "backup-critical-list:" in mk
