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
