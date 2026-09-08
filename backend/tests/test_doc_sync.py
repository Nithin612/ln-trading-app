"""T9 (+ a T8 debt baseline) — the doc-sync ritual as a failing test.

Our doc-sync ritual is a procedure Claude must REMEMBER to run at the end of every task;
AKShare's equivalent is a test that FAILS. Our own hard-won lesson says why that matters —
*"a documented safety net is worth nothing without a test that fails when it lapses"* (the
`unassessed` tripwire that turned out to be imaginary) — and we applied it to code but never
to process.

This is that fix for the ritual step that is mechanically checkable **without fragile prose
parsing**: working rule **W3**, *"a new config item updates `.env.example` in the same
commit"*. (The STATUS.html gate-mode check the finding also lists is deliberately NOT here:
it means matching modes out of hand-written prose, which is exactly the drift-prone shape a
test should not itself become — the durable fix there is to give STATUS.html a data source,
a separate item. The strict "PHASES stamp newer than every phase-doc commit" check is left to
git-aware tooling; here we assert only that the stamp exists, parses, and is not in the
future.)

Two design choices carried from the findings:

- **Report every problem at once** (AKShare's `..._reports_every_problem_at_once`):
  `collect_problems()` returns the full list in one pass, so a drift sweep is one run, not N.
- **A monotonically-shrinking debt baseline** (T8): 49 Settings fields are undocumented in
  `.env.example` today. `KNOWN_UNDOCUMENTED` freezes that snapshot — not a claim the debt is
  fine, a claim it must not GROW. A new undocumented setting fails immediately; documenting an
  old one is free (the check only requires the current set be a SUBSET of the baseline).
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from pathlib import Path

from app.core.config import Settings

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_EXAMPLE = _REPO_ROOT / ".env.example"
_PHASES = _REPO_ROOT / "docs" / "PHASES.md"

#: Env vars consumed by docker-compose (POSTGRES_*, PGADMIN_*), NOT read through pydantic
#: Settings — so their absence from `Settings.model_fields` is correct, not drift.
INFRA_ONLY_ENV: frozenset[str] = frozenset(
    {"postgres_user", "postgres_password", "postgres_db", "pgadmin_password"}
)

#: The debt baseline (T8). Settings fields with no `.env.example` line as of 2026-09-09. This
#: set may only SHRINK — see the module docstring. When you document one, delete it from here.
KNOWN_UNDOCUMENTED: frozenset[str] = frozenset(
    {
        "cas_capture_enabled",
        "chase_max_r",
        "circuit_band_ttl_s",
        "circuit_bands_enabled",
        "circuit_proximity_pct",
        "cookie_secure",
        "depth_capture_enabled",
        "entry_max_dominant_factor_share",
        "entry_min_scoring_factors",
        "entry_min_sl_atr_mult",
        "liquidity_lookback",
        "liquidity_min_traded_value_inr",
        "live_alert_maxlen",
        "live_cross_rearm_bp",
        "live_outcome_recorder_enabled",
        "live_provisional_enabled",
        "live_provisional_health_ttl_s",
        "live_provisional_hotset_max",
        "live_provisional_key_ttl_s",
        "live_provisional_refresh_s",
        "live_provisional_top_n",
        "live_provisional_trigger_market_max",
        "live_provisional_trigger_window_s",
        "live_signal_dispatch_enabled",
        "live_sltp_within_bp",
        "live_vburst_mult",
        "market_regime_dma_buffer_pct",
        "market_regime_dma_period",
        "market_regime_market_symbol",
        "market_regime_vix_threshold",
        "max_screenshot_bytes",
        "paper_costs_enabled",
        "paper_impact_cap_bps",
        "paper_impact_k_bps",
        "paper_participation_enabled",
        "paper_participation_k",
        "paper_participation_lookback",
        "paper_slippage_bps",
        "paper_slippage_max_bps",
        "paper_spread_fill_enabled",
        "paper_tick_size",
        "profit_lock_atr_k",
        "profit_lock_breakeven_early_inr",
        "profit_lock_breakeven_inr",
        "profit_lock_giveback_inr",
        "profit_lock_trail_start_inr",
        "sector_rs_lookback",
        "sector_rs_min_excess_pct",
        "uploads_dir",
    }
)

_ENV_KEY_RE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]+)\s*=")


def settings_fields() -> set[str]:
    return set(Settings.model_fields)


def env_example_keys(text: str) -> set[str]:
    """Lower-cased env keys named in `.env.example`, whether live (`KEY=`) or commented
    (`# KEY=`). `case_sensitive=False` on the model means env `FOO_BAR` maps to field
    `foo_bar`, so comparison is on the lower-cased name."""
    keys: set[str] = set()
    for line in text.splitlines():
        m = _ENV_KEY_RE.match(line)
        if m:
            keys.add(m.group(1).lower())
    return keys


def env_drift_problems(
    fields: set[str],
    env_keys: set[str],
    *,
    infra_only: frozenset[str] = INFRA_ONLY_ENV,
    known_undocumented: frozenset[str] = KNOWN_UNDOCUMENTED,
) -> list[str]:
    """Pure core (so it is unit-testable with synthetic sets). Returns every problem."""
    problems: list[str] = []
    for key in sorted(env_keys - fields - infra_only):
        problems.append(
            f"`.env.example` key `{key.upper()}=` maps to no Settings field "
            "(renamed/removed setting, or a typo?)"
        )
    new_undocumented = (fields - env_keys) - known_undocumented
    for name in sorted(new_undocumented):
        problems.append(
            f"Settings field `{name}` has no `.env.example` line and is not in the debt "
            "baseline — add the line (W3) or, if intentionally internal, add it to "
            "KNOWN_UNDOCUMENTED with a reason."
        )
    return problems


def _phases_stamp_problems(text: str, *, today: date) -> list[str]:
    m = re.search(r"\(updated (\d{4}-\d{2}-\d{2})\)", text)
    if m is None:
        return ["docs/PHASES.md has no parseable `(updated YYYY-MM-DD)` stamp in its top block"]
    stamp = date.fromisoformat(m.group(1))
    if stamp > today:
        return [f"docs/PHASES.md `(updated {stamp})` is in the FUTURE — a typo, not an update"]
    return []


def collect_problems() -> list[str]:
    """Every doc-sync problem on the real tree, in one pass."""
    problems = env_drift_problems(settings_fields(), env_example_keys(_ENV_EXAMPLE.read_text()))
    problems += _phases_stamp_problems(
        _PHASES.read_text(), today=datetime.now(tz=UTC).date()
    )
    return problems


# --------------------------------------------------------------------------- #
# The flagship: the tree is currently aligned                                 #
# --------------------------------------------------------------------------- #
def test_collect_problems_passes_when_all_aligned() -> None:
    problems = collect_problems()
    assert problems == [], "doc-sync drift detected:\n  - " + "\n  - ".join(problems)


# --------------------------------------------------------------------------- #
# The detector actually detects — synthetic inputs                            #
# --------------------------------------------------------------------------- #
def test_reports_every_problem_at_once() -> None:
    """One run returns ALL violations, not just the first — a drift sweep is one pass."""
    fields = {"kept_setting", "brand_new_setting"}
    env = {"kept_setting", "gone_setting_a", "gone_setting_b"}
    problems = env_drift_problems(
        fields, env, infra_only=frozenset(), known_undocumented=frozenset()
    )
    assert len(problems) == 3  # 2 stale keys + 1 new undocumented field


def test_a_stale_env_key_is_flagged() -> None:
    problems = env_drift_problems(
        {"real"}, {"real", "renamed"}, infra_only=frozenset(), known_undocumented=frozenset()
    )
    assert any("RENAMED" in p for p in problems)


def test_a_new_undocumented_setting_is_flagged() -> None:
    problems = env_drift_problems(
        {"documented", "sneaky_new"}, {"documented"},
        infra_only=frozenset(), known_undocumented=frozenset(),
    )
    assert any("sneaky_new" in p for p in problems)


def test_a_baselined_undocumented_setting_is_not_flagged() -> None:
    """Known debt is allowed to remain — it just cannot grow."""
    problems = env_drift_problems(
        {"old_debt"}, set(), infra_only=frozenset(), known_undocumented=frozenset({"old_debt"})
    )
    assert problems == []


def test_infra_only_env_keys_are_not_stale() -> None:
    problems = env_drift_problems(
        set(), {"postgres_user"}, known_undocumented=frozenset()
    )
    assert problems == []  # docker-compose var, not a Settings field — correctly exempt


def test_phases_future_stamp_is_flagged() -> None:
    text = "## ▶ STATE AT A GLANCE (updated 2099-01-01) — read this block first"
    assert _phases_stamp_problems(text, today=date(2026, 9, 9))


def test_phases_missing_stamp_is_flagged() -> None:
    assert _phases_stamp_problems("no stamp here", today=date(2026, 9, 9))
