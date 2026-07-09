"""tradecore.LiveBook FFI contract (Phase 3 slice 3.3).

The engine semantics are pinned by cargo tests; these pin the BOUNDARY:
money as strings in / raw i64·1e-4 out (exact via Decimal, never f64),
fail-loud on bad prices, reject counters, and canon bucket times.
"""

from decimal import Decimal

import pytest
import tradecore

OPEN = 1_000_000
CLOSE = OPEN + 6 * 3600 + 15 * 60


def _book() -> "tradecore.LiveBook":
    book = tradecore.LiveBook(OPEN, CLOSE, [1, 5, 15, 60])
    book.ensure_instruments([42])
    return book


class TestLiveBookBoundary:
    def test_money_round_trips_exactly(self) -> None:
        (event, *_) = _book().on_ticks([(42, OPEN + 3, "123.45", 1000, 0)])
        assert event["open"] == 1_234_500
        assert Decimal(event["open"]) / 10**4 == Decimal("123.45")

    def test_bad_price_fails_loud(self) -> None:
        with pytest.raises(ValueError, match="bad price"):
            _book().on_ticks([(42, OPEN + 3, "garbage", None, 1)])

    def test_bad_session_fails_loud(self) -> None:
        with pytest.raises(ValueError, match="open_ts"):
            tradecore.LiveBook(10, 10, [1])

    def test_reject_counters_exposed(self) -> None:
        book = _book()
        book.on_ticks([(42, OPEN - 5, "1.00", None, 1)])  # pre-open
        book.on_ticks([(42, CLOSE, "1.00", None, 1)])  # close is exclusive
        assert book.rejects(42) == (1, 1, 0, 0)
        assert book.rejects(999) is None

    def test_on_time_commits_every_timeframe_at_close(self) -> None:
        book = _book()
        book.on_ticks([(42, CLOSE - 10, "100.50", 500, 0)])
        events = book.on_time(CLOSE)
        assert sorted(e["tf_minutes"] for e in events if e["kind"] == "committed") == [
            1, 5, 15, 60,
        ]
        # 1h stub bucket starts at open+6h (the 15:15 canon)
        hourly = next(e for e in events if e["tf_minutes"] == 60)
        assert hourly["time"] == OPEN + 6 * 3600
