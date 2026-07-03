"""Daily-loss circuit breaker — Phase 8.

Computes whether the user has breached their daily loss limit by summing
realized P&L on positions closed today (IST).  When triggered, new paper
orders are rejected.  This breaker is NEVER disabled in live mode.
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import Position
from app.models.user import User


def _ist_date_window() -> tuple[datetime, datetime]:
    """Return (start_of_day_utc, now_utc) for the current IST calendar day."""
    from zoneinfo import ZoneInfo

    ist = ZoneInfo("Asia/Kolkata")
    now_utc = datetime.now(tz=UTC)
    now_ist = now_utc.astimezone(ist)
    day_start_ist = now_ist.replace(hour=0, minute=0, second=0, microsecond=0)
    day_start_utc = day_start_ist.astimezone(UTC)
    return day_start_utc, now_utc


async def get_daily_realized_pnl(db: AsyncSession, user_id: int) -> Decimal:
    """Sum realized P&L for all positions closed today (IST)."""
    start, end = _ist_date_window()
    result = await db.execute(
        select(func.coalesce(func.sum(Position.realized_pnl), 0)).where(
            Position.user_id == user_id,
            Position.closed_at >= start,
            Position.closed_at <= end,
            Position.closed_at.is_not(None),
        )
    )
    return Decimal(str(result.scalar()))


async def get_trades_taken_today(db: AsyncSession, user_id: int) -> int:
    """Count positions opened today (IST) — enforces max_trades_per_day."""
    start, end = _ist_date_window()
    result = await db.execute(
        select(func.count(Position.id)).where(
            Position.user_id == user_id,
            Position.opened_at >= start,
            Position.opened_at <= end,
        )
    )
    return int(result.scalar() or 0)


async def check_circuit_breaker(db: AsyncSession, user: User) -> tuple[bool, str]:
    """Return (triggered, reason).

    triggered=True means the user must NOT place new orders.
    """
    daily_pnl = await get_daily_realized_pnl(db, user.id)
    limit_inr = -(user.capital_inr * user.daily_loss_limit_pct / Decimal("100"))

    if daily_pnl <= limit_inr:
        return True, (
            f"Daily loss limit reached: ₹{abs(daily_pnl):.2f} lost "
            f"(limit ₹{abs(limit_inr):.2f})"
        )

    trades_today = await get_trades_taken_today(db, user.id)
    if trades_today >= user.max_trades_per_day:
        return True, (
            f"Max trades per day reached: {trades_today}/{user.max_trades_per_day}"
        )

    return False, ""
