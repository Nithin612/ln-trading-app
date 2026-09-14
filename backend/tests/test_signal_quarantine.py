"""U11 — a withdrawn signal is BLOCKED and VISIBLE, never deleted and never hidden.

⛔ THE 35 SIGNALS THIS EXISTS FOR. Minted 2026-09-09 → 09-11 while the universe was
broken: the scanner saw 1,322 names with every blue chip excluded, so RELIANCE could not
compete for a slot. Each signal's arithmetic is fine — those stocks had bars and the
scorer ran correctly — but the candidate SET was wrong, so they **won the wrong
tournament**. All 35 were still inside their validity window, hence live and clickable on
a repaired universe that would never have produced them.

⭐ Expressed as a `Restriction`, not a filter on the list query. A filtered signal simply
vanishes — the invisibility PART XVIII objects to — while a restriction is rendered by
the existing `tradeBlock()` on all four Buy surfaces with its reason verbatim.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from app.signals import restrictions
from app.signals.restrictions import EnforcedBy

from tests.test_restrictions import _cfg, _ctx


def _quarantined(**kw: object) -> restrictions.RestrictionContext:
    ctx = _ctx(**kw)  # type: ignore[arg-type]
    ctx.signal.quarantined_at = datetime(2026, 9, 14, tzinfo=UTC)
    ctx.signal.quarantine_reason = "minted against the broken universe"
    return ctx


class TestAWithdrawnSignalIsBlocked:
    def test_it_blocks_on_the_order_path(self) -> None:
        out = restrictions.check(
            _quarantined(), _cfg(), enforced_by=EnforcedBy.OVERLAY
        )
        assert out.blocked is True
        assert out.gate == restrictions.GATE_QUARANTINE

    def test_the_reason_reaches_the_user_verbatim(self) -> None:
        """`block_reason` is what the Buy surface renders and what the 409 says; a
        withdrawal the user cannot read is indistinguishable from a bug."""
        out = restrictions.check(
            _quarantined(), _cfg(), enforced_by=EnforcedBy.OVERLAY
        )
        assert out.reason is not None
        assert "minted against the broken universe" in out.reason

    def test_a_missing_reason_still_blocks(self) -> None:
        """Never fail OPEN on an incomplete record: a signal marked withdrawn with no
        reason is still withdrawn."""
        ctx = _ctx()
        ctx.signal.quarantined_at = datetime(2026, 9, 14, tzinfo=UTC)
        ctx.signal.quarantine_reason = None
        out = restrictions.check(ctx, _cfg(), enforced_by=EnforcedBy.OVERLAY)
        assert out.blocked is True
        assert out.reason is not None and "no reason recorded" in out.reason

    def test_an_unquarantined_signal_is_untouched(self) -> None:
        out = restrictions.check(_ctx(), _cfg(), enforced_by=EnforcedBy.OVERLAY)
        assert out.blocked is False

    def test_it_blocks_first_so_its_reason_is_the_one_shown(self) -> None:
        """A withdrawn signal should not be evaluated further, and the reason a user
        sees must be the withdrawal rather than whichever gate happens to fire next."""
        ctx = _quarantined(market_price=None, available=frozenset(), allow_offmarket=False)
        out = restrictions.check(ctx, _cfg())
        assert out.gate == restrictions.GATE_QUARANTINE
        assert [j.gate for j in out.judgements] == [restrictions.GATE_QUARANTINE]


class TestItCannotBeSwitchedOff:
    def test_all_gates_off_does_not_re_admit_a_withdrawn_signal(self) -> None:
        """⭐ THE SAFETY PROPERTY. Every moded gate off — the config a user could
        actually produce — and the withdrawal still holds. A human decision must not be
        reversible by a knob."""
        out = restrictions.check(
            _quarantined(), _cfg(), enforced_by=EnforcedBy.OVERLAY
        )
        assert out.blocked is True

    def test_the_gate_has_no_mode_entry_at_all(self) -> None:
        assert restrictions.GATE_QUARANTINE not in restrictions.MODED_GATES

    def test_it_is_declared_always_on(self) -> None:
        rule = next(
            r for r in restrictions.REGISTRY if r.gate == restrictions.GATE_QUARANTINE
        )
        assert rule.always_on is True
        assert rule.requires == frozenset(), "it must be judgeable from the signal alone"


class TestItIsVisibleNotHidden:
    def test_the_list_path_can_judge_it(self) -> None:
        """It requires no context, so a LIST row can be judged — which is the design:
        the signal is still listed, flagged `⊘ blocked`, rather than vanishing."""
        from app.signals import eligibility

        rule = next(
            r for r in restrictions.REGISTRY if r.gate == restrictions.GATE_QUARANTINE
        )
        assert rule.requires <= eligibility.LIST_AVAILABLE

    def test_it_leaves_no_broker_stamp(self) -> None:
        """Nothing downstream reads a quarantine stamp — the reason is the product."""
        rule = next(
            r for r in restrictions.REGISTRY if r.gate == restrictions.GATE_QUARANTINE
        )
        assert rule.stamp_key is None


class TestTheSignalRowSurvives:
    async def test_quarantining_preserves_the_row_and_its_status(self, db) -> None:  # type: ignore[no-untyped-def]
        """⚠ Withdrawn, NOT deleted: the row is the forensic record of what the broken
        system emitted. And `status` is untouched — it is a LIFECYCLE field the sweeper
        overwrites, so a verdict parked there could be silently undone, and 'expired by
        time' would become indistinguishable from 'withdrawn as contaminated'."""
        from sqlalchemy import text

        from tests.helpers import make_stock

        stock = await make_stock(db, symbol="QUARCO")
        await db.commit()
        await db.execute(
            text(
                "INSERT INTO signals (id, stock_id, direction, classification, timeframe,"
                " entry_price, stop_loss, take_profit, suggested_qty, confidence_pct,"
                " factor_scores, headline, status, validity_until)"
                " VALUES (gen_random_uuid(), :sid, 'BUY', 'swing', '1d',"
                " 100, 95, 115, 10, 80, '{}'::jsonb, 'BUY QUARCO', 'active',"
                " now() + interval '5 days')"
            ),
            {"sid": stock.id},
        )
        await db.commit()

        await db.execute(
            text(
                "UPDATE signals SET quarantined_at = now(), quarantine_reason = :why"
                " WHERE stock_id = :sid"
            ),
            {"why": "test withdrawal", "sid": stock.id},
        )
        await db.commit()

        row = (
            await db.execute(
                text(
                    "SELECT status, quarantined_at IS NOT NULL, quarantine_reason,"
                    " confidence_pct FROM signals WHERE stock_id = :sid"
                ),
                {"sid": stock.id},
            )
        ).first()
        assert row is not None
        assert row[0] == "active", "status must be untouched — the sweeper owns it"
        assert row[1] is True
        assert row[2] == "test withdrawal"
        assert row[3] == 80, "the evidence — scores and all — survives"


def _unused() -> Decimal:  # pragma: no cover - keeps the Decimal import honest
    return Decimal("0")
