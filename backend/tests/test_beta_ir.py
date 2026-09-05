"""Beta to NIFTY and the information ratio — H12.

On 4,843 published replications the median strategy carries beta +0.17, and stripping that
exposure roughly halves the median edge. We computed neither, which left one blindness: a
cohort that is directionally biased in a trending market looks like skill. We have already
been bitten — the market-regime gate's evidence was a proxy for SIDE (NIFTY below its
200-DMA on 33 of 33 days, every LONG blocked and every SHORT kept).

`side_proxy_guard` catches the extreme version by counting sides. Beta catches the graded
version, and these tests pin that it actually does.
"""

from datetime import date

import pytest
from app.services.beta_ir import MIN_TRADES, BetaIr, Trade, compute, render_lines

# A market that rises 1% per step, so a signed return is easy to reason about.
CLOSES = {date(2026, 8, d): 100.0 * (1.01 ** (d - 1)) for d in range(1, 29)}


def _t(entry: int, exit_: int, side: str, ret: float) -> Trade:
    return Trade(date(2026, 8, entry), date(2026, 8, exit_), side, ret)


class TestBetaIdentifiesMarketExposure:
    def test_a_pure_market_follower_has_beta_one_and_no_alpha(self) -> None:
        """A long whose return IS the market move: all market, no skill."""
        trades = []
        for i in range(20):
            e, x = 1 + i % 5, 6 + i % 5 + i % 3
            mkt = CLOSES[date(2026, 8, x)] / CLOSES[date(2026, 8, e)] - 1
            trades.append(_t(e, x, "LONG", mkt))
        r = compute(trades, CLOSES)
        assert r is not None
        assert r.beta == pytest.approx(1.0, abs=1e-9)
        assert r.alpha == pytest.approx(0.0, abs=1e-9)
        assert r.is_market_driven is True
        # A perfect fit has no residual spread, so the IR is undefined — but beta and
        # alpha are not, and discarding them with it would throw away the primary output.
        assert r.information_ratio is None

    def test_a_market_neutral_edge_has_beta_zero_and_all_alpha(self) -> None:
        """Every trade returns the same 2% regardless of what the market did."""
        trades = [_t(1 + i % 5, 6 + i % 7, "LONG", 0.02) for i in range(20)]
        r = compute(trades, CLOSES)
        assert r is not None
        assert r.beta == pytest.approx(0.0, abs=1e-9)
        assert r.alpha == pytest.approx(0.02, abs=1e-9)
        assert r.is_market_driven is False
        assert r.information_ratio is None  # constant returns ⇒ no residual spread

    def test_the_market_return_is_signed_by_side(self) -> None:
        """⭐ The whole point. A SHORT that profits while the index falls is collecting
        market exposure, not skill. Unsigned, it would read as negative beta and flatter
        the cohort."""
        rising = {date(2026, 8, d): 100.0 + d for d in range(1, 29)}
        longs = [_t(1, 10, "LONG", 0.05) for _ in range(MIN_TRADES)]
        shorts = [_t(1, 10, "SHORT", 0.05) for _ in range(MIN_TRADES)]
        # Same window, opposite sides ⇒ opposite signed market returns.
        from app.services.beta_ir import _signed_market_return

        assert _signed_market_return(longs[0], rising) > 0
        assert _signed_market_return(shorts[0], rising) < 0
        assert _signed_market_return(longs[0], rising) == pytest.approx(
            -_signed_market_return(shorts[0], rising)
        )


class TestDimensionalContract:
    def test_beta_is_dimensionless_for_fractional_returns(self) -> None:
        """⭐ Regression on a bug found while validating this module against the real book.

        Feeding CURRENCY returns against a fractional market move gives a beta carrying
        units (measured at −12,561 on the live book) — arithmetically fine, and completely
        incomparable to the +0.17 published median this finding is calibrated against.
        Same trades, scaled by a notional, must move beta by that scale.
        """
        frac = [_t(1 + i % 4, 8 + i % 5, "LONG", 0.01 * (1 + i % 3)) for i in range(20)]
        rupees = [Trade(t.entry_day, t.exit_day, t.side, t.ret * 50_000) for t in frac]
        a, b = compute(frac, CLOSES), compute(rupees, CLOSES)
        assert a is not None and b is not None
        assert b.beta == pytest.approx(a.beta * 50_000)
        assert abs(a.beta) < 100, "a fractional-return beta must be a small number"


