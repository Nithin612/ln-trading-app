"""A38 — one composable, point-in-time declaration of every tradability rule.

## The problem this replaces

The same eight gates were written out twice: once in `api/v1/trading.py`
::`_apply_eligibility_overlays` (with I/O, raising 409) and once in `eligibility.py`
::`preview` (pure, for the list). Two hand-maintained sequences that must agree on
*which* gates exist, in *what order*, and with *what wording*. They did not: on
2026-09-02 the display path ran none of them and **41 of 204 listed signals offered a Buy
that could only 409**, and five separate Buy surfaces needed retrofitting. The fix shipped
that day was a second sequence kept in step by a contract test and a comment reading
*"⚠ flipping an uncovered gate ACTIVE means extending this module IN THE SAME COMMIT"* —
i.e. a synchronisation ritual, which is the thing that had just failed.

Here each rule is declared **once**. Both paths consume the same ordered registry, so a
new restriction lands everywhere by construction rather than by remembering.

## Point-in-time

Every context loader already accepts `as_of`; nothing could *ask* the composed question.
`RestrictionContext.as_of` makes the anchor explicit and mandatory, so a backtest can ask
"was this restricted **on that date**" — the only correct question for a backtest, and one
we could not previously pose. (Zipline's `HistoricalRestrictions`, via repo 14.)

## Assessability is the safety property

A context field being `None` is ambiguous: *loaded, and there is no band* (fail open —
correct) versus *never loaded* (unknown — must NOT read as clear). `available` resolves it
by naming the context keys a caller actually resolved. A restriction whose `requires` are
not all available is **unassessable**: it fails open like every gate here, but if its mode
is ACTIVE the composer NAMES it in `Outcome.unassessed`. That is how the display path can
skip per-row I/O without silently reporting "clear" — and unlike the previous comment, it
cannot lapse, because `requires` is data the composer reads rather than a rule a human
remembers.

## Enforcement site

`enforced_by` distinguishes the settings-moded overlays (`OVERLAY`) from the paper
broker's own unconditional pre-fill rejections (`BROKER`). Both are declared here so there
is one inventory of what can stop a trade, but the order path runs only the overlays — the
broker enforces its own, and running them twice would double-reject. The preview runs
both, because a user clicking Buy meets both.

Pure: `check` takes modes and thresholds as arguments (the `regime_guard` convention), so
it cannot read a stale `@lru_cache` settings singleton and is trivially testable.
`config_from_settings` is the single impure boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Any

from app.models.signal import Signal
from app.signals import (
    chase_guard,
    circuit_guard,
    entry_quality,
    liquidity_guard,
    market_regime,
    regime_guard,
    rr_guard,
    sector_rs,
)

if TYPE_CHECKING:  # types only — keeps this module free of service-layer imports at runtime
    from app.broker.circuit_bands import CircuitBand
    from app.services.benchmark import MarketRegimeContext, RsContext


# ── Gate identity ─────────────────────────────────────────────────────────────
# Keys are the `settings.<key>_mode` field stems, so a caller builds the mode map straight
# from settings and a missing key is a visible KeyError rather than a silent skip.
GATE_REGIME = "regime_gate"
GATE_CIRCUIT = "circuit_gate"
GATE_ENTRY_QUALITY = "entry_quality"
GATE_DIVERSITY = "entry_diversity_gate"
GATE_SL_ATR = "entry_sl_atr_gate"
GATE_RR = "rr_gate"
GATE_SECTOR_RS = "sector_rs_gate"
GATE_MARKET_REGIME = "market_regime_gate"
GATE_LIQUIDITY = "liquidity_gate"
GATE_CHASE = "chase_gate"
GATE_THROUGH_STOP = "through_stop"
GATE_OFFMARKET = "offmarket"
GATE_QUARANTINE = "signal_quarantine"

# ── Context keys ──────────────────────────────────────────────────────────────
# What a restriction may require. Named constants because `requires` is compared against
# `available` and a typo would silently make a gate permanently unassessable.
CTX_ATR = "atr"
CTX_MARKET_PRICE = "market_price"
CTX_FILL_PRICE = "fill_price"
CTX_CIRCUIT_BAND = "circuit_band"
CTX_RS = "rs"
CTX_MARKET = "market"
CTX_TRADED_VALUES = "traded_values"


class EnforcedBy(Enum):
    """Who actually stops the trade. The order path runs `OVERLAY` only — the broker
    enforces its own pre-fill rejections, and running them here too would double-reject."""

    OVERLAY = "overlay"
    BROKER = "broker"


@dataclass(frozen=True)
class RestrictionContext:
    """Everything any restriction might need, resolved once, as of a point in time.

    `available` names the keys the caller actually RESOLVED. It is not the same as a field
    being non-None: `circuit_band=None` with `CTX_CIRCUIT_BAND` available means "looked,
    no band" (fail open); without it, "never looked" (unassessable). Callers that do the
    I/O add the key even when the load returned nothing or failed open."""

    signal: Signal
    side: str
    as_of: datetime
    #: REQUIRED, and deliberately without a default. `allow_offmarket_entry` defaults
    #: FALSE on the user, so a permissive default here is a safety field that is one
    #: refactor away from being wrong — today it is masked only by the order path
    #: filtering BROKER rules out (quant-verifier MEDIUM).
    allow_offmarket: bool
    available: frozenset[str] = frozenset()
    atr: Decimal | None = None
    market_price: Decimal | None = None
    fill_price: Decimal | None = None
    circuit_band: CircuitBand | None = None
    rs: RsContext | None = None
    market: MarketRegimeContext | None = None
    traded_values: Sequence[Decimal] | None = None

    @property
    def entry(self) -> Decimal:
        return Decimal(str(self.signal.entry_price))

    @property
    def stop_loss(self) -> Decimal:
        return Decimal(str(self.signal.stop_loss))

    @property
    def take_profit(self) -> Decimal:
        return Decimal(str(self.signal.take_profit))


@dataclass(frozen=True)
class RestrictionConfig:
    """Modes and thresholds as data, so `check` stays pure and testable.

    `modes` must carry EVERY gate id in the registry: a partial map was exactly what made
    the previous `unassessed` tripwire imaginary (bug-hunter, 2026-09-02), so `check`
    treats a missing key as a hard error rather than defaulting it to "off"."""

    modes: Mapping[str, str]
    min_scoring_factors: int
    max_dominant_share: Decimal
    min_sl_atr_mult: Decimal
    rr_min: Decimal
    max_chase_r: Decimal
    circuit_proximity_pct: Decimal
    sector_rs_lookback: int
    sector_rs_min_excess_pct: Decimal
    market_regime_dma_period: int
    market_regime_dma_buffer_pct: Decimal
    market_regime_vix_threshold: Decimal
    market_regime_market_symbol: str
    liquidity_lookback: int
    liquidity_min_traded_value: Decimal

    def mode(self, gate: str) -> str:
        return self.modes[gate]


@dataclass(frozen=True)
class Judgement:
    """One restriction's verdict on one signal."""

    gate: str
    mode: str
    blocked: bool
    reason: str | None = None
    #: The verdict body for `orders.broker_payload`. The KEY is not set here: it is
    #: declared once on the `Restriction` and attached by `check`, so there is a single
    #: source of truth for it (quant-verifier: two copies, in the module whose whole
    #: purpose is removing exactly that).
    payload: dict[str, Any] | None = None
    #: Set by `check` from the restriction's declaration; judges never populate it.
    stamp_key: str | None = None
    #: False when the context this restriction requires was not resolved.
    assessable: bool = True


