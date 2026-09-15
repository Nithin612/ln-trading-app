"""§77 — is the universe rule still running, and were its inputs captured?

TWO staleness questions about ONE nightly job, deliberately in one instrument rather
than two:

  SNAPSHOT  — how many trading days behind is `max(universe_snapshot.as_of)`?
  INPUTS    — and was that evaluation's SOURCE recorded (`universe_rule_inputs`)?

⭐ **Why the pair and not just the first.** `materialise_universe` is the only writer of
`stocks.is_active`, and `is_active` gates ingestion breadth, the scan universe and the
live subscription. A beat that silently stopped would freeze the universe at whatever it
last decided — which reads as a perfectly healthy system, because a frozen flag has no
symptom of its own. That is the same shape as the 2026-09-07 outage, and the same shape
6.8.6 was blind to: **the absence of a write is not an error anyone raises.**

⭐ **And the INPUTS half is what makes the answer actionable.** A snapshot with no recorded
input can be seen and never explained — the collapse rail fires on a property of the input
while the snapshot records the rule's output (§73/2). A day where the rule ran but its
source was not captured is therefore a *different* defect from a day where nothing ran,
and reporting them together as "stale" would merge two causes with different remedies.

⚠ **Due at 08:35 IST, not 18:45.** The beat runs at 03:05 UTC, so this passes its own
`due` to `expected_latest_trading_day` rather than inheriting the EOD feeds' cutoff — with
the shared default, every morning before 18:45 would have read as a day behind.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.feed_health import expected_latest_trading_day, trading_days_missing

if TYPE_CHECKING:  # pragma: no cover - annotation only
    from app.services.notifier import Notification

log = logging.getLogger(__name__)
_IST = ZoneInfo("Asia/Kolkata")
#: `materialise-universe` fires at 03:05 UTC = 08:35 IST; allow it until 09:00 to finish
#: before today's evaluation counts as owed.
_UNIVERSE_DUE_IST = time(9, 0)
#: Beyond this many trading days behind, the universe is not merely late — every
#: downstream consumer is acting on a decision nobody re-took.
STALE_ALARM_DAYS = 2


@dataclass(frozen=True)
class UniverseHealth:
    expected: date
    snapshot_as_of: date | None
    snapshot_members: int | None
    snapshot_days_behind: int | None
    inputs_as_of: date | None
    inputs_captured_at: datetime | None
    inputs_days_behind: int | None
    active_stocks: int

    @property
    def snapshot_is_stale(self) -> bool:
        return self.snapshot_days_behind is None or self.snapshot_days_behind >= 1

    @property
    def inputs_are_stale(self) -> bool:
        return self.inputs_days_behind is None or self.inputs_days_behind >= 1

    #: Is there an inputs row for the snapshot being judged? Answered by the query, not
    #: by comparing maxima — see the note on `_SQL`.
    inputs_for_snapshot: bool = False

    @property
    def inputs_match_snapshot(self) -> bool:
        """The evaluation that decided today's universe has its source on record.

        ⚠ Every day before 2026-09-14 fails this by construction — the table did not
        exist. That is why the renderer says "not captured", never "missing" (A24)."""
        return self.snapshot_as_of is not None and self.inputs_for_snapshot

    @property
    def apply_diverged(self) -> bool:
        """⛔ The rule DECIDED a membership and `is_active` says something else.

        **This is the half the first version missed, and it was silent in the dangerous
        direction.** `materialise()` commits the snapshot and `apply_to_stocks` may then
        REFUSE it — the collapse rail or the subscription ceiling — after which the task
        logs an error and returns `applied: False`. Recency alone reads that as perfectly
        healthy: the snapshot IS today's, so `days_behind == 0` and the report rendered
        **"✅ Universe current"** while `is_active` stayed frozen for as many consecutive
        days as the rail kept firing. Every downstream consumer reads `is_active`, not the
        snapshot, so the instrument was measuring the wrong one of the two (bug-hunter
        HIGH, 2026-09-15).

        ⚠ Compares against the count, which is the only cross-check available without a
        per-stock diff. It can miss a same-size swap (one name in, one out) — a real limit,
        but the failure this exists to catch is a REFUSED apply, and a refusal leaves the
        counts differing by construction."""
        return (
            self.snapshot_members is not None
            and self.active_stocks != self.snapshot_members
        )

    @property
    def is_alarming(self) -> bool:
        """⚠ Deliberately NOT `snapshot_is_stale`. One day behind is the normal state
        for most of a trading day — the beat runs in the morning and a report generated
        before it, or on a day it has not yet fired, is not a fault. The alarm is for a
        universe nobody has re-decided for `STALE_ALARM_DAYS` sessions — or one whose
        decision was never APPLIED."""
        return (
            self.snapshot_days_behind is None
            or self.snapshot_days_behind >= STALE_ALARM_DAYS
            or self.apply_diverged
        )


# ⚠ `in_captured` is the captured_at OF THE LATEST ROW, not `max(captured_at)`: those are
# different rows the moment a replay back-fills an older `as_of`, and an audit instrument
# printing one row's date beside another row's time is worse than printing neither.
# ⚠ `in_for_snapshot` ASKS THE REAL QUESTION — "is there an inputs row for the snapshot we
# are judging" — rather than comparing two independent maxima, which false-alarmed whenever
# `record_inputs` had committed today's row and `materialise` had not yet written its
# snapshot (bug-hunter, 2026-09-15).
_SQL = """
WITH snap AS (SELECT max(as_of) AS d FROM universe_snapshot),
     inp  AS (SELECT max(as_of) AS d FROM universe_rule_inputs)
