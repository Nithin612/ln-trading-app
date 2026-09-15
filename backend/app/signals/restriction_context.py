"""Order-path context loading for the A38 restriction registry.

Moved out of `api/v1/trading.py` in Phase 7.1. It was never API-layer code: it loads
the live state the eligibility gates judge, and the RiskEngine needs it just as much
as the HTTP endpoint does. Leaving it in the router forced `app.trading.risk_engine`
to import from `app.api`, which is an import cycle and, worse, the wrong direction —
the risk layer would depend on the transport.

**Behaviour is unchanged by the move.** Same function, same order, same fail-open
discipline; only its address changed.

`_assert_every_context_is_loadable()` runs at import time and is the guard that a gate
cannot be added to the registry without a loader — without it a new ACTIVE gate would
silently stop enforcing. A loud startup error is the only version of this that cannot
be missed.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.broker.circuit_bands import get_circuit_band_checked
from app.broker.paper_broker import get_live_ltp
from app.models.stock import Stock
from app.services.benchmark import load_market_regime_context, load_rs_context
from app.services.liquidity import load_traded_values
from app.signals import restrictions
from app.trading.atr import atr_timeframe_for, latest_atr

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.signal import Signal

log = logging.getLogger(__name__)


#: Every context key the ORDER path knows how to resolve. Checked against the registry at
#: import time, so a `Restriction` added with a context nobody loads fails at startup
#: instead of being silently skipped whenever the gate that happens to own that key is off
#: (bug-hunter MEDIUM, 2026-09-05 — the hand-maintained sequence A38 set out to delete had
#: survived one level down, in this function).
_LOADABLE_CONTEXT: frozenset[str] = frozenset(
    {
        restrictions.CTX_ATR,
        restrictions.CTX_CIRCUIT_BAND,
        restrictions.CTX_RS,
        restrictions.CTX_MARKET,
        restrictions.CTX_TRADED_VALUES,
        restrictions.CTX_MARKET_PRICE,
        restrictions.CTX_IN_UNIVERSE,
    }
)


def _assert_every_context_is_loadable() -> None:
    """Fail at import if a rule needs context this path cannot resolve.

    `check` fails OPEN on unresolved context, which is right for a display list and wrong
    for the order path: there, an ACTIVE gate that never runs is a gate that silently
    stopped enforcing. A loud startup error is the only version of this that cannot be
    missed."""
    needed: set[str] = set()
    for r in restrictions.REGISTRY:
        if r.enforced_by is not restrictions.EnforcedBy.OVERLAY:
            continue
        needed |= r.requires | r.requires_any
        for _sub, _label, sub_needs in r.sub_requires:
            needed |= sub_needs
    missing = needed - _LOADABLE_CONTEXT
    if missing:
        raise RuntimeError(
            f"order path has no context loader for {sorted(missing)} — add one to "
            "load_restriction_context and _LOADABLE_CONTEXT, or the gate never runs"
        )


_assert_every_context_is_loadable()


async def load_restriction_context(  # noqa: C901 — a flat sequence of INDEPENDENT
    # optional loads, one per context key, each gated on "is any gate that needs this on".
    # The branching is the point: it is what keeps `off` a true no-op (no query, no stamp).
    # Splitting it into per-key helpers would scatter the savepoint/fail-open discipline
    # that has to be identical across all of them.
    db: AsyncSession,
    signal: Signal,
    side: str,
    cfg: restrictions.RestrictionConfig,
    *,
    allow_offmarket: bool,
) -> restrictions.RestrictionContext:
    """Resolve, point-in-time, exactly the context the non-off restrictions need.

    A38: the RULES live in `app/signals/restrictions.py` and are shared with the display
    path; this function does only the I/O the order path can afford.

    Three properties, each load-bearing:

    * **`off` is a TRUE no-op.** A key is loaded only when a restriction that needs it is
      not off, so an off gate costs no query and leaves no stamp.
    * **Every load fails open, inside its own SAVEPOINT.** A DB fault must never suppress
      a trade, and a nested block that rolls back leaves the session usable for
      `place_paper_order` below (cf. `get_circuit_band`'s except→None).
    * **A key joins `available` only when its load SUCCEEDED.** "Looked, found nothing"
      and "the read failed" are opposite answers: the first is a normal fail-open, the
      second means an ACTIVE gate could not be judged and must surface as `unassessed`.
      Conflating them recorded an infra fault as a data-coverage gap, which the shadow
      sidecars then counted as evidence (bug-hunter MEDIUM, 2026-09-05).

    ⚠ **One property deliberately NOT preserved: context is resolved EAGERLY.** The old
    inline chain interleaved load-and-judge and raised on the first block, so gates after
    the blocker did no I/O. Here every non-off gate's context is fetched before any
    judging, so an order rejected by an early gate still pays for the later ones' loads
    (today, with diversity active and the rest shadow: +3 queries and +1 Redis read on a
    blocked click). That is the price of a PURE composer — `check` takes a resolved
    context so it can be shared with the display path and tested without a database — and
    it is charged per Buy click, not per listed row. Said plainly rather than left as a
    docstring claiming an economy the code no longer has (quant-verifier MEDIUM).

    `as_of` is the signal's `created_at`, so every context is the one knowable AT COMMIT —
    the anchoring that keeps these overlays free of look-ahead.
    """
    as_of = signal.created_at
    available: set[str] = set()
    atr: Decimal | None = None
    band = None
    rs_ctx = None
    mkt_ctx = None
    traded: list[Decimal] | None = None
    ltp: Decimal | None = None

    def on(*gates: str) -> bool:
        return any(cfg.mode(g) != "off" for g in gates)

    if on(restrictions.GATE_DIVERSITY, restrictions.GATE_SL_ATR):
        atr = await latest_atr(
            db,
            signal.stock_id,
            timeframe=atr_timeframe_for(signal.classification),
            before=as_of,
        )
        # Available only on a real ATR: without one the sl_atr half is genuinely unjudged,
        # which `unassessed` must surface.
        if atr is not None:
            available.add(restrictions.CTX_ATR)

    if on(restrictions.GATE_CIRCUIT):
        band, ok = await get_circuit_band_checked(signal.stock_id)
        if ok:
            available.add(restrictions.CTX_CIRCUIT_BAND)

    if on(restrictions.GATE_SECTOR_RS):
        # Fail open on ANY DB fault (unmigrated table, JOIN timeout, transient): a
        # benchmark lookup must never suppress a trade. The read runs in a SAVEPOINT so a
        # failure rolls back only the nested block and leaves the session usable for
        # place_paper_order below.
        ok = True
        try:
            async with db.begin_nested():
                rs_ctx = await load_rs_context(
                    db, signal.stock_id, lookback=cfg.sector_rs_lookback, as_of=as_of
                )
        except SQLAlchemyError:
            log.exception(
                "sector-RS context load failed; failing open for stock_id=%s", signal.stock_id
            )
            rs_ctx, ok = None, False
        if ok:
            available.add(restrictions.CTX_RS)

    if on(restrictions.GATE_MARKET_REGIME):
        ok = True
        try:
            async with db.begin_nested():
                mkt_ctx = await load_market_regime_context(
                    db,
                    market_symbol=cfg.market_regime_market_symbol,
                    dma_period=cfg.market_regime_dma_period,
                    as_of=as_of,
                )
        except SQLAlchemyError:
            log.exception(
                "market-regime context load failed; failing open for stock_id=%s",
                signal.stock_id,
            )
            mkt_ctx, ok = None, False
        if ok:
            available.add(restrictions.CTX_MARKET)

    if on(restrictions.GATE_LIQUIDITY):
        ok = True
        try:
            async with db.begin_nested():
                traded = await load_traded_values(
                    db, signal.stock_id, lookback=cfg.liquidity_lookback, as_of=as_of
                )
        except SQLAlchemyError:
            log.exception(
                "liquidity context load failed; failing open for stock_id=%s", signal.stock_id
            )
            traded, ok = None, False
        if ok:
            available.add(restrictions.CTX_TRADED_VALUES)

    if on(restrictions.GATE_CHASE):
        # get_live_ltp does its own Redis read + fail-to-None, so no savepoint is needed.
        ltp = await get_live_ltp(signal.stock_id)
        if ltp is not None:
            available.add(restrictions.CTX_MARKET_PRICE)

    # V3 — universe membership. Unconditional (the rule is `always_on`) and one indexed
    # column on a row the order path has already touched, so there is no mode to check and
    # no cost worth deferring. A failed read fails OPEN — `None` leaves the gate
    # unsatisfied, which `check` reports in `unassessed` rather than treating as excluded.
    in_universe: bool | None = None
    try:
        async with db.begin_nested():
            in_universe = (
                await db.execute(
                    select(Stock.is_active).where(Stock.id == signal.stock_id)
                )
            ).scalar_one_or_none()
    except SQLAlchemyError:
        log.exception(
            "universe-membership load failed; failing open for stock_id=%s", signal.stock_id
        )
        in_universe = None
    if in_universe is not None:
        available.add(restrictions.CTX_IN_UNIVERSE)

    return restrictions.RestrictionContext(
        signal=signal,
        side=side,
        as_of=as_of,
        allow_offmarket=allow_offmarket,
        available=frozenset(available),
        in_universe=in_universe,
        atr=atr,
        market_price=ltp,
        circuit_band=band,
        rs=rs_ctx,
        market=mkt_ctx,
        traded_values=traded,
    )
