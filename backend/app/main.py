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
    # Try to resume the tick consumer if an admin already authenticated today
    try:
        from sqlalchemy import text

        from app.broker.tick_consumer import start_consumer
        from app.db.session import AsyncSessionFactory

        async with AsyncSessionFactory() as db:
            result = await db.execute(
                text(
                    "SELECT u.id FROM users u"
                    " JOIN broker_tokens bt ON bt.user_id = u.id"
                    " WHERE bt.is_active = true AND bt.expires_at > now()"
                    " AND u.role = 'admin' ORDER BY bt.created_at DESC LIMIT 1"
                )
            )
            row = result.fetchone()
            if row:
                await start_consumer(user_id=row[0])
    except Exception as exc:
        log.debug("Tick consumer auto-start skipped: %s", exc)

    yield

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
