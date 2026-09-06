"""The gate / hypothesis register — H4.

## Why this exists

Constraint #8 makes Claude the owner of the review calendar and requires raising each item
*unprompted* when its trigger fires. That calendar lives in `docs/PHASES.md` as a markdown
table — fine for a human, useless to code. Three things follow from it being prose:

  1. **`N` in `E[max SR]` is a guess.** `deflated_sharpe.DEFAULT_TRIALS = 20` is hand-picked.
     The deflation is the whole point of the bar, and its most important input is not
     measured. That is the soft spot in the entire instrument (U4).
  2. **The failed-hypothesis archive has no home.** The regime gate (−8R) and R:R≥1 (which
     blocked the book's only profitable cohort) exist as prose in memory files. A programme
     that has reverted two promotions in one week should be able to *count* them.
  3. Nothing can assert the calendar is complete, or that a shipped gate appears in it.

This module is that table as data. It is deliberately a Python module rather than YAML or a
table: it is type-checked, imported by the code that reports it, and covered by tests that
fail when it drifts from the settings that actually exist.

## What counts as a TRIAL

Not everything here consumes a multiple-testing trial. A trial is **a partition we searched
and could have adopted** — that is what inflates the best-of-N Sharpe. Two things are
therefore excluded and say so per entry:

  - **Rules we were always going to enforce.** `entry_diversity` implements hard constraint
    #2 ("never a single indicator"). It was not selected for its returns and could not have
    been rejected for them.
  - **Safety rails.** The notional cap and the daily-loss breaker bound catastrophe; they
    make no claim about edge.

Everything else counts, including the ones already decided against — *especially* those. A
trial count that quietly drops its failures is exactly the selection bias the deflation is
correcting for.

⚠ **This module reports; it does not decide.** `DEFAULT_TRIALS` is untouched deliberately:
raising the assumed N makes the bar harder for every candidate, and changing a bar is a
decision with consequences, taken by a person looking at the discrepancy this module now
makes visible. Sources for every entry are `docs/PHASES.md`'s REVIEW CALENDAR and the
CHANGELOG.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Status(StrEnum):
    ACTIVE = "active"  # enforced on the order path today
    SHADOW = "shadow"  # measured, suppresses nothing
    REVERTED = "reverted"  # was promoted, then refuted by its own forward evidence
    DECIDED_NO = "decided_no"  # measured to a conclusion; stop accruing
    RESEARCH = "research"  # studied, never wired to the order path


@dataclass(frozen=True)
class Hypothesis:
    key: str
    name: str
    status: Status
    #: What it claimed, in the form that could have been wrong.
    prediction: str
    #: What would promote it — or what closed it.
    bar: str
    #: Where the evidence stands, as of `as_of`.
    stands_at: str
    verdict: str
    #: True when this consumed a multiple-testing trial — see the module docstring.
    counts_as_trial: bool = True
    #: What re-opens it. None = closed, do not carry it forward.
    review_due: str | None = None


AS_OF = "2026-09-05"

#: Every partition of the book we have searched, decided or shipped. Transcribed from the
#: REVIEW CALENDAR in docs/PHASES.md; each entry's verdict is quoted from the record rather
#: than re-derived here.
REGISTER: tuple[Hypothesis, ...] = (
    Hypothesis(
        key="regime_adx",
        name="Regime gate — skip transitional ADX 20–25",
        status=Status.REVERTED,
        prediction=(
            "the transitional-ADX band is net-negative; skipping it nearly doubles captured R"
        ),
        bar="≥20 resolved suppressed trades, suppressed set net-negative",
        stands_at="91 resolved suppressed, +0.078 expR",
        verdict=(
            "PROMOTED on 44 observations 2026-08-14, REVERTED 2026-09-02 when 88 refuted it — "
            "all three §8 metrics inverted and the gate SUBTRACTED ~8R. Re-promotion needs a "
            "fresh forward window, not the same backtest"
        ),
        review_due=None,
    ),
    Hypothesis(
        key="rr_min",
        name="R:R ≥ 1 floor",
        status=Status.REVERTED,
        prediction="a target nearer than the stop needs a >50% win rate merely to break even",
        bar="argued as an IDENTITY needing no forward evidence — which was the error",
        stands_at="24 resolved would-block",
        verdict=(
            "PROMOTED 2026-09-02, REVERTED 2026-09-03: the blocked cohort was the book's ONLY "
            "profitable one (+₹10,585, 63% win). R:R<1 is a PROXY FOR A WIDE STOP, and wide "
            "stops are independently the good cohort. An identity still rests on an empirical "
            "premise"
        ),
        review_due=(
            "needs the deflated-Sharpe bar AND a tail check — never the identity argument again"
        ),
    ),
    Hypothesis(
        key="entry_sl_atr",
        name="Stop-too-tight — |entry−SL| < k·ATR",
        status=Status.DECIDED_NO,
        prediction="stops inside one ATR are noise-width and should not be entered",
        bar="the deflated-Sharpe bar (t ≈ 3.6)",
        stands_at="17/20 resolved flagged; eligible set Sharpe +0.046 over n=78 ⇒ t ≈ 0.41",
        verdict=(
            "CLOSED by H8 2026-09-04 — short of the hurdle by ~9×. It passes all three readiness "
            "guards and is still the clearest rejection the bar has produced; the 20-trade trigger "
            "is WITHDRAWN because the count was never the constraint"
        ),
        review_due=None,
    ),
    Hypothesis(
        key="entry_diversity",
        name="Factor diversity — ≥2 scoring factors",
        status=Status.ACTIVE,
        prediction="(none — it implements hard constraint #2, 'never a single indicator')",
        bar="n/a — a stated rule, not a measured edge",
        stands_at="active on the order path; the only ACTIVE order-path gate",
        verdict=(
            "exempt from the edge bar by construction; it could not have been rejected on returns"
        ),
        counts_as_trial=False,
        review_due=None,
    ),
    Hypothesis(
        key="chase",
        name="Anti-chase — LTP run > 0.33R past entry",
        status=Status.SHADOW,
        prediction="a chased entry has spent its reward:risk before it starts",
        bar="≥20 resolved chased trades",
        stands_at="4/20 resolved chased",
        verdict=(
            "far off; the retrospective read says the chase cohort is the loss, but forward n is "
            "thin"
        ),
        review_due="when ≥20 resolved",
    ),
    Hypothesis(
        key="liquidity",
        name="Liquidity junk gate — median daily traded value floor",
        status=Status.SHADOW,
        prediction="names too illiquid to exit are the loss cohort (the SRTL archetype)",
        bar="≥20 resolved illiquid trades AND net-negative",
        stands_at="19/20 resolved illiquid",
        verdict=(
            "5a deep-dive already ruled DON'T FLIP — the illiquid set is net-POSITIVE and the "
            "ACTIVE diversity gate already catches SRTL. Reframe as a sizing/slippage MODIFIER"
        ),
        review_due=None,
    ),
    Hypothesis(
        key="circuit",
        name="Circuit-band proximity",
        status=Status.SHADOW,
        prediction="an entry pinned near its adverse band cannot be exited at any price",
        bar="≥20 resolved blocked entries",
        stands_at="0/20 resolved blocked",
        verdict="nothing to measure yet",
        review_due="when ≥20 resolved",
    ),
    Hypothesis(
        key="sector_rs",
        name="Sector/index relative strength",
        status=Status.SHADOW,
        prediction="stocks lagging their benchmark underperform after entry",
        bar="would-block worse than eligible, plus the shared guards",
        stands_at="vetoed by the tail guard",
        verdict=(
            "NEVER ACTUALLY TESTED — only 3 broad indices exist, so it benchmarks every stock "
            "against NIFTY50. A data gap, not a verdict"
        ),
        review_due="after sector indices are ingested",
    ),
    Hypothesis(
        key="market_regime",
        name="Market regime — 200-DMA + VIX",
        status=Status.SHADOW,
        prediction="entries against the broad-market trend underperform",
        bar="the shared guards plus a 2y corpus run",
        stands_at="banner reads READY; vetoed by side_proxy and tail",
        verdict=(
            "DO NOT FLIP — the banner is measuring SIDE. NIFTY sat below its 200-DMA on 33 of 33 "
            "days: 39 LONG all blocked, 11 SHORT all kept, and NDRAUTO alone is 94% of the long "
            "loss"
        ),
        review_due="a 2y corpus run only",
    ),
    Hypothesis(
        key="momentum_retune",
        name="Momentum weight ×1.5 retune",
        status=Status.DECIDED_NO,
        prediction="up-weighting momentum lifts the confluence's hit rate",
        bar="t >= 3.6 on the trade series, deflated for the best-of-13 selection",
        stands_at="t = +1.00 over 734 corpus trades (forward arm: 7 minted, 0 resolved in 21 days)",
        verdict=(
            "DECIDED NO 2026-09-07. Short of the bar by ~3.6x; DSR 74.8% vs a 95% bar, needing "
            "~4,453 observations against 734 held. ⭐ And the WINNER MOVED: re-running the same "
            "sweep on a slightly larger corpus puts `structure x0.5` first, not momentum x1.5 — "
            "a ranking that reshuffles when the sample nudges was never measuring an ordering, "
            "so the original best-of-12 pick was the selection itself. The forward A/B is no "
            "longer a pending decision. ⚠ Still in-sample (deflation prices the selection, not "
            "the missing holdout), and the lever is per-GROUP while the 6.2 leak is per-FACTOR"
        ),
        review_due=None,
    ),
    Hypothesis(
        key="pair_df",
        name="Pair trading — Dickey-Fuller arm",
        status=Status.SHADOW,
        prediction="a DF t-stat gate selects tradeable cointegrated pairs",
        bar="resolutions in both arms",
        stands_at="nightly minter accruing",
        verdict="accruing",
        review_due="when both arms have resolutions",
    ),
    Hypothesis(
        key="pair_adf",
        name="Pair trading — augmented Dickey-Fuller arm",
        status=Status.SHADOW,
        prediction="ADF selects better pairs than plain DF",
        bar="resolutions in both arms",
        stands_at="nightly minter accruing",
        verdict="accruing",
        review_due="when both arms have resolutions",
    ),
    Hypothesis(
        key="confidence_gate_raise",
        name="Raise the confluence confidence gate above 70%",
        status=Status.DECIDED_NO,
        prediction="the 70–79 band is net-negative, so a higher gate captures more R",
        bar="the §6.2 gate experiment",
        stands_at="tested at corpus scale 2026-08-12",
        verdict=(
            "REJECTED in favour of the regime gate, which beat it — and the regime gate has since "
            "been reverted too"
        ),
        review_due=None,
    ),
    Hypothesis(
        key="intraday_profiles",
        name="Three intraday strategy profiles",
        status=Status.RESEARCH,
        prediction="intraday setups carry an edge worth trading",
        bar="§8 walk-forward with positive risk-adjusted returns",
        stands_at="walk-forward returned NEGATIVE risk-adjusted returns for all three",
        verdict="never activated; runs in shadow so a zero can be attributed to a reason",
        review_due=None,
    ),
    Hypothesis(
        key="heat_cap",
        name="6% portfolio heat cap",
        status=Status.RESEARCH,
        prediction="capping aggregate heat improves outcomes",
        bar="the counterfactual replay",
        stands_at="admitted 12 / skipped 35",
        verdict=(
            "a RISK control, NOT a profitability fix — total is better (+₹5,790) but per-trade is "
            "WORSE (−₹1,478 vs −₹796); chronological admission selects by arrival time, not "
            "quality. "
            "BUILT into the RiskEngine 2026-09-06 (`heat_cap_mode`, `heat_cap_pct`) and shipped "
            "mode=OFF: a 6% cap cuts cycle-1 entries ~74% and cycle 1 exists to accrue volume. "
            "Unlike the selection overlays it FAILS CLOSED — unmeasurable open risk refuses the "
            "next entry rather than counting as zero"
        ),
        # ⚠ STAYS a trial (unlike `notional_cap`, which never claimed an edge). This
        # hypothesis DID make one — "capping aggregate heat improves outcomes" — and was
        # tested against the counterfactual and answered no. Re-labelling it a pure safety
        # rail now, because that is how it ships, would retroactively drop an attempted and
        # failed trial from the count. That is precisely the selection bias the deflation
        # corrects: failures COUNT.
        review_due="flip to `active` at the CYCLE-2 RESET, not before",
    ),
    Hypothesis(
        key="notional_cap",
        name="Per-position notional cap",
        status=Status.ACTIVE,
        prediction="(none — a safety rail bounding catastrophe, not a claim about edge)",
        bar="n/a",
        stands_at="active; reject-never-clamp",
        verdict="shipped 2026-09-02 after a 4-paise stop sized 50,000 shares = ₹1.19cr on ₹1L",
        counts_as_trial=False,
        review_due=None,
    ),
    Hypothesis(
        key="profit_lock_breakeven",
        name="Profit-lock early breakeven at ₹800",
        status=Status.DECIDED_NO,
        prediction="arming breakeven earlier protects more profit",
        bar="an A/B over the closed book",
        stands_at="20 of 99 positions differ",
        verdict=(
            "NOT SHIPPED — 13 runners clipped against 7 blow-ups prevented. The knob's UNITS are "
            "wrong; an ADR-denominated variant with a pre-registered k would be a new trial"
        ),
        review_due="an ADR-denominated variant, pre-registered",
    ),
)


def trials_attempted() -> int:
    """The OBSERVED multiple-testing trial count — a LOWER BOUND on `N` in `E[max SR]`.

    Counts every searched partition including the failures, because a trial count that
    quietly drops its failures is the exact selection bias the deflation corrects for.

    ⚠ **A lower bound, not the number.** One entry here is one HYPOTHESIS, but most were
    evaluated at several thresholds — `sl_atr`'s k, anti-chase's 0.33R, circuit's 1.5%,
    liquidity's floor, the confidence gate's level. Each variant we could have adopted is
    its own trial, so the true N exceeds this count and the register does not yet record
    variants. Reading "observed 15 < assumed 20, so the bar is conservative" would be
    falsely reassuring, which is why `render_lines` says so out loud.
    """
    return sum(1 for h in REGISTER if h.counts_as_trial)


def by_status(status: Status) -> tuple[Hypothesis, ...]:
    return tuple(h for h in REGISTER if h.status is status)


def due_for_review() -> tuple[Hypothesis, ...]:
    """Everything still carrying a trigger. Constraint #8 requires raising these unprompted."""
    return tuple(h for h in REGISTER if h.review_due is not None)


