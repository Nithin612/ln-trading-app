from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
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

    # U1 — live_worker refuses to start when its subscription universe falls
    # below this fraction of the previous session's. Mirrors kite_client's
    # _SWEEP_MIN_FRACTION: a real market never halves its tradable universe
    # overnight, so a collapse is a data defect. 0 disables the collapse arm;
    # the EMPTY arm is not disableable.
    live_universe_min_fraction: float = 0.5
    # Absolute floor, in instruments. The ratio arm cannot see a collapse that
    # arrives in sub-threshold steps, and has nothing to compare against on a
    # first run; this arm can. 0 disables it.
    live_universe_min_count: int = 500
    # U16 — Kite carries at most this many instruments on one WebSocket connection
    # and live_worker subscribes in a single unchunked call. Exceeding it drops the
    # excess server-side silently, so the worker refuses instead. 0 disables.
    live_universe_max_count: int = 3000
    # D2′b — `apply_to_stocks` refuses to adopt a snapshot smaller than this fraction
    # of the currently-active set. The rule's input is a CSV fetched over the internet
    # and the job runs unattended; a truncated feed must not switch off the market.
    # Growth is never refused. 0 disables.
    universe_apply_min_fraction: float = 0.5
    # U4′ — the coverage-aware feed alarm fires when a feed still CURRENT carries
    # fewer names than usual: today's breadth below this fraction of the median over
    # the trailing COVERAGE_BASELINE_SESSIONS.
    # ⚠ Measured, not chosen — and the margin depends on WHICH window you measure, so
    # all three are recorded rather than the flattering one: the worst BENIGN shortfall
    # vs the trailing median is 2.21% over the last 239 sessions, 3.21% over the 791
    # post-gap sessions (2024-09-05), and 8.17% over all 1,098 (2020-07-03, 1,383 vs
    # 1,506 — the pre-gap ingestion era). So 0.90 sits ~4.5x above the RECENT noise
    # floor but only ~1.2x above the archive's worst, against a ~50% collapse. Replaying
    # the shipped detector over all 1,098 sessions fires 0 times. 0 disables.
    feed_coverage_min_fraction: float = 0.90
    # Session notifier (A11). Unset ⇒ log-only, which is the DEFAULT and not a degraded
    # mode: the policy still runs and still logs at the level it chose. Set it and the same
    # messages also POST as JSON. Vendor-neutral on purpose — Slack/Discord accept the
    # shape directly, Telegram/ntfy want a small relay.
    notifier_webhook_url: str | None = None
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
    # Market-level alerts (vburst / PDH / PDL / S&R — stamped style="market")
    # are BREADTH breadcrumbs, not near-trigger: measured 2026-08-18 they
    # carried 1271 distinct stocks inside one 15-min window and flooded the
    # 150 hot-set cap, so the cap was spent on the lowest stock_ids and
    # watchlist stocks were never scored at all. 0 = signal-bound triggers
    # only; >0 admits that many market-level stocks newest-first, deduped
    # against everything already hot and ranked BELOW the watchlist so the
    # dial can never starve it. NOTE at 0 the third hot-set source adds
    # ~nothing new (measured 2026-08-19: 38 of 45 signal-bound alert stocks
    # already carried an active signal), so ~1569 breadth-movers are
    # unscoreable and ~37 of 150 slots sit idle — a discovery/cost
    # trade-off, not an oversight (quant-verifier MEDIUM 2026-08-19).
    live_provisional_trigger_market_max: int = 0
    live_provisional_top_n: int = 20         # rows per style leaderboard
    live_provisional_key_ttl_s: int = 60     # leaderboard SET key TTL
    # Cycle-health key TTL. One key PER SESSION DAY, kept a week: the
    # thread's log is otherwise the only record of cadence/clip health, and
    # `make live-worker` writes no log file at all (only `make soak` tees
    # one), so a day's evidence used to vanish with the terminal. A week
    # spans "monitor it for a few days" without any scheduler running.
    live_provisional_health_ttl_s: int = 604_800

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

    # ── Entry-quality overlay (Phase 6.8 R-track, app/signals/entry_quality.py) ──
    # Attacks the entry-side leak the SRTL loss exposed (see
    # docs/analysis/exit-ladder-research-2026-08-18.md): (1) the confidence math
    # normalizes by SCORING-factor weight, so a single factor at 0.8 reads 80% —
    # "80% but one indicator", not real confluence; (2) a stop far tighter than the
    # stock's volatility guarantees a fast stop-out AND amplifies slippage on the
    # huge qty risk-first sizing then buys. Downstream eligibility overlay (frozen
    # engine untouched, the regime_gate pattern), FAIL-OPEN.
    # Two INDEPENDENTLY-moded checks (off / shadow / active):
    #  • diversity — enforces "≥2 factors, never a single indicator" (a STATED hard
    #    rule the strength-only ≥70% gate fails to enforce). ACTIVE by user sign-off
    #    2026-08-18 (the SRTL loss): a single-factor signal must not enter. Reversible.
    #  • sl_atr — the stop-too-tight-for-volatility heuristic; a TUNABLE threshold, so
    #    it stays SHADOW (measure-only) until forward evidence (the entry-quality
    #    shadow report) justifies a flip.
    entry_diversity_gate_mode: Literal["off", "shadow", "active"] = "active"
    entry_sl_atr_gate_mode: Literal["off", "shadow", "active"] = "shadow"
    # Reject a signal with fewer than this many SCORING factors (score != 0).
    entry_min_scoring_factors: int = 2
    # …or where one factor is more than this share of the weighted confluence.
    entry_max_dominant_factor_share: float = 0.90
    # Flag a stop tighter than this multiple of ATR (too fragile for the stock's
    # noise → fast stop-out + slippage amplification). 0 disables the ATR check.
    entry_min_sl_atr_mult: float = 1.0

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
    # Flat tick-size OVERRIDE (₹) for rounding simulated fills.
    # ⭐ **0 (the default) means "use `app.broker.tick_schedule`"** — the DATED PRICE-BAND
    # schedule, which is the real grid: NSE moved sub-₹250 names to ₹0.01 during June 2024
    # while ≥₹250 stayed at ₹0.05. A single constant charged a ₹39 name ~10 bps of
    # round-trip rounding the market does not (≈0.051R at a 2% stop, ~40% of the real
    # 25.5 bps charge stack).
    # A POSITIVE value forces that flat grid everywhere, ignoring the schedule — kept for
    # tests and for pinning a historical model, not for production use.
    # ⚠ Negative disables rounding entirely. That is not a mode anything ships with: an
    # off-grid price is not transactable, so skipping the snap hands out fills better than
    # reality, which is the exact failure `_round_tick` exists to prevent.
    paper_tick_size: float = 0.0

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
    # CAS (Closing Auction Session) capture (Stage 1). Master switch for the market-hours task that
    # records the auction close + imbalance for the F&O universe into `cas_daily` (research only —
    # never gates/sizes/trades). Self-skips without a Kite admin token; off ⇒ no capture.
    cas_capture_enabled: bool = True
    # TTL on a cached band (s). Must exceed the refresh cadence so a live band never
    # expires between refreshes; once the refresher stops, bands go stale and the
    # gate fails open (by design). Bands are intraday-static, so this is generous.
    circuit_band_ttl_s: int = 1800

    # ── Sector/index relative-strength overlay (MCE slice 2, app/signals/sector_rs.py) ──
    # The top-down context the confluence engine lacks: a long is out of context when
    # the stock is UNDER-performing its benchmark index over `sector_rs_lookback`
    # sessions (a short is the mirror). Benchmark = the most specific membership index
    # (Bank-Nifty ⊃ Fin-Nifty ⊃ NIFTY 50), closes from index_ohlcv_1d via
    # app/services/benchmark.py; the order path only READS them. Frozen engine untouched
    # (a downstream overlay, cf. regime_gate_mode). Reuses eval_relative_strength's
    # definition (excess = stock_ret − bench_ret).
    #   off    — TRUE no-op: no query, no stamp.
    #   shadow — measure + stamp the verdict; the order path never acts on it (default —
    #            slice 3 flipped it here to start accruing forward evidence; the sector-RS
    #            shadow sidecar recomputes the verdict per signal regardless, so evidence
    #            accrues once index_ohlcv_1d has backfilled).
    #   active — reject an ineligible signal. Behaviour-changing → forward shadow evidence
    #            + §8-on-≥2y + explicit sign-off first. Fully reversible.
    # FAIL-OPEN: no benchmark data / too-short history / any DB fault never blocks a signal.
    sector_rs_gate_mode: Literal["off", "shadow", "active"] = "shadow"
    # Lookback in trading sessions for the excess-return comparison (matches
    # eval_relative_strength's default).
    sector_rs_lookback: int = 20
    # A long passes when excess ≥ this %, a short when excess ≤ −this %. 0.0 = block a
    # long only on strict under-performance (a short only on strict out-performance).
    sector_rs_min_excess_pct: float = 0.0

    # ── Market-regime overlay (MCE slice 4, app/signals/market_regime.py) ──────────────
    # The broadest top-down filter (above sector-RS): is the MARKET itself risk-on/off? A
    # LONG into a broad market below its N-DMA — or a SHORT into one above — is fighting the
    # tape. Trend from the broad-market index (`market_regime_market_symbol`) in
    # index_ohlcv_1d; VIX from india_vix_daily is an INFORMATIONAL companion (reported,
    # never blocks — VIX history is too shallow to §8-validate). Frozen engine untouched (a
    # downstream overlay). FAIL-OPEN: history shorter than the DMA period never blocks.
    #   off    — TRUE no-op.
    #   shadow — measure + stamp, never act (default; the 200-DMA needs a deep index
    #            backfill before it has data — until then it fails open everywhere).
    #   active — reject an ineligible signal. Behaviour-changing → forward evidence +
    #            §8-on-≥2y + explicit sign-off first. Fully reversible.
    market_regime_gate_mode: Literal["off", "shadow", "active"] = "shadow"
    market_regime_market_symbol: str = "NIFTY50"
    market_regime_dma_period: int = 200
    # Buffer band around the DMA (a long isn't flagged for sitting a hair below it). % of
    # the DMA; 0.0 = flag on any cross.
    market_regime_dma_buffer_pct: float = 0.0
    # India-VIX "elevated" threshold — INFORMATIONAL only (stamped/reported, never blocks).
    market_regime_vix_threshold: float = 20.0

    # ── Liquidity overlay (MCE slice 5a, app/signals/liquidity_guard.py) ───────────────
    # The junk filter's core: block an entry into a name too illiquid to exit (the SRTL
    # archetype — a ₹39 micro-cap with no buyers for the stop). Metric = the MEDIAN daily
    # traded value (₹ = close × volume) over `liquidity_lookback` sessions from ohlcv_1d,
    # side-INDEPENDENT (illiquidity traps a long and a short alike). Frozen engine untouched
    # (a downstream overlay). FAIL-OPEN: history thinner than the lookback never blocks.
    #   off    — TRUE no-op.
    #   shadow — measure + stamp, never act (default).
    #   active — reject an ineligible signal. Behaviour-changing → forward evidence +
    #            §8-on-≥2y + explicit sign-off first. Fully reversible.
    liquidity_gate_mode: Literal["off", "shadow", "active"] = "shadow"
    liquidity_lookback: int = 20
    # Median-daily-traded-value floor in ₹ (default ₹1 crore/day). Tune from the shadow
    # evidence before flipping active.
    liquidity_min_traded_value_inr: float = 10_000_000.0

    # ── Anti-chase eligibility overlay (app/signals/chase_guard.py) ─────────
    # Blocks an order when the LIVE price has run more than `chase_max_r` × the trade's risk
    # (|entry − SL| = 1R) PAST the signal's entry — the server-side backstop to the AlertBell
    # guardrail. Reads the Redis LTP at order time; fail-open when no live price (off-market)
    # or a zero-risk signal. Frozen engine untouched (a downstream overlay).
    #   off    — TRUE no-op (no LTP read, no stamp).
    #   shadow — measure + stamp, never act (default).
    #   active — reject a chasing order. Behaviour-changing → forward evidence + sign-off first.
    #            Fully reversible.
    chase_gate_mode: Literal["off", "shadow", "active"] = "shadow"
    # Ceiling in R past entry. 0.33 from the chase_r-vs-outcome measurement (2026-08-21): trades
    # with chase_r ≤ 0.33 were net-positive; the only two past it were both losers.
    chase_max_r: float = 0.33

    # ── Reward:risk floor overlay (app/signals/rr_guard.py) ─────────────────
    # Rejects a signal whose planned TARGET is closer than its STOP.
    #
    # ⛔ SHIPPED ACTIVE 2026-09-02, REVERTED TO SHADOW 2026-09-03 — and the default here
    # was moved with it (verified 2026-09-04). The original argument was that this gate
    # enforces an IDENTITY, not a hypothesis, and therefore needed no forward-evidence
    # bar: at planned R:R < 1 a trade needs a >50% win rate merely to break even, "which
    # no trend-following system sustains". The arithmetic was right; the clause after the
    # comma was an ASSERTION, never checked, and the tape falsified it in one week. The
    # blocked cohort was the only profitable one in the book — 24 trades, +₹10,585, 63%
    # win, 33% tp_hit — because (a) a nearer target is mechanically easier to hit, and
    # (b) R:R < 1 is a PROXY FOR A WIDE STOP (7.29% avg, zero tight) and wide stops are
    # independently the good cohort. The gate blocked wide stops. Backwards.
    #
    # Standing lesson (CLAUDE.md constraint 8): an identity about arithmetic still rests
    # on an empirical premise — test the premise against the tape before flipping.
    # Re-promotion needs the deflated-Sharpe / multiple-testing bar plus a tail check,
    # not a repeat of the identity argument. Moving the floor ABOVE 1.0 is doubly
    # empirical: 1.67 is fitted to our observed 37.5% win rate.
    #
    # Why the defect it targets exists: `analysis/risk.py::compute_levels` pairs a
    # STRUCTURAL stop (swing pivot / EMA20) with an ABSOLUTE-% target (swing +6%,
    # positional +15%), so the ratio is an accident of where the pivot sat — 94 of 295
    # swing signals landed under 1.0 (2026-09-02 audit). Intraday/scalp are ratio-based
    # (1:2, 1:1.5) and are fine. Making swing/positional ratio-based is a §6 spec change
    # with an §8 regression, and remains the real fix.
    #   off    — TRUE no-op.
    #   shadow — measure only (default, after the revert).
    #   active — reject.
    rr_gate_mode: Literal["off", "shadow", "active"] = "shadow"
    # The floor itself. Keep at 1.0 unless you have run the multiple-testing bar.
    rr_min: float = 1.0

    # ── Volume-participation impact (A37, app/broker/paper_broker.py) ───────
    # Our 6.8.2 model charges the real half-spread plus a size-vs-TOP-OF-BOOK impact.
    # Neither notices that an order is large relative to the stock's DAILY VOLUME: the
    # notional cap bounds a position in rupees, not in liquidity. SRTL is the named case
    # — a ₹39 micro-cap, 2,666 shares; a ₹1 lakh position in a name trading ₹5 lakh a day
    # is 20% of a session and is not fillable at the quoted price, yet we modelled it free.
    #
    # Charge `k × participation²` bps, participation = order value ÷ median daily traded
    # value. Quadratic, following zipline's `VolumeShareSlippage`
    # (`price × (1 + price_impact × volume_share²)`, `price_impact` 0.1). At k=0.1: 2.5%
    # participation ≈ 0.6 bps, 10% ≈ 10 bps, 20% ≈ 40 bps, 50% ≈ 250 bps. Small orders are
    # untouched; the cost bites exactly where the order stops being absorbable.
    #
    # ⚠⚠ **THE FORM IS ZIPLINE'S; THE CALIBRATION ABOVE 2.5% IS OURS.** Zipline pairs
    # `price_impact=0.1` with `volume_limit=0.025` — it NEVER fills more than 2.5% of a
    # bar, so 0.1 was only ever evaluated up to ≈0.6 bps. We apply the same quadratic at
    # 20% (40 bps) and 50% (250 bps), saturating the 500 bps ceiling at 70.7%
    # participation. That extrapolation is a JUDGEMENT CALL with no external validation
    # (quant-verifier; the T12 rule — "our trading layer has fitted constants nobody can
    # re-derive, mark judgement calls as such").
    #
    # What would falsify it: real fills on names where we take >5% of a session. We have
    # none — the paper book has never traded live — so this stands until Phase 7 supplies
    # execution data, and any recalibration should come from that, not from a backtest
    # fitted to the same trades the number is meant to price.
    #
    # ⚠ It OVERLAPS the top-of-book term rather than being orthogonal to it: one measures
    # instantaneous depth, the other daily capacity, and an illiquid name trips both. That
    # is intended — both being large IS the signal the trade is unfillable — and the sum
    # is bounded by `paper_slippage_max_bps`.
    #
    # ⚠ NOT a partial-fill cap. Zipline also refuses to fill more than 2.5% of a bar and
    # spills the rest; that needs partial fills, which are Phase 7. This prices the trade
    # honestly rather than rejecting it — no signal is suppressed by this knob.
    paper_participation_enabled: bool = True
    #: Clamped ≥ 0 at the edge: a negative k would drive `slippage_bps` NEGATIVE on the
    #: spread path — a fill BETTER than the reference, which the module contract forbids.
    #: Nothing validated it before, and the guard that looked like it did was dead code
    #: for every k ≥ 0 (quant-verifier).
    paper_participation_k: float = Field(default=0.1, ge=0.0)
    #: Sessions of history required before participation is charged at all. Fewer than this
    #: is "unknown", and unknown fails OPEN (no impact) — never "infinitely illiquid".
    paper_participation_lookback: int = 20

    # ── Paper account constraints (app/broker/paper_broker.py) ──────────────
    # Per-position NOTIONAL cap as a multiple of capital. `qty = risk_budget /
    # risk_per_share` has no ceiling on `qty × price`, so a stop a few paise wide sized a
    # ₹1,18,65,000 position on ₹1,00,000 of capital (2026-09-02) — 119× the account, which
    # then polluted the paper book, the R statistics and the 30-day go-live clock.
    # 1.0 = cash-delivery reality on NSE: you cannot buy more stock than you have money.
    # Raise it ONLY to model an intraday product that genuinely grants leverage.
    # NOTE: this is PER POSITION. Portfolio-wide exposure is the portfolio-heat cap's job
    # (not built — the book ran at 45.3% risk across 23 positions on 2026-09-02).
    paper_max_notional_leverage: float = 1.0

    # ── Paper SAMPLING scale (reporting only — never affects sizing) ───────
    # `capital_inr` is the LIVE account figure and drives per-trade sizing
    # (risk_pct × capital). But the paper book is deliberately run as a WIDE EVIDENCE
    # SAMPLER — 5 entries/day, ~5-day holds, so ~25 concurrent positions — which means
    # exposure measured against the live figure reads alarmingly (45.3% "heat" on
    # 2026-09-02) while the very same book is a textbook-conservative 9% against the
    # scale the sampler actually represents. Same positions, different denominator.
    #
    # This is the declared notional account size the sampler stands for, used ONLY as a
    # reporting denominator. It NEVER touches `compute_quantity`/`size_for_fill`, so no
    # trade changes size and history stays comparable. 0 = unset ⇒ fall back to
    # `capital_inr` (previous behaviour exactly).
    #
    # The daily report prints exposure against BOTH figures, labelled — replacing one
    # misleading number with a different one would be no improvement.
    paper_sampling_capital_inr: float = 0.0

    # Portfolio-heat cap used by the COUNTERFACTUAL only (no enforcement anywhere).
    # Elder's 6% rule / Tharp's 6–10% band. The counterfactual answers the question the
    # 30-day go-live clock should be reading: "what would a disciplined ₹1L book, capped
    # here, have returned from the same signals?" — because the wide sampler's P&L is not
    # the book that will ever be traded live (1–2 positions on ₹1 lakh).
    heat_counterfactual_pct: float = 6.0

    # ── Portfolio HEAT CAP (Phase 7.1, app/trading/risk_engine.py) ─────────
    # The enforcing sibling of `heat_counterfactual_pct`. Admission risk summed across
    # OPEN positions: heat = qty × max(0, entry − commit_SL), initial risk (never
    # mark-to-market — a from-the-mark definition LOOSENS as the book deteriorates,
    # which is perverse for a risk cap), from the COMMIT stop (never the trailed
    # `current_sl`, which leaks price action the admission decision could not see).
    #
    # ⚠ DEFAULT IS `off`, and that is deliberate rather than timid: a 6% cap cuts
    # cycle-1 entries by ~74% and cycle 1 exists to accrue evidence VOLUME. The
    # counterfactual already answers what a cap would answer, with no behaviour change
    # (admitted 12 / skipped 35; capped −₹13,303 vs full −₹19,093 in TOTAL, but per-trade
    # WORSE at −₹1,478 vs −₹796 ⇒ a heat cap is a RISK control, NOT a profitability fix).
    # It flips to `active` at the CYCLE-2 RESET, not before.
    #
    # ⚠ Unlike the six selection overlays this rail FAILS CLOSED: an open position whose
    # risk cannot be measured refuses the next entry rather than counting as zero. For a
    # selection gate the error to avoid is suppressing a good trade on uncertainty; for a
    # risk rail it is taking risk you cannot count. Same logic as the daily-loss breaker.
    #
    # ⚠ The denominator is `capital_inr` (the LIVE figure), NEVER
    # `paper_sampling_capital_inr` — that one is reporting-only and 5× larger, so
    # misapplying it would silently quintuple the cap.
    heat_cap_mode: Literal["off", "shadow", "active"] = "off"
    heat_cap_pct: float = 6.0

    # ── Portfolio position-count cap (D4, 2026-09-08) ──────────────────────────
    # Max CONCURRENT open positions. At cycle-2 scale (₹1L, the live 1–2 book) a heat
    # PERCENTAGE barely binds — 2 positions at 2% risk ≈ 4% heat, under the 6% cap — so a
    # COUNT is the concentration rail that actually bites and directly enforces the design
    # intent. A HARD design rail (like entry_diversity), NOT a measured-edge gate: no
    # deflated-Sharpe bar. Adding to an EXISTING position opens no new slot and is exempt.
    # `off` during the cycle-1 sampler (which runs ~25 concurrent BY DESIGN); flips to
    # `active` at the CYCLE-2 RESET alongside the heat cap. 0 or negative = disabled.
    position_count_cap_mode: Literal["off", "shadow", "active"] = "off"
    max_concurrent_positions: int = 3

    # ── Aggregate cash constraint (B2, round 10 — 2026-09-11) ──────────────────
    # ⛔ Before this the constraint DID NOT EXIST ANYWHERE: not in `paper_broker`, not in
    # the RiskEngine, not in the backtest. The per-position notional cap bounds ONE trade
    # against capital; nothing bounded the SUM. Three slots at the median 5% swing stop
    # need ~120% of capital, and every one of them returned 201.
    #
    # It enforces an IDENTITY — a delivery account cannot deploy money it does not have —
    # so under §5.4's asymmetric burden it carries NO forward-evidence bar, unlike the six
    # selection overlays. It is a rail, not a gate.
    #
    # ⚠ The denominator is `capital_inr`, the LIVE figure, for the same reason the heat cap
    # uses it: `paper_sampling_capital_inr` is declared reporting-only and is 5× larger, so
    # misapplying it would silently quintuple the rail.
    #
    # `off` during the cycle-1 sampler (which runs ~25 concurrent positions BY DESIGN and
    # would be throttled to a stop); flips `active` at the CYCLE-2 RESET alongside the heat
    # cap and the position-count cap. `cash_cap_leverage` is the multiple of capital the
    # book may deploy — 1.0 = strictly cash-and-carry, no leverage.
    cash_cap_mode: Literal["off", "shadow", "active"] = "off"
    cash_cap_leverage: float = 1.0

    # ── KILL SWITCH (Phase 7.4) ────────────────────────────────────────────
    # The human's stop. `true` halts all NEW ENTRIES immediately, at the first rule the
    # RiskEngine runs — ahead of even the daily-loss breaker, because someone who has hit
    # stop should not have to reason about which other rule might still let an order
    # through.
    #
    # ⚠ IT DOES NOT BLOCK EXITS, deliberately. A switch that traps you in open positions
    # is a hazard dressed as a safety feature: the moment you most want to halt new risk
    # is often the moment you most need to close what you are already holding. Exits run
    # through `close_position`, which does not consult the RiskEngine's entry path.
    #
    # ⚠ It is a plain bool with no "shadow" mode. A kill switch you can set to
    # measure-only is not a kill switch, and the three-valued gate vocabulary would invite
    # exactly that.
    trading_kill_switch: bool = False

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
    # The EARLY-BREAKEVEN candidate replayed beside the live ladder by
    # `profit_lock_shadow` — an honest one-variable A/B for the rung the 2026-08-18
    # exit-ladder research supported moving ("₹800 instead of ₹2,000… it cut blow-ups
    # 3 vs 5 at little cost"). Nothing acts on it: it only names the counterfactual.
    # Note ₹2,000 = exactly +1R at the ₹1L/2% budget, which is WHY the live rung almost
    # never armed — every daily report shows "never reached +1R, lock stayed unarmed".
    profit_lock_breakeven_early_inr: float = 800.0

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
