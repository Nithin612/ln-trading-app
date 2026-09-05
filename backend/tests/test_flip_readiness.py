"""Shared readiness guards (2026-09-03).

Built after two gates were promoted on favourable banners and had to be reverted within a
week, and after the market-regime sidecar was found printing ✅ READY on evidence that
could not certify anything: NIFTY sat below its 200-DMA on 33 of 33 days, so the gate was
a proxy for SIDE, and its negative mean was 94% one trade (NDRAUTO −₹14,970) while the
cohort it wanted to block had the BETTER median (+₹156) and win rate (54%).

These are the shared vetoes. Each sidecar keeps its own count/sign rules; a failure here
refuses READY regardless of how good the headline looks.
"""

from datetime import timedelta
from decimal import Decimal

from app.services import flip_readiness as fr


def _row(side: str, blocked: bool, pnl: str | None) -> fr.Row:
    return fr.Row(side=side, blocked=blocked, realized=None if pnl is None else Decimal(pnl))


class TestSideProxyGuard:
    def test_perfect_side_split_is_vetoed(self) -> None:
        """The market-regime case: every LONG blocked, every SHORT kept."""
        rows = [_row("LONG", True, "-100") for _ in range(20)]
        rows += [_row("SHORT", False, "-5") for _ in range(10)]
        g = fr.side_proxy_guard(rows)
        assert g.ok is False
        assert "PROXY FOR SIDE" in g.reason
        assert fr.veto(rows) is not None

    def test_mixed_partition_passes(self) -> None:
        rows = [_row("LONG", True, "-100"), _row("SHORT", True, "-90"),
                _row("LONG", False, "50"), _row("SHORT", False, "40")] * 5
        assert fr.side_proxy_guard(rows).ok is True

    def test_near_perfect_split_is_also_vetoed(self) -> None:
        """95% purity, not just 100% — a near-proxy cannot certify either."""
        rows = [_row("LONG", True, "-100") for _ in range(19)] + [_row("SHORT", True, "-80")]
        rows += [_row("SHORT", False, "-5") for _ in range(20)]
        assert fr.side_proxy_guard(rows).ok is False

    def test_empty_side_of_partition_is_not_assessable(self) -> None:
        rows = [_row("LONG", True, "-100") for _ in range(5)]
        g = fr.side_proxy_guard(rows)
        assert g.ok is True and "not assessable" in g.reason


class TestTailGuard:
    def test_positive_median_with_negative_mean_is_vetoed(self) -> None:
        """The exact market-regime shape: typically profitable, mean wrecked by outliers."""
        rows = [_row("LONG", True, "150") for _ in range(9)]     # median +150
        rows += [_row("LONG", True, "-15000")]                    # mean strongly negative
        rows += [_row("SHORT", False, "-5") for _ in range(5)]
        g = fr.tail_guard(rows)
        assert g.ok is False
        assert "MEDIAN" in g.reason and "carried by a few large losses" in g.reason

    def test_sign_that_does_not_survive_trimming_is_vetoed(self) -> None:
        """Median ≤ 0 (so the median check passes and we reach the trim check), but the
        mean is negative ONLY because of the single worst outcome.

        Blocked set = five ₹0 + four +₹1 + one −₹5,000: median ₹0, mean −₹499. Drop the
        worst 1 (10% of 10) and the mean becomes +₹0.44 — the sign was entirely that one
        trade. Sides are alternated so `side_proxy` is not what fires here."""
        blocked = ["0", "0", "0", "0", "0", "1", "1", "1", "1", "-5000"]
        rows = [
            _row("LONG" if i % 2 else "SHORT", True, v) for i, v in enumerate(blocked)
        ]
        rows += [_row("LONG" if i % 2 else "SHORT", False, "10") for i in range(5)]
        g = fr.tail_guard(rows)
        assert g.ok is False
        # Assert the MEANING, not the phrasing — a wording tweak should not break this.
        assert "tail-driven" in g.reason

    def test_net_positive_would_block_says_so_instead_of_claiming_losses(self) -> None:
        """REGRESSION: the first version said "the negative mean is carried by a few large
        losses" even when the mean was POSITIVE — the liquidity sidecar emitted exactly
        that on its first run (median ₹515, mean ₹326). A guard built to stop misleading
        banners must not emit one itself."""
        rows = [_row("LONG" if i % 2 else "SHORT", True, "500") for i in range(10)]
        rows += [_row("LONG" if i % 2 else "SHORT", False, "-10") for i in range(5)]
        g = fr.tail_guard(rows)
        assert g.ok is False
        assert "net-POSITIVE" in g.reason
        assert "carried by a few large losses" not in g.reason

    def test_a_genuinely_negative_cohort_passes(self) -> None:
        rows = [_row("LONG", True, "-500") for _ in range(10)]
        rows += [_row("SHORT", False, "100") for _ in range(5)]
        assert fr.tail_guard(rows).ok is True

    def test_too_few_resolved_is_not_assessable(self) -> None:
        rows = [_row("LONG", True, "-500"), _row("LONG", True, "-400")]
        g = fr.tail_guard(rows)
        assert g.ok is True and "not assessable" in g.reason


