from functools import lru_cache
from pathlib import Path

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

    # ── Paper-trading cost model (app/trading/fees.py) ──────────────────────
    # Realized P&L is charged with the Zerodha cash-equity schedule so the
    # 30-day paper record reflects live-trading net returns. Rates live in
    # fees.py (ZERODHA_EQUITY); these are the behavioural toggles.
    paper_costs_enabled: bool = True
    # Adverse slippage applied to paper fills, in basis points (0 = off).
    # BUY fills move up, SELL fills move down by this fraction of the price.
    paper_slippage_bps: float = 0.0
    # NSE equity tick size (₹) for rounding simulated fills; 0 disables.
    paper_tick_size: float = 0.05
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