def render_lines(*, assumed_trials: int) -> list[str]:
    """The U4 counter, and the failed-hypothesis archive that gives it meaning."""
    n = trials_attempted()
    reverted = by_status(Status.REVERTED)
    decided = by_status(Status.DECIDED_NO)
    out = [
        f"- **Trials attempted (observed): {n}** vs **{assumed_trials} assumed** by the "
        "deflated-Sharpe bar — "
        + (
            f"the bar is currently **too LENIENT** by {n - assumed_trials} trials"
            if n > assumed_trials
            else (
                f"the bar is currently **stricter** than our search by {assumed_trials - n}"
                if n < assumed_trials
                else "they agree"
            )
        ),
        f"  - {len(reverted)} promoted-then-reverted · {len(decided)} decided against · "
        f"{len(by_status(Status.SHADOW))} still in shadow · "
        f"{len(by_status(Status.ACTIVE))} active",
        "  - ⚠ **observed is a LOWER BOUND**: one entry is one HYPOTHESIS, but most were tried "
        "at several thresholds (`sl_atr`'s k, chase's 0.33R, circuit's 1.5%, liquidity's floor) "
        "and each variant is its own trial. The register does not record variants yet, so "
        "\"observed < assumed, therefore the bar is conservative\" does NOT follow.",
        "  - ⚠ this is a REPORT, not a change: `DEFAULT_TRIALS` is untouched, because raising "
        "the assumed N makes the bar harder for every candidate and that is a decision for a "
        "person, not a side effect.",
    ]
    if reverted:
        out.append(
            "  - reverted: "
            + " · ".join(f"**{h.name}**" for h in reverted)
            + " — kept visible on purpose; a programme that forgets its failures re-runs them"
        )
    return out
