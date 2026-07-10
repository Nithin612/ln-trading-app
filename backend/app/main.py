import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    # The v1 tick consumer must NEVER auto-start. It used to resume here
    # whenever a valid token existed, which armed it on every uvicorn
    # (re)start — on 2026-07-10 that wrote off-canon candles twice while
    # the Phase-3 live worker owned the tables (see phase-03 ledger,
    # §post-close forensics). The live worker (`python -m
    # app.broker.live_worker`) is the candle owner; the v1 consumer runs
    # only via the explicit admin endpoint POST /broker/kite/consumer/start
    # — a deliberate act by whoever guarantees the worker is not running.
    yield

    # Clean up a manually-started consumer on shutdown.
    from app.broker.tick_consumer import stop_consumer
    await stop_consumer()
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Trading Platform API",
        version="0.1.0",
        description="Intelligent stock-suggestion and algo-trading platform for Indian markets",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    # Serve uploaded screenshots as static files
    uploads_path = Path(settings.uploads_dir)
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