SELECT
    (SELECT d FROM snap)                                             AS snap_as_of,
    (SELECT count(*) FROM universe_snapshot
      WHERE as_of = (SELECT d FROM snap))                            AS snap_members,
    (SELECT d FROM inp)                                              AS in_as_of,
    (SELECT captured_at FROM universe_rule_inputs
      WHERE as_of = (SELECT d FROM inp))                             AS in_captured,
    (SELECT EXISTS (SELECT 1 FROM universe_rule_inputs
                     WHERE as_of = (SELECT d FROM snap)))            AS in_for_snapshot,
    (SELECT count(*) FROM stocks WHERE is_active)                    AS active
"""


async def read_universe_health(
    db: AsyncSession, *, now: datetime | None = None
) -> UniverseHealth:
    """Read-only, and NEVER raises: a health probe that can take down its own report has
    inverted its purpose (`calendar_health` states the rule; `feed_health` learned it the
    expensive way)."""
    now_ist = (now or datetime.now(UTC)).astimezone(_IST)
    try:
        expected = await expected_latest_trading_day(db, now_ist, due=_UNIVERSE_DUE_IST)
        row = (await db.execute(text(_SQL))).one()
        snap_behind = await trading_days_missing(db, row.snap_as_of, expected)
        in_behind = await trading_days_missing(db, row.in_as_of, expected)
    except Exception:  # noqa: BLE001 — a health probe must not raise into its own report
        log.exception("universe health read failed; reporting as unknown")
        today = now_ist.date()
        return UniverseHealth(today, None, None, None, None, None, None, 0, False)

    health = UniverseHealth(
        expected=expected,
        snapshot_as_of=row.snap_as_of,
        snapshot_members=int(row.snap_members or 0) if row.snap_as_of else None,
        snapshot_days_behind=snap_behind,
        inputs_as_of=row.in_as_of,
        inputs_captured_at=row.in_captured,
        inputs_days_behind=in_behind,
        active_stocks=int(row.active or 0),
        inputs_for_snapshot=bool(row.in_for_snapshot),
    )
    if health.is_alarming:
        log.warning(
            "UNIVERSE STALE: last evaluated %s (expected >= %s, %s trading day(s) "
            "behind); %d stocks remain active on a decision nobody re-took",
            health.snapshot_as_of, expected,
            "NEVER" if snap_behind is None else snap_behind, health.active_stocks,
        )
    return health


def to_notification(health: UniverseHealth) -> Notification | None:
    """The proactive push, or None when there is nothing worth a human's attention."""
    from app.services.notifier import Level, Notification

    if not health.is_alarming:
        return None
    # ⭐ Two failures, two remedies, so two messages. "The beat stopped" sends you to the
    # scheduler; "the rule ran and its verdict was refused" sends you to the rail and its
    # threshold. Merging them would send every reader to the wrong place half the time.
    if health.apply_diverged and not health.snapshot_is_stale:
        return Notification(
            event="universe_not_applied",
            level=Level.ERROR,
            title=(
                f"UNIVERSE VERDICT NOT APPLIED — rule decided "
                f"{health.snapshot_members:,}, {health.active_stocks:,} active"
            ),
            lines=[
                f"the rule evaluated {health.snapshot_as_of} and recorded "
                f"{health.snapshot_members:,} members, but is_active holds "
                f"{health.active_stocks:,}",
                "that gap is what a REFUSED apply looks like — the collapse rail or the "
                "subscription ceiling fired and the universe was left frozen",
                "every consumer reads is_active, not the snapshot, so the scan universe "
                "and the live subscription are running on an older decision",
                "REMEDY: read the materialise_universe log for the refusal, then inspect "
                "that day's row in universe_rule_inputs to see WHY the input was small",
            ],
        )
    behind = (
        "NEVER evaluated"
        if health.snapshot_days_behind is None
        else f"{health.snapshot_days_behind} trading day(s) behind"
    )
    return Notification(
        event="universe_stale",
        level=Level.ERROR,
        title=f"UNIVERSE RULE STALE — last evaluated {health.snapshot_as_of or '—'}",
        lines=[
            f"expected an evaluation for >= {health.expected}; {behind}",
            f"{health.active_stocks:,} stocks are still active on a decision nobody re-took",
            "is_active gates ingestion breadth, the scan universe AND the live "
            "subscription, so a frozen flag has no symptom of its own",
            "REMEDY: check the celery beat (materialise-universe, 03:05 UTC) and its log",
        ],
    )


