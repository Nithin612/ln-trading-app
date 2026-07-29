"""Paper broker — Phase 8.

Simulates order placement and fills entirely in software:
  - place_paper_order  : create Order + open (or add to) Position
  - close_position     : create a SELL Order, close Position, record P&L
  - get_current_price  : Redis LTP → latest daily close fallback
  - update_position_pnl: refresh unrealized_pnl on an open position
"""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analysis.risk import compute_quantity
from app.core.config import settings
from app.models.signal import Signal
from app.models.trading import Order, Position
from app.models.user import User
from app.trading.fees import product_for_classification, roundtrip_charges
from app.trading.trail_sl import compute_pnl


class PaperOrderError(Exception):
    """Raised when a paper order cannot be placed (e.g. size rounds to zero
    at the account's capital/risk). The API maps this to HTTP 422."""


def _apply_slippage(price: Decimal, order_side: str) -> Decimal:
    """Adverse slippage on a simulated fill (config `paper_slippage_bps`).

    A BUY fills higher, a SELL lower — the trader always pays the spread.
    Zero bps (the default) is a no-op.
    """
    bps = Decimal(str(settings.paper_slippage_bps))
    if bps <= 0:
        return price
    factor = bps / Decimal("10000")
    if order_side.upper() == "BUY":
        return price * (Decimal("1") + factor)
    return price * (Decimal("1") - factor)


def _round_tick(price: Decimal) -> Decimal:
    """Round a fill to the exchange tick grid (config `paper_tick_size`)."""
    tick = Decimal(str(settings.paper_tick_size))
    if tick <= 0:
        return price.quantize(Decimal("0.0001"))
    steps = (price / tick).to_integral_value(rounding=ROUND_HALF_UP)
    return (steps * tick).quantize(Decimal("0.0001"))


def _simulated_fill(base_price: Decimal, order_side: str) -> Decimal:
    """Apply slippage then tick-rounding to a raw reference price."""
    return _round_tick(_apply_slippage(base_price, order_side))


async def get_live_ltp(stock_id: int) -> Decimal | None:
    """Latest LIVE tick price from Redis (no fallback). None means there is no
    fresh price — the market is closed or this stock isn't currently trading
    (the `ltp:` key has a 600s TTL). Used to gate off-market paper entries."""
    try:
        import contextlib

        import redis.asyncio as aioredis

        from app.broker.tick_consumer import LTP_KEY

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        try:
            ltp_str: str | None = await r.get(LTP_KEY.format(stock_id=stock_id))
        finally:
            # aclose in finally — a raised GET must not leak the connection
            with contextlib.suppress(Exception):
                await r.aclose()
        return Decimal(ltp_str) if ltp_str else None
    except Exception:
        return None


async def get_current_price(db: AsyncSession, stock_id: int) -> Decimal | None:
    """Best-effort current price: live Redis LTP first, then latest daily close."""
    live = await get_live_ltp(stock_id)
    if live is not None:
        return live

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

    Quantity: an explicit override is used as-is; otherwise the size is
    computed from THIS user's capital and per-trade risk (never the signal's
    generic suggested_qty, which is sized to a house default). A size that
    rounds to zero (stop too wide for the account) is rejected, not clamped.
    """
    entry = Decimal(str(signal.entry_price))
    stop_loss = Decimal(str(signal.stop_loss))
    if quantity is not None:
        qty = quantity
    else:
        qty = compute_quantity(user.capital_inr, user.risk_per_trade_pct, entry, stop_loss)
    if qty <= 0:
        raise PaperOrderError(
            "Position size rounds to 0 at your capital and per-trade risk — "
            "the stop is too wide for this account (raise capital or pick a tighter setup)."
        )

    # Off-market guard: without a live tick price a fill would use a stale prior
    # close (misleading for the paper record). Reject unless the user opts out.
    live_ltp = await get_live_ltp(signal.stock_id)
    if live_ltp is None and not user.allow_offmarket_entry:
        raise PaperOrderError(
            "No live market price for this stock right now — the market may be closed "
            "or the stock isn't trading, so a fill would use a stale prior close. "
            "Enable 'Allow off-market entry' in Settings to override."
        )
    if live_ltp is not None:
        base_price = live_ltp
    else:
        base_price = await get_current_price(db, signal.stock_id) or entry
    fill_price = _simulated_fill(base_price, side)
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

    close_side = "SELL" if position.side == "LONG" else "BUY"
    raw_price = exit_price or await get_current_price(db, position.stock_id)
    if raw_price is None:
        raw_price = position.avg_entry_price  # fallback: flat trade
    price = _simulated_fill(raw_price, close_side)

    now = datetime.now(tz=UTC)
    entry = Decimal(str(position.avg_entry_price))
    gross_pnl = compute_pnl(
        side=position.side, entry=entry, exit_price=price, quantity=position.quantity
    )

    # Net the round-trip trading costs (fees.py) so realized_pnl reflects
    # live-trading returns. Product is inferred from the originating signal's
    # classification (delivery for swing/positional, intraday for scalp/day).
    charges = Decimal("0")
    breakdown: dict[str, object] | None = None
    if settings.paper_costs_enabled:
        classification = "swing"
        if position.signal_id is not None:
            sig = await db.get(Signal, position.signal_id)
            if sig is not None:
                classification = sig.classification
        charges, breakdown = roundtrip_charges(
            position_side=position.side,
            entry_price=entry,
            exit_price=price,
            quantity=position.quantity,
            product=product_for_classification(classification),
        )

    payload: dict[str, object] = {"reason": reason}
    if breakdown is not None:
        payload["charges"] = breakdown

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
        broker_payload=payload,
    )
    db.add(order)

    position.realized_pnl = gross_pnl - charges
    position.charges = charges
    position.unrealized_pnl = Decimal("0")
    position.exit_price = price
    position.exit_reason = reason
    position.closed_at = now

    await db.flush()
    return order, position


async def _estimated_roundtrip_charges(
    db: AsyncSession, position: Position, exit_price: Decimal
) -> Decimal:
    """Estimated round-trip cost for an OPEN position exiting at `exit_price`.

    Lets `unrealized_pnl` be reported NET of costs, so open and closed
    positions read in the same units (a realised trade's `realized_pnl` is
    already net). Returns Decimal('0') when the cost model is disabled.
    """
    if not settings.paper_costs_enabled:
        return Decimal("0")
    classification = "swing"
    if position.signal_id is not None:
        sig = await db.get(Signal, position.signal_id)
        if sig is not None:
            classification = sig.classification
    charges, _ = roundtrip_charges(
        position_side=position.side,
        entry_price=Decimal(str(position.avg_entry_price)),
        exit_price=exit_price,
        quantity=position.quantity,
        product=product_for_classification(classification),
    )
    return charges


async def update_position_pnl(
    db: AsyncSession,
    position: Position,
    price: Decimal | None = None,
) -> Decimal | None:
    """Refresh unrealized_pnl (NET of estimated round-trip costs) on an open
    position and return the price used.

    Pass `price` to reuse a price the caller already fetched (the monitor
    passes the live LTP it acted on); otherwise the best-effort current price
    is used (live LTP → last daily close). Returns None if the position is
    closed or no price is available.
    """
    if position.closed_at is not None:
        return None
    if price is None:
        price = await get_current_price(db, position.stock_id)
    if price is None:
        return None
    gross = compute_pnl(
        side=position.side,
        entry=Decimal(str(position.avg_entry_price)),
        exit_price=price,
        quantity=position.quantity,
    )
    charges = await _estimated_roundtrip_charges(db, position, price)
    position.unrealized_pnl = gross - charges
    return price