class TestWinRateGuard:
    def test_blocked_winning_more_often_is_vetoed(self) -> None:
        """54% blocked vs 47% eligible — the real market-regime numbers."""
        rows = [_row("LONG", True, "100") for _ in range(6)] + [_row("LONG", True, "-900")] * 4
        rows += [_row("SHORT", False, "50") for _ in range(4)] + [_row("SHORT", False, "-60")] * 6
        g = fr.win_rate_guard(rows)
        assert g.ok is False and "wins MORE often" in g.reason

    def test_blocked_losing_more_often_passes(self) -> None:
        rows = [_row("LONG", True, "-100") for _ in range(8)] + [_row("LONG", True, "50")] * 2
        rows += [_row("SHORT", False, "50") for _ in range(8)] + [_row("SHORT", False, "-10")] * 2
        assert fr.win_rate_guard(rows).ok is True


class TestVeto:
    def test_clean_evidence_returns_no_veto(self) -> None:
        """A gate whose blocked set genuinely loses more often AND is not a side proxy
        AND survives trimming must NOT be vetoed — the guards are a filter on bad
        evidence, not a blanket refusal."""
        rows = []
        for i in range(12):
            rows.append(_row("LONG" if i % 2 else "SHORT", True, "-400"))
        for i in range(12):
            rows.append(_row("LONG" if i % 2 else "SHORT", False, "200"))
        assert fr.veto(rows) is None
        assert all(g.ok for g in fr.guards(rows))

    def test_veto_names_every_failing_guard(self) -> None:
        rows = [_row("LONG", True, "150") for _ in range(9)] + [_row("LONG", True, "-15000")]
        rows += [_row("SHORT", False, "-5") for _ in range(10)]
        v = fr.veto(rows)
        assert v is not None
        # side proxy AND tail AND win-rate all fire on this shape
        assert "side_proxy" in v and "tail" in v and "win_rate" in v


class TestBlockBootstrapInEvidence:
    """H1 — the non-parametric complement to the DSR bar, rendered beside it.

    Blocks are runs of CONSECUTIVE trades, so the series must be in time order. Sidecars
    sort their rows for display (market_regime sorts newest-first), so the ordering cannot
    be left to convention — `Row.at` carries it and the bootstrap refuses without it.
    """

    def _dated(self, i: int, *, blocked: bool, pnl: str) -> fr.Row:
        from datetime import UTC, datetime

        return fr.Row(
            side="LONG",
            blocked=blocked,
            realized=Decimal(pnl),
            at=datetime(2026, 8, 1, tzinfo=UTC) + timedelta(days=i),
        )

    def test_evidence_includes_the_bootstrap_when_rows_are_dated(self) -> None:
        rows = [
            self._dated(i, blocked=False, pnl=str(500 if i % 3 else -300)) for i in range(30)
        ]
        out = "\n".join(fr.evidence_lines(rows, label="test gate"))
        assert "block bootstrap" in out
        assert "90% interval" in out

    def test_undated_rows_refuse_rather_than_bootstrap_an_arbitrary_order(self) -> None:
        """Fail closed: an interval computed from arbitrarily-ordered blocks would look
        authoritative while measuring nothing."""
        rows = [
            fr.Row(side="LONG", blocked=False, realized=Decimal(500 if i % 3 else -300))
            for i in range(30)
        ]
        out = "\n".join(fr.evidence_lines(rows, label="test gate"))
        assert "block bootstrap" in out
        assert "not assessable" in out

    def test_display_order_does_not_change_the_result(self) -> None:
        """A sidecar that sorts newest-first must get the same number as one that does not
        — which is the whole reason the timestamp is carried."""
        rows = [
            self._dated(i, blocked=False, pnl=str(500 if i % 3 else -300)) for i in range(30)
        ]
        forward = "\n".join(fr.evidence_lines(rows, label="g"))
        reverse = "\n".join(fr.evidence_lines(list(reversed(rows)), label="g"))
        assert forward == reverse
