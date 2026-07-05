from fastapi import APIRouter

from app.api.v1 import (
    auth,
    broker,
    calendar,
    categories,
    filings,
    journal,
    market_data,
    portfolio,
    screener,
    signals,
    stocks,
    strategy,
    trading,
    users,
    ws,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(stocks.router)
api_router.include_router(screener.router)
api_router.include_router(categories.router)
api_router.include_router(market_data.router)
api_router.include_router(calendar.router)
api_router.include_router(signals.router)
api_router.include_router(filings.router)
api_router.include_router(broker.router)
api_router.include_router(trading.router)
api_router.include_router(strategy.router)
api_router.include_router(journal.router)
api_router.include_router(portfolio.router)
api_router.include_router(ws.router)
