"""Signal validity / expiry rules.

Implements SIGNAL_ENGINE.md §5.
"""

from datetime import UTC, datetime, timedelta


def compute_validity_until(
    classification: str,
    created_at: datetime,
    trading_days_offset: int = 0,
) -> datetime:
    """Return the UTC datetime when a signal expires.

    For scalp: 30 minutes from creation.
    For intraday: 3:15 PM IST same trading day (converted to UTC = 9:45 AM UTC).
    For swing: 5 trading days from creation.
    For positional: 30 trading days from creation.

    trading_days_offset: pre-computed calendar days to add (caller resolves trading days).
    When trading_days_offset > 0, it is used directly (for test/backtest injection).
    """
    if classification == "scalp":
        return created_at + timedelta(minutes=30)

    if classification == "intraday":
        # Market closes at 15:30 IST = UTC 10:00. We use 15:15 IST = 09:45 UTC.
        same_day = created_at.date()
        market_close_utc = datetime(
            same_day.year, same_day.month, same_day.day,
            9, 45, 0, tzinfo=UTC
        )
        if created_at > market_close_utc:
            market_close_utc += timedelta(days=1)
        return market_close_utc

    if classification == "swing":
        # 5 trading days ≈ 7 calendar days (safe overestimate; reconciler marks expired)
        days = trading_days_offset if trading_days_offset > 0 else 7
        return created_at + timedelta(days=days)

    if classification == "positional":
        days = trading_days_offset if trading_days_offset > 0 else 42
        return created_at + timedelta(days=days)

    raise ValueError(f"Unknown classification: {classification}")


def is_expired(validity_until: datetime, now: datetime | None = None) -> bool:
    if now is None:
        now = datetime.now(tz=UTC)
    return now >= validity_until
