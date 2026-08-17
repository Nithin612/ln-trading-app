from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env regardless of the working directory:
# config.py lives at backend/app/core/config.py → parents[3] = project root
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ────────────────────────────────────────────────────────────
    database_url: str           # postgresql+asyncpg://... (app path)
    database_url_sync: str      # postgresql+psycopg://... (alembic path)

    # ── Redis ───────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    # live-worker tick/pulse JSONL recording (Phase 3; empty = off)
    live_record_path: str | None = None
    # Per-candle Celery signal-regeneration dispatch. OFF by default: with
    # no Celery worker consuming (e.g. a soak) send_task still ENQUEUES to
    # the Redis broker and succeeds, so the TTL-less "celery" list grows
    # unboundedly until Redis hits maxmemory and refuses ALL writes (the
    # 2026-07-13 soak OOM). Turn ON only alongside a running worker AND
    # active intraday profiles worth regenerating intraday.
    live_signal_dispatch_enabled: bool = False

    # Order-book depth capture (Phase 6.8.1). Extracts top-of-book from the
    # already-subscribed MODE_FULL ticks into `depth:{stock_id}` (Redis, 60 s
    # TTL) for the spread-aware paper fill model + liquidity gates. PROVISIONAL
    # live data — never a candle, never a backtest. Cheap (one Redis SET per
    # ticked stock); a kill switch, on by default so the data accrues.
    depth_capture_enabled: bool = True

    # ── Live tick triggers (Phase 3, slice 3.5) ─────────────────────────────
    # Alert thresholds only — they gate ALERTS, never signals; signal
    # semantics stay in SIGNAL_ENGINE.md. Zone width mirrors §2.5 proximity.
    live_level_refresh_s: int = 30       # signal-level refresh cadence
    live_entry_zone_pct: float = 0.5     # entry-zone half-width, % of entry
    live_sltp_within_bp: int = 25        # SL/TP proximity band (0.25%)
    live_cross_rearm_bp: int = 10        # PDH/PDL/S&R cross re-arm band
    live_vburst_mult: float = 3.0        # forming 5m vol ≥ mult × 20d avg
    live_alert_stream: str = "alerts:live"   # Redis Stream (at-least-once)
    live_alert_maxlen: int = 10_000      # stream MAXLEN ~ cap

    # ── Provisional confidence + leaderboards (3.5-deferred; design pinned
    # 2026-07-11, ledger §Decisions). Derived observability view ONLY —
    # never engine events, never recorded/replayed, never in backtests.
    live_provisional_enabled: bool = True    # reversibility switch (worker thread)
    live_provisional_refresh_s: float = 3.0  # cycle-START cadence (pinned 1–5 s)
    live_provisional_hotset_max: int = 150   # hot-set cap; clipping is logged
    live_provisional_trigger_window_s: int = 900  # "near-trigger" recency window
    live_provisional_top_n: int = 20         # rows per style leaderboard
    live_provisional_key_ttl_s: int = 60     # leaderboard SET key TTL

    # ── Signal-outcome recorder (Phase 3, slice 3.6) ─────────────────────
    # Durable alerts-stream consumer persisting first entry/SL/TP touches
    # per signal — Phase-6 outcome data. Observability only.
    live_outcome_recorder_enabled: bool = True
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── JWT ─────────────────────────────────────────────────────────────────
    jwt_secret_key: str          # required — no default; fails loudly if missing
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 45
    jwt_refresh_token_expire_days: int = 7

    # ── Cookie ──────────────────────────────────────────────────────────────
    cookie_secure: bool = False   # set True in production (HTTPS)

    # ── App ─────────────────────────────────────────────────────────────────
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "DEBUG"

    # ── CORS ────────────────────────────────────────────────────────────────
    # In .env use JSON array: CORS_ORIGINS=["http://localhost:5173"]
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # ── Zerodha Kite Connect ─────────────────────────────────────────────────
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_redirect_url: str = "http://localhost:8000/api/v1/broker/kite/callback"
    kite_access_token: str = ""

    # ── F&O chain recorder (Phase 0 recorders) ──────────────────────────────
    # Comma-separated underlyings to snapshot every minute during market hours
    fo_chain_underlyings: str = "NIFTY,BANKNIFTY"
    # Distinct strikes kept around spot (2N+1 nearest), per expiry side
    fo_chain_strikes_each_side: int = 10

    # ── File uploads ────────────────────────────────────────────────────────
    uploads_dir: str = "uploads"          # relative to backend root; created on first use
    max_screenshot_bytes: int = 5_242_880  # 5 MB

    # ── Engine selection (Phase 1) ──────────────────────────────────────────
    # "python" = frozen pandas reference · "rust" = tradecore (parity-gated)
    engine_impl: str = "python"

    # ── Trading defaults ────────────────────────────────────────────────────
    default_risk_per_trade_pct: float = 2.0
    min_signal_confidence: int = 70

    # Regime-eligibility overlay (app/signals/regime_guard.py). The §8 walk-forward
    # (docs/analysis/gate-walkforward-*.md) found transitional-ADX (20–25) entries
    # net-negative and skipping them improves win rate / Sharpe / drawdown OOS.
    #   off    — no gate.
    #   shadow — measure what it WOULD suppress; the order path never acts on it (default).
    #   active — the order path rejects an ineligible signal. Behaviour-changing: flip
    #            only on forward shadow evidence + explicit sign-off. Fully reversible.
    regime_gate_mode: Literal["off", "shadow", "active"] = "shadow"

    # ── Paper-trading cost model (app/trading/fees.py) ──────────────────────
    # Realized P&L is charged with the Zerodha cash-equity schedule so the
    # 30-day paper record reflects live-trading net returns. Rates live in
    # fees.py (ZERODHA_EQUITY); these are the behavioural toggles.
    paper_costs_enabled: bool = True
    # Adverse slippage applied to paper fills, in basis points (0 = off).
    # BUY fills move up, SELL fills move down by this fraction of the price.
    # Default 2 bps (~₹0.10 on a ₹500 name each way): a real market order never
    # fills at the exact screen price, so a 0-slippage paper record is optimistic
    # — and that record gates live trading. Conservative-in-the-right-direction;
    # tune per the names/size actually traded. Tests pin this to 0 (conftest
    # `_neutral_paper_slippage`) so fill assertions aren't coupled to the knob;
    # the 2-bps path is exercised explicitly in the dedicated slippage tests.
    paper_slippage_bps: float = 2.0
    # NSE equity tick size (₹) for rounding simulated fills; 0 disables.
    paper_tick_size: float = 0.05

    # ── Spread-aware fill model (Phase 6.8.2, app/broker/paper_broker.py) ───
    # The flat bps above is fine for a Nifty large-cap and a LIE for a small-cap
    # whose spread is 50–100 bps: every paper fill on an illiquid name overstates
    # our edge, and that record gates live trading. When 6.8.1's `depth:{stock_id}`
    # top-of-book is fresh, the fill is priced from the REAL book instead:
    #     adverse_bps = clamp(half-spread + impact, floor=paper_slippage_bps,
    #                         ceiling=paper_slippage_max_bps)
    #     impact      = min(paper_impact_k_bps × qty/top_qty, paper_impact_cap_bps)
    # The flat bps is a FLOOR, so the model can only ever make a fill WORSE —
    # never better than today. No depth (pre-open, thin name, cache miss, capture
    # off) ⇒ the flat path, byte-identical to before: it fails OPEN, never blocking
    # a fill on missing microstructure. Backtests are untouched (they run on candle
    # data and never read depth) — only live paper fills change.
    paper_spread_fill_enabled: bool = True
    # Impact charged when the order size equals the whole visible top-of-book
    # (qty == top_qty). Scales linearly with qty/top_qty; a model, not a
    # book-walking simulator.
    paper_impact_k_bps: float = 5.0
    # Ceiling on the impact TERM alone — a 1-lot-deep book can't produce an
    # unbounded haircut. The half-spread is charged in full on top of it.
    paper_impact_cap_bps: float = 50.0
    # Hard ceiling on TOTAL adverse bps — a feed glitch that survives the
    # crossed-book filter must not price a fill absurdly. 500 bps = 5%.
    paper_slippage_max_bps: float = 500.0

    # ── Circuit-band eligibility overlay (Phase 6.8.3, app/signals/circuit_guard.py) ──
    # A long whose stock is pinned near its LOWER circuit has no buyers — its stop
    # cannot fill at ANY price (software or exchange); a short near the UPPER band is
    # the mirror. This overlay skips entering a name sitting within
    # `circuit_proximity_pct` of its ADVERSE band. Downstream eligibility gate — the
    # frozen confluence engine is untouched (cf. regime_gate_mode). Bands come from
    # Kite quote() (`lower/upper_circuit_limit`), cached to Redis `circuit:{stock_id}`
    # by the refresh_circuit_bands task; the order path only READS the cache.
    #   off    — no gate.
    #   shadow — measure what it WOULD suppress; the order path never acts on it (default).
    #   active — the order path rejects an ineligible signal. Behaviour-changing: flip
    #            only on forward shadow evidence + explicit sign-off. Fully reversible.
    # FAIL-OPEN: a missing/stale band never blocks an otherwise-valid signal.
    circuit_gate_mode: Literal["off", "shadow", "active"] = "shadow"
    # Block when the entry sits within this % of the adverse band. Some bands are
    # 20%-wide and legitimately tradeable, so gate on PROXIMITY, not band existence.
    circuit_proximity_pct: float = 1.5
    # Master switch for the band-refresh task (kite quote() fetch). Off ⇒ the cache
    # is never populated ⇒ the gate fails open everywhere.
    circuit_bands_enabled: bool = True
    # TTL on a cached band (s). Must exceed the refresh cadence so a live band never
    # expires between refreshes; once the refresher stops, bands go stale and the
    # gate fails open (by design). Bands are intraday-static, so this is generous.
    circuit_band_ttl_s: int = 1800

    # ── Profit-lock: absolute-rupee ladder (app/trading/profit_lock.py) ─────
    # When a user opts in (users.profit_lock_enabled), the position monitor
    # governs open PAPER exits with a rupee-denominated profit ladder — the
    # trader's own model: once peak profit ≥ breakeven_inr, lock breakeven (no
    # loss); once ≥ trail_start_inr, seal (peak_profit − giveback_inr), a fixed-₹
    # trailing giveback that tightens as a fraction as the trade runs. The giveback
    # is at least atr_k × ATR in price, so a volatile name in a genuine trend gets
    # room and isn't stopped by normal pullback noise. Coherent across trades
    # because P1 sizes every trade to the same per-trade risk budget (so ₹≈R).
    # These are calibration starting points — tune on the tape toward the daily
    # profit goal; per-user overrides can come later.
    profit_lock_breakeven_inr: float = 2000.0
    profit_lock_trail_start_inr: float = 3000.0
    profit_lock_giveback_inr: float = 1000.0
    profit_lock_atr_k: float = 2.0

    market_open_hour: int = 9
    market_open_minute: int = 15
    market_close_hour: int = 15
    market_close_minute: int = 30

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