@dataclass(frozen=True)
class Restriction:
    """One tradability rule, declared once and consulted by every path."""

    gate: str
    #: ALL of these context keys must be resolved for the rule to be judged.
    requires: frozenset[str]
    enforced_by: EnforcedBy
    judge: Callable[[RestrictionContext, RestrictionConfig], Judgement]
    #: ...and, when non-empty, AT LEAST ONE of these as well. `through_stop` needs *a
    #: usable price* and either the live one or the modelled fill will do. A plain
    #: `requires` is an AND, which skipped the rule entirely whenever only a fill was
    #: supplied — the preview then reported a void setup as CLEAR (quant-verifier HIGH).
    requires_any: frozenset[str] = frozenset()
    #: `(sub-gate mode key, reported label, context it needs)` for rules that bundle
    #: independently-moded checks. The label is spelled out rather than derived from the
    #: mode key, because the reported string is a client-facing contract.
    #: The rule still RUNS without it — the other half is judged — but that sub-gate is
    #: reported unassessed when it is ACTIVE and its context is absent. Only
    #: entry-quality needs this (diversity needs nothing, sl_atr needs an ATR); it is a
    #: declaration rather than a hardcoded branch so `_unassessed_gates` stays generic
    #: (bug-hunter LOW, 2026-09-05: the one gate not derived from data was the one that
    #: most needed to be).
    sub_requires: tuple[tuple[str, str, frozenset[str]], ...] = ()
    #: `broker_payload` key for the verdict stamp; None = this gate leaves no footprint.
    stamp_key: str | None = None
    #: Always on, with no mode and no setting. ⚠ Distinct from `EnforcedBy.BROKER`, which
    #: was previously the only way to say this and meant something else — *the broker
    #: rejects it*. U11's quarantine is ours and unconditional: a recorded human
    #: withdrawal must not be disableable by a knob, and giving it a mode would create a
    #: `..._gate_mode = off` that silently re-admits a signal a person removed.
    always_on: bool = False