class TestRefusals:
    def test_too_few_trades(self) -> None:
        assert compute([_t(1, 5, "LONG", 0.01)] * (MIN_TRADES - 1), CLOSES) is None

    def test_a_flat_market_cannot_identify_a_slope(self) -> None:
        """Zero would be a claim ('no market exposure'); None is the truth ('not
        estimable here')."""
        flat = {date(2026, 8, d): 100.0 for d in range(1, 29)}
        trades = [_t(1 + i % 4, 8 + i % 5, "LONG", 0.01 * i) for i in range(20)]
        assert compute(trades, flat) is None

    def test_trades_without_index_bars_are_dropped_not_substituted(self) -> None:
        """A wrong window is a wrong beta, so a missing bar drops the trade rather than
        borrowing a nearby one."""
        # Varied windows so the market actually moves across trades (a flat market is
        # separately refused, and would mask what this test is checking).
        trades = [_t(1 + i % 4, 8 + i % 6, "LONG", 0.01 * (i % 3)) for i in range(MIN_TRADES)]
        trades += [_t(1, 30, "LONG", 99.0) for _ in range(5)]  # 30 Aug: no bar → excluded
        sparse = {d: v for d, v in CLOSES.items() if d.day <= 20}
        r = compute(trades, sparse)
        assert r is not None
        assert r.n == MIN_TRADES  # the five bar-less trades never entered the fit

    def test_all_trades_missing_bars(self) -> None:
        assert compute([_t(1, 5, "LONG", 0.01)] * 20, {}) is None


class TestMarketDrivenFlag:
    def _mk(self, alpha: float, explained: float) -> BetaIr:
        return BetaIr(
            n=50, beta=0.5, alpha=alpha, information_ratio=0.1,
            market_mean=0.01, explained_by_market=explained,
        )

    def test_flags_when_the_market_explains_most_of_the_return(self) -> None:
        assert self._mk(alpha=0.002, explained=0.008).is_market_driven is True

    def test_does_not_flag_a_genuinely_market_neutral_cohort(self) -> None:
        assert self._mk(alpha=0.009, explained=0.001).is_market_driven is False

    def test_zero_total_does_not_divide(self) -> None:
        assert self._mk(alpha=0.0, explained=0.0).is_market_driven is False


class TestRender:
    def test_refusal_names_both_conditions(self) -> None:
        out = "\n".join(render_lines(None, label="eligible set"))
        assert "not assessable" in out
        assert "index actually moved" in out

    def test_result_carries_the_market_driven_flag_and_the_limits(self) -> None:
        r = BetaIr(
            n=50, beta=0.9, alpha=0.001, information_ratio=0.05,
            market_mean=0.02, explained_by_market=0.018,
        )
        out = "\n".join(render_lines(r, label="eligible set"))
        assert "MARKET-DRIVEN" in out
        assert "beta **+0.90**" in out
        assert "per-TRADE beta, not a portfolio beta" in out


class TestMarketDrivenGainVsLoss:
    """⭐ The flag fires on outcomes of BOTH signs and they mean opposite things — found on
    the real book, where it printed MARKET-DRIVEN beside a POSITIVE alpha.

    A market-driven GAIN is the failure mode H12 exists to catch: a directionally-biased
    cohort in a trending window looking like skill. A market-driven LOSS says the exposure
    sank an otherwise-positive alpha. One sentence for both would mislead in one of them —
    the A24 rule that a caveat must branch on the data.
    """

    def _mk(self, explained: float) -> BetaIr:
        return BetaIr(
            n=44, beta=0.92, alpha=0.0010, information_ratio=0.017,
            market_mean=explained / 0.92, explained_by_market=explained,
        )

    def test_a_market_driven_gain_names_the_skill_illusion(self) -> None:
        r = self._mk(+0.0031)
        assert r.is_market_driven and r.market_helped
        out = "\n".join(render_lines(r, label="x"))
        assert "MARKET-DRIVEN GAIN" in out
        assert "looks like skill" in out

    def test_a_market_driven_loss_says_the_alpha_is_the_other_sign(self) -> None:
        """The real book's shape: beta +0.92, alpha +0.0010, market explains −0.0031."""
        r = self._mk(-0.0031)
        assert r.is_market_driven and not r.market_helped
        out = "\n".join(render_lines(r, label="x"))
        assert "MARKET-DRIVEN LOSS" in out
        assert "OPPOSITE sign" in out
        assert "looks like skill" not in out, "the gain gloss must not appear on a loss"

    def test_a_market_neutral_cohort_gets_no_gloss_at_all(self) -> None:
        r = BetaIr(
            n=44, beta=0.05, alpha=0.0090, information_ratio=0.30,
            market_mean=0.002, explained_by_market=0.0001,
        )
        out = "\n".join(render_lines(r, label="x"))
        assert "MARKET-DRIVEN" not in out
