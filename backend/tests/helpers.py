"""
Shared test helpers — user creation, auth, and fixture factories.
Centralised here so test files don't duplicate boilerplate.
"""
from __future__ import annotations

from decimal import Decimal

from app.core.security import hash_password
from app.models.stock import Stock
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    password: str = "Secret123",
    role: str = "user",
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        full_name="Test User",
        role=role,
        is_active=True,
        trading_mode="paper",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_auth_headers(
    client: AsyncClient,
    email: str = "test@example.com",
    password: str = "Secret123",
) -> dict[str, str]:
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def make_stock(
    db: AsyncSession,
    symbol: str = "TESTCO",
    company_name: str = "Test Company Ltd",
    exchange: str = "NSE",
    isin: str | None = None,
    sector: str | None = None,
    industry: str | None = None,
    lot_size: int = 1,
    is_fno: bool = False,
    is_nifty50: bool = False,
    is_banknifty: bool = False,
    is_finnifty: bool = False,
    is_active: bool = True,
) -> Stock:
    stock = Stock(
        symbol=symbol,
        exchange=exchange,
        isin=isin,
        company_name=company_name,
        sector=sector,
        industry=industry,
        lot_size=lot_size,
        tick_size=Decimal("0.05"),
        is_fno=is_fno,
        is_nifty50=is_nifty50,
        is_banknifty=is_banknifty,
        is_finnifty=is_finnifty,
        is_active=is_active,
    )
    db.add(stock)
    await db.commit()
    await db.refresh(stock)
    return stock


async def make_profile(
    db: AsyncSession,
    key: str = "test_profile",
    style: str = "swing",
    timeframe: str = "1d",
    schedule: str = "eod",
    universe_spec: dict | None = None,
    setup_conditions: list | None = None,
    risk_template: dict | None = None,
    status: str = "active",
    min_confidence: int = 70,
):
    """Insert a StrategyProfile version row (config hash computed live)."""
    from app.models.profile import StrategyProfile
    from app.schemas.profile import StrategyProfileConfig, compute_config_hash

    cfg = StrategyProfileConfig(
        key=key,
        name=key.replace("_", " ").title(),
        style=style,
        timeframe=timeframe,
        schedule=schedule,
        universe_spec=universe_spec or {"kind": "all_active"},
        setup_conditions=setup_conditions or [],
        weight_multipliers={},
        min_confidence=min_confidence,
        risk_template=risk_template or {"kind": "rr", "ratio": "2"},
    )
    row = StrategyProfile(
        key=cfg.key,
        version=1,
        name=cfg.name,
        style=cfg.style,
        timeframe=cfg.timeframe,
        schedule=cfg.schedule,
        universe_spec=cfg.universe_spec.model_dump(mode="json"),
        setup_conditions=[c.model_dump(mode="json") for c in cfg.setup_conditions],
        weight_multipliers=cfg.weight_multipliers,
        min_confidence=cfg.min_confidence,
        risk_template=cfg.risk_template.model_dump(mode="json"),
        validity_spec=None,
        status=status,
        config_hash=compute_config_hash(cfg),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def make_daily_candles(
    db: AsyncSession,
    stock_id: int,
    n: int = 60,
    base: float = 100.0,
) -> None:
    """n completed daily candles around `base` with a pivot low (−4%) and a
    pivot high (+4%) so swing SL/TP levels resolve inside the 8% swing cap."""
    from datetime import UTC, datetime, timedelta
    from decimal import Decimal as Dec

    from app.models.market_data import OhlcvDaily

    start = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)
    for i in range(n):
        o = c = base
        # monotone-drifting extremes: tied pivots count as pivots (canon),
        # so drift keeps every low/high unique and ONLY the designed
        # dip/spike become swing levels
        h = base + 0.5 - 0.005 * i
        lo = base - 0.5 + 0.005 * i
        if i == n - 30:  # the one swing high, +4%
            h = base * 1.04
        if i == n - 20:  # the one swing low, −4%
            lo = base * 0.96
        db.add(
            OhlcvDaily(
                time=start + timedelta(days=i),
                stock_id=stock_id,
                open=Dec(str(o)),
                high=Dec(str(round(h, 4))),
                low=Dec(str(round(lo, 4))),
                close=Dec(str(c)),
                volume=100_000,
                is_complete=True,
            )
        )
    await db.commit()
