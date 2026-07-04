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
