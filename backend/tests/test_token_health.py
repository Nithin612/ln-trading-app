"""A3 — broker-token status.

The assertion that carries the weight is `test_report_names_the_data_corruption`: this is
not an ops-convenience check, and a report that said only "token expired" would understate
it. A lapsed token makes paper fills price **cheaper than reality**, in the direction that
flatters us — so the alarm has to say that, or a reader will deprioritise it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.models.broker import BrokerToken
from app.services import token_health as th
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import create_test_user

_NOW = datetime(2026, 9, 7, 9, 0, tzinfo=UTC)


def _status(expires: datetime | None) -> th.TokenStatus:
    return th.TokenStatus(user_id=1, expires_at=expires, now=_NOW)


class TestStatusSemantics:
    def test_absent_and_expired_are_distinct(self) -> None:
        """Both mean 'no usable token', but the diagnosis differs and a report that
        conflates them teaches people to ignore it."""
        absent = _status(None)
        expired = _status(_NOW - timedelta(hours=3))
        assert absent.absent and not absent.expired
        assert expired.expired and not expired.absent
        assert not absent.healthy and not expired.healthy

    def test_expiring_soon_is_not_yet_expired(self) -> None:
        s = _status(_NOW + timedelta(minutes=30))
        assert s.expiring_soon
        assert not s.expired
        assert not s.healthy, "a token about to die is not healthy"

    def test_healthy_token(self) -> None:
        s = _status(_NOW + timedelta(hours=8))
        assert s.healthy
        assert not (s.absent or s.expired or s.expiring_soon)

    def test_the_states_are_mutually_exclusive(self) -> None:
        """Exactly one of {absent, expired, expiring_soon, healthy} at any moment —
        overlapping states would let a render branch pick the wrong message."""
        for expires in (
            None,
            _NOW - timedelta(hours=1),
            _NOW + timedelta(minutes=10),
            _NOW + timedelta(hours=10),
        ):
            s = _status(expires)
            assert [s.absent, s.expired, s.expiring_soon, s.healthy].count(True) == 1

    def test_boundary_at_the_warn_threshold(self) -> None:
        exactly = _status(_NOW + th.WARN_AHEAD)
        just_after = _status(_NOW + th.WARN_AHEAD + timedelta(seconds=1))
        assert exactly.expiring_soon, "at the threshold, warn"
        assert just_after.healthy


class TestReadFromDb:
    async def test_no_token_reads_as_absent(self, db: AsyncSession) -> None:
        await create_test_user(db)
        await db.commit()
        s = await th.read_token_status(db, now=_NOW)
        assert s.absent

    async def test_active_token_is_found(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        db.add(
            BrokerToken(
                user_id=user.id, access_token="tok", request_token="req",
                expires_at=_NOW + timedelta(hours=6), is_active=True,
            )
        )
        await db.commit()
        s = await th.read_token_status(db, now=_NOW)
        assert s.healthy
        assert s.user_id == user.id

    async def test_inactive_tokens_are_ignored(self, db: AsyncSession) -> None:
        """A revoked token is not a usable one."""
        user = await create_test_user(db)
        db.add(
            BrokerToken(
                user_id=user.id, access_token="old", request_token="req",
                expires_at=_NOW + timedelta(hours=6), is_active=False,
            )
        )
        await db.commit()
        s = await th.read_token_status(db, now=_NOW)
        assert s.absent

    async def test_the_latest_active_token_wins(self, db: AsyncSession) -> None:
        user = await create_test_user(db)
        for hours in (1, 9):
            db.add(
                BrokerToken(
                    user_id=user.id, access_token=f"t{hours}", request_token="req",
                    expires_at=_NOW + timedelta(hours=hours), is_active=True,
                )
            )
        await db.commit()
        s = await th.read_token_status(db, now=_NOW)
        assert s.healthy, "the newest token is what the feed is using"


class TestRendering:
    def test_report_names_the_data_corruption(self) -> None:
        """⭐ The point of the whole module.

        "Token expired" reads as an ops annoyance. What actually happens is that the feed
        stops, depth expires at its 60 s TTL, spread-aware fills fall back to the flat
        floor, and paper fills price CHEAPER than reality — biased in the flattering
        direction, on a book whose numbers decide a go-live gate. The alarm must say so.
        """
        out = "\n".join(th.render_lines(_status(_NOW - timedelta(hours=1))))
        assert "cheaper than reality" in out
        assert "flat" in out.lower()
        assert "60 s TTL" in out or "60s TTL" in out

    def test_expired_alarm_names_the_remedy_and_that_it_is_normal(self) -> None:
        """Expiry is a normal daily lifecycle event, not a fault — saying so is what stops
        someone building a retry loop around a flow that needs a human at a browser."""
        out = "\n".join(th.render_lines(_status(_NOW - timedelta(hours=1))))
        assert "kite_login.py" in out
        assert "not a fault" in out

    def test_absent_and_expired_render_differently(self) -> None:
        absent = "\n".join(th.render_lines(_status(None)))
        expired = "\n".join(th.render_lines(_status(_NOW - timedelta(hours=2))))
        assert "nobody has logged in" in absent
        assert "EXPIRED" in expired
        assert absent != expired

    def test_healthy_line_still_says_how_long(self) -> None:
        """'The token is fine' is only useful if it says how long that stays true."""
        out = "\n".join(th.render_lines(_status(_NOW + timedelta(hours=6))))
        assert "✅" in out
        assert "6h00m" in out

    def test_expiring_soon_is_a_warning_not_an_alarm_block(self) -> None:
        """A warning is one line; an alarm is a block quote. Rendering a still-working
        token as a full alarm would train the reader to skip alarm blocks."""
        lines = th.render_lines(_status(_NOW + timedelta(minutes=45)))
        assert len(lines) == 1
        assert "⚠️" in lines[0]
        assert not lines[0].startswith(">")

    def test_alarm_is_a_block_quote(self) -> None:
        lines = th.render_lines(_status(None))
        assert lines[0].startswith("> ##")


class TestNeverRaises:
    async def test_a_broken_read_reports_absent_rather_than_throwing(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """⚠ A health probe that can take down the report it appears in has inverted its
        own purpose — the rule `worker_health.read_statuses` already follows."""

        async def _boom(*_a: object, **_k: object) -> object:
            raise RuntimeError("database on fire")

        monkeypatch.setattr(db, "execute", _boom)
        s = await th.read_token_status(db, now=_NOW)
        assert s.absent, "a failed probe degrades to 'absent', it does not raise"
