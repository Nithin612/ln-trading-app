"""Paper broker — Phase 8.

Simulates order placement and fills entirely in software:
  - place_paper_order  : create Order + open (or add to) Position
  - close_position     : create a SELL Order, close Position, record P&L
  - get_current_price  : Redis LTP → latest daily close fallback
  - update_position_pnl: refresh unrealized_pnl on an open position
"""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.signal import Signal
from app.models.trading import Order, Position
from app.models.user import User
from app.trading.trail_sl import compute_pnl


async def get_current_price(db: AsyncSession, stock_id: int) -> Decimal | None:
    """Best-effort current price: Redis LTP first, then latest daily close."""
    try:
        import redis.asyncio as aioredis

        from app.core.config import settings

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        ltp_str: str | None = await r.get(f"ltp:{stock_id}")
        await r.aclose()
        if ltp_str:
            return Decimal(ltp_str)
    except Exception:
        pass

    # Fall back to last daily close in DB
    from app.models.market_data import OhlcvDaily

    result = await db.execute(
        select(OhlcvDaily.close)
        .where(OhlcvDaily.stock_id == stock_id, OhlcvDaily.is_complete.is_(True))
        .order_by(OhlcvDaily.time.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return Decimal(str(row)) if row is not None else None


async def place_paper_order(
    db: AsyncSession,
    user: User,
    signal: Signal,
    side: str = "BUY",
    quantity: int | None = None,
) -> tuple[Order, Position]:
    """Place a paper MARKET order and immediately simulate a fill.

    Fill price = current LTP from Redis, or signal's entry_price if unavailable.
    Opens a new Position (or returns existing open position for the stock).

    Returns (order, position) — both are already flushed into the session.
    """
    qty = quantity if quantity is not None else signal.suggested_qty
    fill_price = await get_current_price(db, signal.stock_id) or Decimal(str(signal.entry_price))
    now = datetime.now(tz=UTC)

    order = Order(
        user_id=user.id,
        signal_id=signal.id,
        stock_id=signal.stock_id,
        mode="paper",
        side=side,
        order_type="MARKET",
        quantity=qty,
        status="filled",
        placed_at=now,
        filled_at=now,
        filled_price=fill_price,
        filled_qty=qty,
    )
    db.add(order)

    # Determine position side from order side
    pos_side = "LONG" if side == "BUY" else "SHORT"

    # Check for an existing open position for this stock/user (paper)
    existing_result = await db.execute(
        select(Position).where(
            Position.user_id == user.id,
            Position.stock_id == signal.stock_id,
            Position.mode == "paper",
            Position.closed_at.is_(None),
            Position.side == pos_side,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Average in — weighted average entry price
        total_qty = existing.quantity + qty
        new_avg = (existing.avg_entry_price * existing.quantity + fill_price * qty) / total_qty
        existing.avg_entry_price = new_avg.quantize(Decimal("0.0001"))
        existing.quantity = total_qty
        # Keep original SL/TP from the first entry
        position = existing
    else:
        position = Position(
            user_id=user.id,
            stock_id=signal.stock_id,
            mode="paper",
            side=pos_side,
            quantity=qty,
            avg_entry_price=fill_price,
            current_sl=signal.stop_loss,
            current_tp=signal.take_profit,
            trail_state="none",
            unrealized_pnl=Decimal("0"),
            realized_pnl=Decimal("0"),
            opened_at=now,
            signal_id=signal.id,
        )
        db.add(position)

    await db.flush()
    return order, position


async def close_position(
    db: AsyncSession,
    position: Position,
    exit_price: Decimal | None = None,
    reason: str = "manual",
) -> tuple[Order, Position]:
    """Close an open paper position at exit_price (or current LTP).

    Creates a closing Order, marks Position as closed, sets realized_pnl.
    Returns (close_order, updated_position).
    """
    if position.closed_at is not None:
        raise ValueError(f"Position {position.id} is already closed")

    price = exit_price or await get_current_price(db, position.stock_id)
    if price is None:
        price = position.avg_entry_price  # fallback: flat trade

    now = datetime.now(tz=UTC)
    close_side = "SELL" if position.side == "LONG" else "BUY"

    order = Order(
        user_id=position.user_id,
        signal_id=position.signal_id,
        stock_id=position.stock_id,
        mode="paper",
        side=close_side,
        order_type="MARKET",
        quantity=position.quantity,
        status="filled",
        placed_at=now,
        filled_at=now,
        filled_price=price,
        filled_qty=position.quantity,
        broker_payload={"reason": reason},
    )
    db.add(order)

    pnl = compute_pnl(
        side=position.side,
        entry=Decimal(str(position.avg_entry_price)),
        exit_price=price,
        quantity=position.quantity,
    )
    position.realized_pnl = pnl
    position.unrealized_pnl = Decimal("0")
    position.closed_at = now

    await db.flush()
    return order, position


async def update_position_pnl(
    db: AsyncSession,
    position: Position,
) -> None:
    """Refresh unrealized_pnl on an open position using the current price."""
    if position.closed_at is not None:
        return
    price = await get_current_price(db, position.stock_id)
    if price is None:
        return
    pnl = compute_pnl(
        side=position.side,
        entry=Decimal(str(position.avg_entry_price)),
        exit_price=price,
        quantity=position.quantity,
    )
    position.unrealized_pnl = pnl