def render_lines(health: UniverseHealth) -> list[str]:
    """Daily-report header. Loud when the universe is stale; a quiet confirmation
    otherwise — and the INPUTS line is always present, because "the rule ran" and "we can
    explain what it decided" are different facts."""
    out: list[str] = []
    if health.apply_diverged and not health.snapshot_is_stale:
        # The rule is CURRENT; its verdict was not adopted. A different sentence, because
        # it is a different fault with a different fix.
        out += [
            "> ## ⚠️ UNIVERSE VERDICT NOT APPLIED (live — as of report generation)",
            ">",
            f"> The rule evaluated **{health.snapshot_as_of}** and recorded "
            f"**{health.snapshot_members:,}** members, but `is_active` holds "
            f"**{health.active_stocks:,}**. That gap is what a **refused apply** looks "
            "like — the collapse rail or the subscription ceiling fired and the universe "
            "was left frozen. Every consumer reads `is_active`, not the snapshot.",
            "> REMEDY: read the `materialise_universe` log for the refusal, then that "
            "day's row in `universe_rule_inputs` for WHY the input was small.",
            "",
        ]
    elif health.is_alarming:
        behind = (
            "**NEVER evaluated**"
            if health.snapshot_days_behind is None
            else f"**{health.snapshot_days_behind}** trading day(s) behind"
        )
        out += [
            "> ## ⚠️ UNIVERSE RULE STALE (live — as of report generation)",
            ">",
            f"> The universe was last evaluated **{health.snapshot_as_of or '—'}**, "
            f"expected ≥ {health.expected} — {behind}. "
            f"**{health.active_stocks:,}** stocks are active on a decision nobody "
            "re-took, and `is_active` gates ingestion breadth, the scan universe and "
            "the live subscription — so a frozen flag has no symptom of its own.",
            "> REMEDY: check the `materialise-universe` beat (03:05 UTC) and its log.",
            "",
        ]
    else:
        members = f"{health.snapshot_members:,}" if health.snapshot_members else "—"
        out += [
            f"> ✅ **Universe current** — evaluated {health.snapshot_as_of} "
            f"({members} members, {health.active_stocks:,} active).",
            "",
        ]
    if health.inputs_match_snapshot:
        out.append(
            f"> ↳ Rule inputs on record for {health.inputs_as_of} "
            f"(captured {health.inputs_captured_at:%Y-%m-%d %H:%M UTC}) — a refusal or a "
            "flip can be explained, not just observed."
        )
    else:
        # A24 — "not captured" is a legitimate rendering; every day before 2026-09-14
        # has no record because the table did not exist, and that is not a fault.
        seen = health.inputs_as_of or "never"
        out.append(
            f"> ↳ ⚠ **Rule inputs NOT captured** for {health.snapshot_as_of or 'that day'} "
            f"(latest captured: {seen}) — the rule's verdict is on record but its SOURCE "
            "is not, so a refusal cannot be explained (§73)."
        )
    out.append("")
    return out