@dataclass(frozen=True)
class Outcome:
    """The composed result: the first block (if any), every judgement, and the gaps."""

    blocked: bool = False
    gate: str | None = None
    reason: str | None = None
    judgements: tuple[Judgement, ...] = field(default_factory=tuple)
    #: ACTIVE gates that could not be assessed — "unknown", never "clear".
    unassessed: tuple[str, ...] = field(default_factory=tuple)

    def stamps(self) -> dict[str, Any]:
        """Verdict stamps for `orders.broker_payload` — only gates that actually ran."""
        return {
            j.stamp_key: j.payload
            for j in self.judgements
            if j.stamp_key is not None and j.payload is not None
        }


def _off(gate: str, mode: str) -> Judgement:
    """A true no-op: no context read, no verdict, no stamp."""
    return Judgement(gate=gate, mode=mode, blocked=False)


# ── The rules ─────────────────────────────────────────────────────────────────
# Each judge is pure. Order below IS the evaluation order and mirrors what the order path
# has always done; the reason a user sees is the first gate hit.


def _judge_regime(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    """Transitional-ADX eligibility. The only gate with no verdict object, so no stamp —
    provenance survives via the persisted `signals.regime` column."""
    mode = cfg.mode(GATE_REGIME)
    if mode == "off":
        return _off(GATE_REGIME, mode)
    reason = regime_guard.order_block_reason(ctx.signal, mode)
    return Judgement(gate=GATE_REGIME, mode=mode, blocked=bool(reason), reason=reason)


def _judge_circuit(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    mode = cfg.mode(GATE_CIRCUIT)
    if mode == "off":
        return _off(GATE_CIRCUIT, mode)
    v = circuit_guard.evaluate(
        entry=ctx.entry,
        side=ctx.side,
        band=ctx.circuit_band,
        proximity_pct=cfg.circuit_proximity_pct,
    )
    reason = circuit_guard.order_block_reason(v, mode)
    return Judgement(
        gate=GATE_CIRCUIT, mode=mode, blocked=bool(reason), reason=reason,
        payload=v.as_payload(),
    )


#: THE gate-mode vocabulary, weakest first. Every `*_gate_mode` setting is typed
#: `Literal["off", "shadow", "active"]` — eight separate declarations with nothing tying
#: them together, which is precisely the shape T7 exists to catch: an enumeration extended
#: in one place and unhandled in another, with no test that fails. A contract test walks
#: the settings model against this tuple, so a fourth mode cannot be added to one knob and
#: silently fall through `_effective_mode` as "off".
GATE_MODES: tuple[str, ...] = ("off", "shadow", "active")


def _effective_mode(*modes: str) -> str:
    """The strongest of several modes: active > shadow > off.

    ⚠ Written out rather than `a or b`: **`"off"` is a non-empty string and therefore
    TRUTHY**, so `div or sl` returns `"off"` whenever diversity is off — which tagged the
    judgement off, made `check` drop it, and silently stopped writing the `entry_quality`
    stamp for the `off`/`shadow` pair, so a non-off gate ran and recorded nothing
    (quant-verifier, found by differential fuzz: 1,885 stamp diffs, all in that one class).

    ⚠ The stamp has no CURRENT reader — `entry_quality_shadow.py` recomputes `eq.evaluate`
    from `Signal` rows with today's thresholds — so this was an audit-trail defect rather
    than a live-evidence one. Worth knowing separately: that recomputation means the
    sl_atr evidence is **not point-in-time**, and retuning `entry_min_sl_atr_mult`
    silently re-partitions every historical `entry-quality-shadow-<date>.md`."""
    if "active" in modes:
        return "active"
    if "shadow" in modes:
        return "shadow"
    return "off"


def _judge_entry_quality(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    """Diversity + stop-too-tight: two independently-moded checks behind one badge,
    because `entry_quality.order_block_reason` returns one combined reason.

    Runs when EITHER is on. With no ATR the sl_atr half is not assessable and fails open,
    which is still correct for the diversity verdict — `_unassessed_gates` records the gap
    separately so an ACTIVE sl_atr is never silently passed."""
    div, sl = cfg.mode(GATE_DIVERSITY), cfg.mode(GATE_SL_ATR)
    if div == "off" and sl == "off":
        return _off(GATE_ENTRY_QUALITY, "off")
    v = entry_quality.evaluate(
        entry=ctx.entry,
        stop_loss=ctx.stop_loss,
        factor_scores=ctx.signal.factor_scores,
        atr=ctx.atr,
        min_scoring_factors=cfg.min_scoring_factors,
        max_dominant_share=cfg.max_dominant_share,
        min_sl_atr_mult=cfg.min_sl_atr_mult,
    )
    reason = entry_quality.order_block_reason(v, div, sl)
    return Judgement(
        gate=GATE_ENTRY_QUALITY, mode=_effective_mode(div, sl),
        blocked=bool(reason), reason=reason, payload=v.as_payload(),
    )


def _judge_rr(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    """Reward:risk floor. Beside entry-quality because both judge the SIGNAL ITSELF
    (malformed levels), ahead of every gate needing live market state."""
    mode = cfg.mode(GATE_RR)
    if mode == "off":
        return _off(GATE_RR, mode)
    v = rr_guard.evaluate(
        entry=ctx.entry, stop_loss=ctx.stop_loss, take_profit=ctx.take_profit, rr_min=cfg.rr_min
    )
    reason = rr_guard.order_block_reason(v, mode)
    return Judgement(
        gate=GATE_RR, mode=mode, blocked=bool(reason), reason=reason,
        payload=v.as_payload(),
    )


def _judge_sector_rs(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    mode = cfg.mode(GATE_SECTOR_RS)
    if mode == "off":
        return _off(GATE_SECTOR_RS, mode)
    v = sector_rs.evaluate(
        stock_closes=ctx.rs.stock_closes if ctx.rs else [],
        benchmark_closes=ctx.rs.benchmark_closes if ctx.rs else None,
        side=ctx.side,
        lookback=cfg.sector_rs_lookback,
        min_excess_pct=cfg.sector_rs_min_excess_pct,
        benchmark_label=ctx.rs.benchmark_symbol if ctx.rs else None,
    )
    reason = sector_rs.order_block_reason(v, mode)
    return Judgement(
        gate=GATE_SECTOR_RS, mode=mode, blocked=bool(reason), reason=reason,
        payload=v.as_payload(),
    )


def _judge_market_regime(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    mode = cfg.mode(GATE_MARKET_REGIME)
    if mode == "off":
        return _off(GATE_MARKET_REGIME, mode)
    v = market_regime.evaluate(
        side=ctx.side,
        market_closes=ctx.market.market_closes if ctx.market else [],
        dma_period=cfg.market_regime_dma_period,
        buffer_pct=cfg.market_regime_dma_buffer_pct,
        vix=ctx.market.vix if ctx.market else None,
        vix_threshold=cfg.market_regime_vix_threshold,
        market_symbol=cfg.market_regime_market_symbol,
    )
    reason = market_regime.order_block_reason(v, mode)
    return Judgement(
        gate=GATE_MARKET_REGIME, mode=mode, blocked=bool(reason), reason=reason,
        payload=v.as_payload(),
    )


def _judge_liquidity(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    mode = cfg.mode(GATE_LIQUIDITY)
    if mode == "off":
        return _off(GATE_LIQUIDITY, mode)
    v = liquidity_guard.evaluate(
        traded_values=list(ctx.traded_values or []),
        side=ctx.side,
        lookback=cfg.liquidity_lookback,
        min_traded_value=cfg.liquidity_min_traded_value,
    )
    reason = liquidity_guard.order_block_reason(v, mode)
    return Judgement(
        gate=GATE_LIQUIDITY, mode=mode, blocked=bool(reason), reason=reason,
        payload=v.as_payload(),
    )


def _judge_chase(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    """Anti-chase: a pre-fill EXECUTION check, distinct from the upstream selection gates,
    which is why it runs last among the overlays. A missing price fails open."""
    mode = cfg.mode(GATE_CHASE)
    if mode == "off":
        return _off(GATE_CHASE, mode)
    v = chase_guard.evaluate(
        entry=ctx.entry,
        stop_loss=ctx.stop_loss,
        market_price=ctx.market_price,
        side=ctx.side,
        max_chase_r=cfg.max_chase_r,
    )
    reason = chase_guard.order_block_reason(v, mode)
    return Judgement(
        gate=GATE_CHASE, mode=mode, blocked=bool(reason), reason=reason,
        payload=v.as_payload(),
    )


#: Verbatim the sentence `place_paper_order` raises with no live tick and no opt-in.
OFFMARKET_REASON = (
    "No live market price for this stock right now — the market may be closed "
    "or the stock isn't trading, so a fill would use a stale prior close. "
    "Enable 'Allow off-market entry' in Settings to override."
)


def through_stop_reason(*, side: str, price: Decimal, stop_loss: Decimal) -> str | None:
    """The rejection for a price already at/through the stop, or None if tradeable.

    A long at/below its own stop (or a short at/above) is a position already through its
    stop before it exists. Owned here so `place_paper_order` and the preview use the
    IDENTICAL sentence.

    ⚠ `price` must be the MODELLED FILL, not the raw LTP: the broker checks its
    post-slippage fill, so a raw-LTP comparison disagrees inside a half-spread band in
    BOTH directions — and a false BLOCK, which hides a tradeable signal, is the worse
    error (quant-verifier, 2026-09-02)."""
    is_long = side.upper() in ("LONG", "BUY")
    if not (price <= stop_loss if is_long else price >= stop_loss):
        return None
    pos_side = "LONG" if is_long else "SHORT"
    return (
        f"Price has moved through this signal's stop loss (₹{stop_loss}) — a "
        f"{pos_side} entered at ₹{price} would already be past its own stop. "
        "The setup is void; wait for a fresh signal rather than entering this one."
    )


def _judge_offmarket(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    """Not settings-moded: always on. Fires most often of anything here, because the list
    is usually read outside market hours and `allow_offmarket_entry` defaults False."""
    blocked = ctx.market_price is None and not ctx.allow_offmarket
    return Judgement(
        gate=GATE_OFFMARKET, mode="active", blocked=blocked,
        reason=OFFMARKET_REASON if blocked else None,
    )


def _judge_quarantine(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    """U11 — a signal a human WITHDREW after the fact.

    ⚠ Unconditional, like the broker's own rejections: it takes no mode and no setting,
    because it is not a claim about the tape that might be wrong. It is a recorded
    statement that this signal should not have existed — the only gate here whose
    authority is a person rather than a measurement.

    ⭐ It is a RESTRICTION rather than a filter on the list query on purpose. A filtered
    signal simply vanishes, which is precisely the invisibility PART XVIII objects to;
    a restriction is rendered by the existing `tradeBlock()` on all four Buy surfaces,
    with its reason verbatim. **The withdrawal stays visible instead of becoming an
    absence nobody can ask about.**
    """
    at = getattr(ctx.signal, "quarantined_at", None)
    if at is None:
        return Judgement(gate=GATE_QUARANTINE, mode="active", blocked=False, reason=None)
    why = getattr(ctx.signal, "quarantine_reason", None) or "no reason recorded"
    return Judgement(
        gate=GATE_QUARANTINE,
        mode="active",
        blocked=True,
        reason=f"signal withdrawn: {why}",
    )


def _judge_through_stop(ctx: RestrictionContext, cfg: RestrictionConfig) -> Judgement:
    price = ctx.fill_price if ctx.fill_price is not None else ctx.market_price
    reason = (
        through_stop_reason(side=ctx.side, price=price, stop_loss=ctx.stop_loss)
        if price is not None
        else None
    )
    return Judgement(
        gate=GATE_THROUGH_STOP, mode="active", blocked=bool(reason), reason=reason
    )


#: THE canonical order. Both paths walk this list, so they cannot disagree about which
#: gates exist or which reason a user sees first. Selection gates precede execution
#: checks; the broker's own rejections come last, as they do in reality.
REGISTRY: tuple[Restriction, ...] = (
    # U11 FIRST, ahead of everything: a withdrawn signal should not be evaluated further,
    # and its reason is the one a user must see. It needs no context — the verdict is
    # recorded on the signal row itself.
    Restriction(
        GATE_QUARANTINE, frozenset(), EnforcedBy.OVERLAY, _judge_quarantine, always_on=True
    ),
    # offmarket requires NOTHING: the ABSENCE of a price is precisely its trigger, so a
    # missing one is an answer rather than a gap.
    Restriction(GATE_OFFMARKET, frozenset(), EnforcedBy.BROKER, _judge_offmarket),
    Restriction(GATE_REGIME, frozenset(), EnforcedBy.OVERLAY, _judge_regime),
    Restriction(GATE_CIRCUIT, frozenset({CTX_CIRCUIT_BAND}), EnforcedBy.OVERLAY,
                _judge_circuit, stamp_key="circuit_gate"),
    Restriction(GATE_ENTRY_QUALITY, frozenset(), EnforcedBy.OVERLAY, _judge_entry_quality,
                stamp_key="entry_quality",
                sub_requires=((GATE_SL_ATR, "entry_quality.sl_atr", frozenset({CTX_ATR})),)),
    Restriction(GATE_RR, frozenset(), EnforcedBy.OVERLAY, _judge_rr, stamp_key="rr_gate"),
    Restriction(GATE_SECTOR_RS, frozenset({CTX_RS}), EnforcedBy.OVERLAY, _judge_sector_rs,
                stamp_key="sector_rs"),
    Restriction(GATE_MARKET_REGIME, frozenset({CTX_MARKET}), EnforcedBy.OVERLAY,
                _judge_market_regime, stamp_key="market_regime"),
    Restriction(GATE_LIQUIDITY, frozenset({CTX_TRADED_VALUES}), EnforcedBy.OVERLAY,
                _judge_liquidity, stamp_key="liquidity"),
    # chase requires NOTHING even though it reads the price: `chase_guard.evaluate`
    # handles a missing one internally as assessable=False and fails open, and the ORDER
    # path does exactly the same — so with no price both paths definitively do not block.
    # Declaring it a gap would raise a warning about a rejection that cannot happen.
    Restriction(GATE_CHASE, frozenset(), EnforcedBy.OVERLAY, _judge_chase,
                stamp_key="chase_gate"),
    # through_stop DOES require one, and this is the asymmetry worth understanding: with
    # `allow_offmarket_entry` on and no live tick the broker still prices a fill off the
    # last close and CAN reject on it. So the answer exists at order time and the preview
    # simply cannot see it — a genuine gap, not a fail-open.
    Restriction(GATE_THROUGH_STOP, frozenset(), EnforcedBy.BROKER, _judge_through_stop,
                requires_any=frozenset({CTX_MARKET_PRICE, CTX_FILL_PRICE})),
)

#: Gate ids whose mode comes from settings — i.e. everything `RestrictionConfig.modes`
#: must carry. The broker's rejections are unconditional and are not in here.
MODED_GATES: tuple[str, ...] = (
    GATE_REGIME, GATE_CIRCUIT, GATE_DIVERSITY, GATE_SL_ATR, GATE_RR,
    GATE_SECTOR_RS, GATE_MARKET_REGIME, GATE_LIQUIDITY, GATE_CHASE,
)


def _mode_of(r: Restriction, cfg: RestrictionConfig) -> str:
    """The effective mode for a restriction, for assessability purposes. Entry-quality is
    two moded checks behind one id; the broker's rejections are always on."""
    if r.gate == GATE_ENTRY_QUALITY:
        return _effective_mode(cfg.mode(GATE_DIVERSITY), cfg.mode(GATE_SL_ATR))
    if r.always_on or r.enforced_by is EnforcedBy.BROKER:
        return "active"
    return cfg.mode(r.gate)


def _satisfied(r: Restriction, ctx: RestrictionContext) -> bool:
    """Whether `ctx` carries the context `r` needs: ALL of `requires`, and — when it is
    non-empty — at least one of `requires_any`. One definition, because the walk and the
    gap report disagreeing is precisely how a rule goes silently unjudged."""
    if not r.requires <= ctx.available:
        return False
    return not r.requires_any or bool(r.requires_any & ctx.available)


def _unassessed_gates(
    restrictions: Sequence[Restriction], ctx: RestrictionContext, cfg: RestrictionConfig
) -> tuple[str, ...]:
    """Every ACTIVE restriction whose required context the caller did not resolve.

    This is the enforcement, not a comment: it is derived from `Restriction.requires`, so
    a gate added to the registry is covered automatically and cannot be forgotten."""
    # Sub-gates FIRST: a bundled check (sl_atr inside entry-quality) cannot be surfaced by
    # the registry walk, because the bundle's own `requires` is empty — the other half
    # needs nothing. Without this an ACTIVE sl_atr judged without an ATR reads as clear.
    # Ordered ahead of the walk to match the sequence the previous implementation produced.
    out: list[str] = []
    for r in restrictions:
        for sub_gate, label, needs in r.sub_requires:
            if cfg.mode(sub_gate) == "active" and not needs <= ctx.available:
                out.append(label)
    out += [r.gate for r in restrictions if _mode_of(r, cfg) == "active" and not _satisfied(r, ctx)]
    return tuple(out)


def check(
    ctx: RestrictionContext,
    cfg: RestrictionConfig,
    *,
    enforced_by: EnforcedBy | None = None,
    restrictions: Sequence[Restriction] = REGISTRY,
) -> Outcome:
    """Walk the registry in order and return the first block, all judgements, and the gaps.

    `enforced_by` narrows the walk — the order path passes `OVERLAY` because the broker
    enforces its own rejections downstream and running them here would double-reject; the
    display path passes None, because a user clicking Buy meets every rule.

    A restriction whose required context is unavailable is SKIPPED, never guessed: it
    fails open like every gate here, and lands in `unassessed` when active. Judgements are
    returned for every gate that ran, blocked or not, so the caller can stamp them.
    """
    chosen = [r for r in restrictions if enforced_by is None or r.enforced_by is enforced_by]
    unassessed = _unassessed_gates(chosen, ctx, cfg)
    judgements: list[Judgement] = []
    first: Judgement | None = None
    for r in chosen:
        if not _satisfied(r, ctx):
            continue
        j = replace(r.judge(ctx, cfg), stamp_key=r.stamp_key)
        if j.mode == "off":
            continue  # a true no-op leaves no footprint
        judgements.append(j)
        if j.blocked:
            # STOP at the first block, as the old preview did by returning. Continuing
            # meant an exception raised by a LATER rule escaped `preview`, and both
            # display callers swallow that into a row indistinguishable from "verified
            # clear" — a blocked signal rendering a live Buy button (bug-hunter LOW). No
            # caller reads post-block judgements, and the order path raises immediately.
            first = j
            break
    if first is not None:
        return Outcome(
            blocked=True, gate=first.gate, reason=first.reason,
            judgements=tuple(judgements), unassessed=unassessed,
        )
    return Outcome(judgements=tuple(judgements), unassessed=unassessed)


def config_from_settings() -> RestrictionConfig:
    """The single impure boundary: live modes and thresholds, in one place.

    Every consumer builds its config here, so `check` is always handed the COMPLETE mode
    map — a partial one is what made the previous tripwire imaginary."""
    from app.core.config import settings

    return RestrictionConfig(
        modes={
            GATE_REGIME: settings.regime_gate_mode,
            GATE_CIRCUIT: settings.circuit_gate_mode,
            GATE_DIVERSITY: settings.entry_diversity_gate_mode,
            GATE_SL_ATR: settings.entry_sl_atr_gate_mode,
            GATE_RR: settings.rr_gate_mode,
            GATE_SECTOR_RS: settings.sector_rs_gate_mode,
            GATE_MARKET_REGIME: settings.market_regime_gate_mode,
            GATE_LIQUIDITY: settings.liquidity_gate_mode,
            GATE_CHASE: settings.chase_gate_mode,
        },
        min_scoring_factors=settings.entry_min_scoring_factors,
        max_dominant_share=Decimal(str(settings.entry_max_dominant_factor_share)),
        min_sl_atr_mult=Decimal(str(settings.entry_min_sl_atr_mult)),
        rr_min=Decimal(str(settings.rr_min)),
        max_chase_r=Decimal(str(settings.chase_max_r)),
        circuit_proximity_pct=Decimal(str(settings.circuit_proximity_pct)),
        sector_rs_lookback=settings.sector_rs_lookback,
        sector_rs_min_excess_pct=Decimal(str(settings.sector_rs_min_excess_pct)),
        market_regime_dma_period=settings.market_regime_dma_period,
        market_regime_dma_buffer_pct=Decimal(str(settings.market_regime_dma_buffer_pct)),
        market_regime_vix_threshold=Decimal(str(settings.market_regime_vix_threshold)),
        market_regime_market_symbol=settings.market_regime_market_symbol,
        liquidity_lookback=settings.liquidity_lookback,
        liquidity_min_traded_value=Decimal(str(settings.liquidity_min_traded_value_inr)),
    )
