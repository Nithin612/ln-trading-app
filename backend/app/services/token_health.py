"""A3 — broker-token status, and what its lapse silently costs.

The Kite access token dies **~06:00 IST every day**. Across cycle 2's 45–50 trading days
that is 45–50 chances for it to lapse unnoticed, and the failure is quiet by construction:

    token lapses → the tick feed stops → `depth:{stock_id}` expires at its 60 s TTL →
    6.8.2's spread-aware fills fall back to the FLAT floor →
    **paper fills quietly CHEAPER than reality**

That last step is why this is a data-QUALITY control and not an ops convenience. A dead
feed does not merely interrupt the record — **it corrupts it**, in the direction that
flatters us, and 82% of live NSE books are wider than the flat 2 bps the fallback charges.
A cycle-2 window read off those fills would overstate the edge.

⚠ **Expiry is a NORMAL lifecycle event, never an error loop** (trading-domain rule). This
module therefore *reports*; it does not attempt re-auth. Kite's login flow needs a human at
a browser, so a retry loop would spin without ever succeeding.

Shaped to match `worker_health` deliberately (same `render_lines` contract, same daily-report
block) rather than opening a second health surface — W2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.models.broker import BrokerToken

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

_IST = ZoneInfo("Asia/Kolkata")

#: Warn this far ahead of expiry. Chosen so a morning report still flags a token that will
#: die before the session ends, rather than after.
WARN_AHEAD = timedelta(hours=2)


@dataclass(frozen=True)
class TokenStatus:
    """One broker token's standing.

    `absent` and `expired` are kept apart even though both mean "no usable token right
    now": absent is a token never obtained (someone has not logged in), expired is one that
    worked and aged out. The remedy is the same command but the *diagnosis* is not, and a
    report that conflates them teaches people to ignore it.
    """

    user_id: int | None
    expires_at: datetime | None
    now: datetime

    @property
    def absent(self) -> bool:
        return self.expires_at is None

    @property
    def expired(self) -> bool:
        return self.expires_at is not None and self.expires_at <= self.now

    @property
    def expiring_soon(self) -> bool:
        return (
            self.expires_at is not None
            and not self.expired
            and self.expires_at - self.now <= WARN_AHEAD
        )

    @property
    def healthy(self) -> bool:
        return not (self.absent or self.expired or self.expiring_soon)

    @property
    def remaining(self) -> timedelta | None:
        if self.expires_at is None:
            return None
        return self.expires_at - self.now


async def read_token_status(
    db: AsyncSession, *, now: datetime | None = None
) -> TokenStatus:
    """The most recent ACTIVE token's standing.

    ⚠ Never raises. This is read by the daily report, and a health check that can take
    down the report it appears in has inverted its own purpose — the same rule
    `worker_health.read_statuses` follows.
    """
    at = now or datetime.now(tz=UTC)
    try:
        row = (
            await db.execute(
                select(BrokerToken)
                .where(BrokerToken.is_active.is_(True))
                .order_by(BrokerToken.expires_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    except Exception:  # noqa: BLE001 — a health probe must not raise into its own report
        log.exception("broker-token status read failed; reporting as absent")
        return TokenStatus(user_id=None, expires_at=None, now=at)

    if row is None:
        return TokenStatus(user_id=None, expires_at=None, now=at)
    expires = row.expires_at
    if expires.tzinfo is None:  # defensive: storage is UTC-aware, but a naive row would
        expires = expires.replace(tzinfo=UTC)  # otherwise compare-crash the report
    return TokenStatus(user_id=row.user_id, expires_at=expires, now=at)


def _hhmm(td: timedelta) -> str:
    total = int(td.total_seconds())
    sign = "-" if total < 0 else ""
    total = abs(total)
    return f"{sign}{total // 3600}h{(total % 3600) // 60:02d}m"


def render_lines(status: TokenStatus) -> list[str]:
    """Daily-report block, matching `worker_health.render_lines`'s contract.

    Loud when there is no usable token; **one quiet line when healthy** — and the quiet
    line still states the remaining time, because "the token is fine" is only useful if it
    says how long that will remain true.
    """
    if status.absent or status.expired:
        why = (
            "no active broker token exists at all — nobody has logged in"
            if status.absent
            else f"the active token EXPIRED {_hhmm(-(status.remaining or timedelta()))} ago"
        )
        return [
            "> ## ⛔ BROKER TOKEN UNUSABLE",
            ">",
            f"> {why}.",
            ">",
            "> **This corrupts the record, it does not merely interrupt it.** With no token",
            "> the tick feed stops, `depth:{stock_id}` expires at its 60 s TTL, and",
            "> spread-aware fills fall back to the FLAT floor — so paper fills price",
            "> **cheaper than reality**, in the direction that flatters us. 82% of live NSE",
            "> books are wider than that floor.",
            ">",
            "> Remedy: `uv run python scripts/kite_login.py` (needs a human at a browser —",
            "> this is a normal daily lifecycle event, not a fault).",
            "",
        ]
    if status.expiring_soon:
        return [
            f"- **Broker token:** ⚠️ expires in **{_hhmm(status.remaining or timedelta())}** "
            f"({(status.expires_at or status.now).astimezone(_IST):%H:%M IST}). Re-auth "
            "before the next session, or fills silently fall back to the flat floor.",
        ]
    return [
        f"- **Broker token:** ✅ valid for {_hhmm(status.remaining or timedelta())} "
        f"(until {(status.expires_at or status.now).astimezone(_IST):%H:%M IST}).",
    ]
