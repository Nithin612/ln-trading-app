"""Entry-quality eligibility overlay — Phase 6.8 research track.

Attacks the entry-side leak the SRTL loss exposed (post-mortem in
`docs/analysis/exit-ladder-research-2026-08-18.md`), which the ≥70% confidence
gate does NOT catch:

  1. **Near-single-factor signals (DIVERSITY check).** The confluence confidence
     normalizes by the weight of the factors that SCORED (`total_weighted /
     Σ weight[score≠0]`), so one factor at 0.8 reads 80% — SRTL fired on
     RSI_DIVERGENCE alone with every other factor 0.0. That is "80% but one
     indicator", not real confluence, and it violates the STATED hard rule
     ("confluence only, ≥2 factors, never a single indicator"). ACTIVE by user
     sign-off (2026-08-18): a single-factor signal must not enter.
  2. **Stops far tighter than the stock's volatility (SL_ATR check).** SRTL's ₹0.50
     stop on a volatile ₹39 micro-cap guaranteed a fast stop-out AND amplified
     slippage on the huge quantity risk-first sizing then buys (the qty cancels —
     the real signal is the stop distance measured in ATRs). A TUNABLE threshold, so
     it stays SHADOW until the shadow report earns a flip.

Downstream ELIGIBILITY overlay (frozen confluence engine untouched — the
`regime_guard` / `circuit_guard` shape). Pure (no I/O). **Fail-open** — a signal it
can't assess is eligible on that dimension.

The two checks are moded INDEPENDENTLY (`settings.entry_diversity_gate_mode`,
`settings.entry_sl_atr_gate_mode`; each off / shadow / active) so the hard-rule
enforcement (diversity) can be active while the tunable one (sl_atr) accrues
evidence. `order_block_reason` blocks only on an ACTIVE check that fired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

_Q = Decimal("0.0001")


def factor_diversity(factor_scores: object) -> tuple[int, Decimal | None]:
    """`(scoring_count, dominant_share)` from a signal's `factor_scores`
    ({name: {score, weight, explanation}}). `scoring_count` = factors with a
    non-zero score (the confidence denominator's set). `dominant_share` = the top
    factor's |weight×score| as a fraction of the total — None when nothing scored."""
    if not isinstance(factor_scores, dict):
        return 0, None
    contribs: list[Decimal] = []
    for v in factor_scores.values():
        if not isinstance(v, dict):
            continue
        try:
            score = Decimal(str(v.get("score", 0)))
            weight = Decimal(str(v.get("weight", 0)))
        except (TypeError, ValueError, ArithmeticError):
            continue
        if score != 0:
            contribs.append(abs(weight * score))
    if not contribs:
        return 0, None
    # dominant_share's denominator is Σ|weight×score| over scoring factors — a
    # contribution-share heuristic, deliberately NOT the confidence denominator
    # (Σ weight[score≠0], confluence.py) which reproduces the % rather than breadth.
    total = sum(contribs)
    dominant = (max(contribs) / total) if total > 0 else None
    return len(contribs), dominant


@dataclass(frozen=True)
class EntryQualityVerdict:
    """The overlay's read on one signal — the audit trail stamped on the order's
    `broker_payload["entry_quality"]` so the shadow report can aggregate what each
    check WOULD suppress, and so any decision is reconstructable later. The two
    checks are flagged separately because they are moded (and flipped) separately."""

    diversity_blocked: bool
    sl_blocked: bool
    diversity_reasons: list[str] = field(default_factory=list)
    sl_reasons: list[str] = field(default_factory=list)
    scoring_factors: int = 0
    dominant_share: Decimal | None = None
    sl_atr_mult: Decimal | None = None  # stop distance in ATRs (None if ATR absent)

    @property
    def blocked(self) -> bool:
        """Either check fired, independent of which mode each check is in. A
        convenience union for any consumer that wants the 'would-suppress'
        signal; the shadow service partitions on the two flags directly, and the
        order path uses `order_block_reason` (mode-aware), not this."""
        return self.diversity_blocked or self.sl_blocked

    def as_payload(self) -> dict[str, object]:
        return {
            "diversity_blocked": self.diversity_blocked,
            "sl_blocked": self.sl_blocked,
            "diversity_reasons": list(self.diversity_reasons),
            "sl_reasons": list(self.sl_reasons),
            "scoring_factors": self.scoring_factors,
            "dominant_share": (
                str(self.dominant_share.quantize(_Q)) if self.dominant_share is not None else None
            ),
            "sl_atr_mult": (
                str(self.sl_atr_mult.quantize(_Q)) if self.sl_atr_mult is not None else None
            ),
        }


def evaluate(
    *,
    entry: Decimal,
    stop_loss: Decimal,
    factor_scores: object,
    atr: Decimal | None,
    min_scoring_factors: int,
    max_dominant_share: Decimal,
    min_sl_atr_mult: Decimal,
) -> EntryQualityVerdict:
    """Judge a signal's entry quality on both dimensions. Fail-open: an unassessable
    signal (no factors parsed, ATR absent for the vol check) is not flagged on that
    dimension. Moding/blocking is decided by `order_block_reason`, not here."""
    diversity_reasons: list[str] = []
    count, dominant = factor_diversity(factor_scores)
    # Only judge diversity when we actually parsed factors (count > 0) — a payload
    # we couldn't read fails open rather than flagging every such signal.
    if count > 0:
        if count < min_scoring_factors:
            diversity_reasons.append(
                f"only {count} scoring factor(s) (< {min_scoring_factors}) — single-indicator, "
                "not confluence"
            )
        if dominant is not None and dominant > max_dominant_share:
            diversity_reasons.append(
                f"one factor is {dominant.quantize(_Q)} of the confluence "
                f"(> {max_dominant_share}) — one indicator carries it"
            )

    sl_reasons: list[str] = []
    sl_atr_mult: Decimal | None = None
    sl_distance = abs(entry - stop_loss)
    if atr is not None and atr > 0 and min_sl_atr_mult > 0:
        sl_atr_mult = sl_distance / atr
        if sl_atr_mult < min_sl_atr_mult:
            sl_reasons.append(
                f"stop is {sl_atr_mult.quantize(_Q)}×ATR (< {min_sl_atr_mult}×) — too tight "
                "for the stock's volatility; fast stop-out + slippage amplification"
            )

    return EntryQualityVerdict(
        diversity_blocked=bool(diversity_reasons),
        sl_blocked=bool(sl_reasons),
        diversity_reasons=diversity_reasons,
        sl_reasons=sl_reasons,
        scoring_factors=count,
        dominant_share=dominant,
        sl_atr_mult=sl_atr_mult,
    )


def order_block_reason(
    verdict: EntryQualityVerdict, diversity_mode: str, sl_atr_mode: str
) -> str | None:
    """The 409 reason to reject a paper order on this signal, or None to allow it.
    Blocks only on a check that is BOTH flagged AND in `active` mode — each check is
    moded independently (diversity active by default, sl_atr shadow)."""
    reasons: list[str] = []
    if diversity_mode == "active" and verdict.diversity_blocked:
        reasons += verdict.diversity_reasons
    if sl_atr_mode == "active" and verdict.sl_blocked:
        reasons += verdict.sl_reasons
    if not reasons:
        return None
    return "Signal fails the entry-quality overlay: " + "; ".join(reasons)
