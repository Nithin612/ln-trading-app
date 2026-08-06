"""Paper broker — Phase 8.

Simulates order placement and fills entirely in software:
  - place_paper_order  : create Order + open (or add to) Position
  - close_position     : create a SELL Order, close Position, record P&L
  - get_current_price  : Redis LTP → latest daily close fallback
  - update_position_pnl: refresh unrealized_pnl on an open position
"""

from datetime import UTC, datetime
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

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
    Zero bps is a no-op; the configured default is 2 bps.
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
    """Best-effort current price: live Redis LTP, else the FRESHEST stored close.

    When live ticks are cold (off-market, or a tick outage), the last completed
    1-minute close is the freshest mark available — much fresher than the daily
    close, which lags a full session until the evening EOD ingest. Preferring
    the 1m close keeps unrealised P&L honest instead of stuck a day behind.
    """
    live = await get_live_ltp(stock_id)
    if live is not None:
        return live

    from app.models.market_data import Ohlcv1m, OhlcvDaily

    minute = (
        await db.execute(
            select(Ohlcv1m.close)
            .where(Ohlcv1m.stock_id == stock_id, Ohlcv1m.is_complete.is_(True))
            .order_by(Ohlcv1m.time.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if minute is not None:
        return Decimal(str(minute))

    daily = (
        await db.execute(
            select(OhlcvDaily.close)
            .where(OhlcvDaily.stock_id == stock_id, OhlcvDaily.is_complete.is_(True))
            .order_by(OhlcvDaily.time.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return Decimal(str(daily)) if daily is not None else None


def size_for_fill(
    *,
    capital: Decimal,
    risk_pct: Decimal,
    fill: Decimal,
    stop_loss: Decimal,
    existing_qty: int = 0,
    existing_entry: Decimal | None = None,
) -> int:
    """Risk-first quantity sized from the ACTUAL fill price (not the signal's
    entry), so a fill that drifted from the plan — a chase, a gap, slippage —
    shrinks the quantity to hold the trade's risk at the per-trade budget rather
    than silently over-risking: ``floor(budget / |fill - stop_loss|)``.

    When adding to an ``existing`` open position, the add is sized against the
    REMAINING budget (budget minus the risk already on the book), so repeated
    entries on the same name can't stack risk past the budget. Returns 0 when no
    budget remains, or the stop sits at/through the fill (the caller rejects the
    order — never clamps to a token size)."""
    per_share = abs(fill - stop_loss)
    if per_share <= 0:
        return 0
    if existing_qty <= 0 or existing_entry is None:
        try:
            return compute_quantity(capital, risk_pct, fill, stop_loss)
        except ValueError:
            return 0
    budget = capital * risk_pct / Decimal("100")
    used = Decimal(existing_qty) * abs(existing_entry - stop_loss)
    remaining = budget - used
    if remaining <= 0:
        return 0
    return int((remaining / per_share).to_integral_value(rounding=ROUND_DOWN))


async def place_paper_order(
    db: AsyncSession,
    user: User,
    signal: Signal,
    side: str = "BUY",
    quantity: int | None = None,
) -> tuple[Order, Position]:
    """Place a paper MARKET order and immediately simulate a fill.

    Fill price = current LTP from Redis, or signal's entry_price if unavailable.
    Opens a new Position (or averages into an existing open one for the stock).

    Returns (order, position) — both are already flushed into the session.

    Quantity: an explicit override is used as-is; otherwise the size is computed
    RISK-FIRST from THIS user's capital/risk% **and the actual fill price** (via
    `size_for_fill`), not the signal's entry — so a fill that ran past the plan
    (a chase) reduces the size to keep the trade's risk at the budget instead of
    silently over-risking, and a repeat entry on the same name is sized against
    the remaining budget so risk can't stack. A size that rounds to zero (stop
    too wide, price too far past entry, or already at budget) is rejected, not
    clamped. The entry order records `chase` telemetry in `broker_payload`.
    """
    entry = Decimal(str(signal.entry_price))
    stop_loss = Decimal(str(signal.stop_loss))
    pos_side = "LONG" if side == "BUY" else "SHORT"

    # Determine the FILL first — sizing is risk-first from the actual fill, so
    # the fill must be known before the quantity. Off-market guard is unchanged:
    # without a live tick a fill would use a stale prior close.
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

    # Existing open position for this stock/user/side (a repeat entry averages in).
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

    if quantity is not None:
        qty = quantity
    else:
        qty = size_for_fill(
            capital=user.capital_inr,
            risk_pct=user.risk_per_trade_pct,
            fill=fill_price,
            stop_loss=stop_loss,
            existing_qty=existing.quantity if existing is not None else 0,
            existing_entry=(
                Decimal(str(existing.avg_entry_price)) if existing is not None else None
            ),
        )
    if qty <= 0:
        if existing is not None:
            raise PaperOrderError(
                "This position is already at your per-trade risk budget — close or "
                "reduce it before adding more (a repeat entry would stack risk)."
            )
        raise PaperOrderError(
            "Position size rounds to 0 at your capital and per-trade risk — the stop "
            "is too wide (or the price ran too far past entry) for this account "
            "(raise capital, wait for a better entry, or pick a tighter setup)."
        )

    now = datetime.now(tz=UTC)

    # Chase telemetry (informational; risk is already capped by sizing from the
    # fill). How far past the signal's entry, in R = |entry − SL|, did we fill?
    r_designed = abs(entry - stop_loss)
    chase_move = (fill_price - entry) if pos_side == "LONG" else (entry - fill_price)
    chase_r = (chase_move / r_designed) if r_designed > 0 else Decimal("0")
    order_payload: dict[str, object] = {
        "chase": {
            "signal_entry": str(entry),
            "fill": str(fill_price),
            "chase_r": str(chase_r.quantize(Decimal("0.001"))),
            "past_chase_ceiling": bool(chase_r > Decimal("0.33")),
        }
    }

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
        broker_payload=order_payload,
    )
    db.add(order)

    if existing:
        # Average in — weighted average entry price. SL/TP stay from the first
        # entry (the structural levels the trade was planned around).
        total_qty = existing.quantity + qty
        new_avg = (existing.avg_entry_price * existing.quantity + fill_price * qty) / total_qty
        existing.avg_entry_price = new_avg.quantize(Decimal("0.0001"))
        existing.quantity = total_qty
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
