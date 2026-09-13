"""kite_instruments sync + stale sweep (2026-07-17).

Kite's instruments dump is the complete tradable universe for the kept
segments — a row missing from it is dead (delisted equity, moved
exchange, expired derivative). The upsert-only sync let those carcasses
accumulate and keep JOINing into the worker's subscription universe,
where every REST call against them failed `invalid token` (the 07-14/15
morning-repair failures: 16 stocks, 1,584 stale rows by 2026-07-17).

Real test Postgres; `build_kite` stubbed at the module seam (no Kite
calls). The sweep tests are stash-proven to FAIL on the pre-sweep code.
"""

from __future__ import annotations

from typing import Any

import app.broker.kite_client as kite_client
import pytest
from app.broker.kite_client import sync_instruments
from app.broker.tick_consumer import _build_token_stock_map
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock


def _row(token: int, symbol: str, exchange: str = "NSE", itype: str = "EQ") -> dict[str, Any]:
    """One raw dump row in the parsed-list shape kiteconnect returns."""
    return {
        "instrument_token": token,
        "exchange_token": token >> 8,
        "tradingsymbol": symbol,
        "exchange": exchange,
        "instrument_type": itype,
        "name": f"{symbol} Ltd",
        "last_price": 100.0,
        "tick_size": 0.05,
        "lot_size": 1,
        "segment": exchange,
        "expiry": "",
        "strike": 0,
    }


class _StubKC:
    def __init__(self, rows: list[dict[str, Any]]):
        self._rows = rows

    def instruments(self) -> list[dict[str, Any]]:
        return self._rows


def _stub_dump(monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]) -> None:
    monkeypatch.setattr(kite_client, "build_kite", lambda token: _StubKC(rows))


async def _tokens(db: AsyncSession) -> set[int]:
    rows = await db.execute(text("SELECT instrument_token FROM kite_instruments"))
    return {r[0] for r in rows}


class TestStaleSweep:
    async def test_sweep_removes_rows_absent_from_the_dump(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Token rotation: the same symbol reappears under a NEW
        instrument_token and the old row vanishes from the dump. The old
        row must be DELETED — upsert-only left it behind, and the
        symbol-join then carried both tokens (one dead) into the
        subscription universe."""
        _stub_dump(monkeypatch, [_row(101, "ROTATECO"), _row(201, "STAYCO")])
        await sync_instruments(db, "tok")
        assert await _tokens(db) == {101, 201}

        _stub_dump(monkeypatch, [_row(102, "ROTATECO"), _row(201, "STAYCO")])
        with caplog.at_level("INFO"):
            n = await sync_instruments(db, "tok")

        assert n == 2
        assert await _tokens(db) == {102, 201}  # 101 swept; old code kept it
        # the logged count comes from the DELETE's real rowcount
        assert "1 stale swept" in caplog.text

    async def test_sweep_skipped_on_partial_dump(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """A truncated CSV must never mass-delete the table: below the
        _SWEEP_MIN_FRACTION tripwire the sweep is skipped loudly and the
        stale rows survive until a full dump arrives."""
        full = [_row(100 + i, f"BULKCO{i}") for i in range(10)]
        _stub_dump(monkeypatch, full)
        await sync_instruments(db, "tok")

        _stub_dump(monkeypatch, full[:2])  # 2 rows vs 10 in table → < 50%
        with caplog.at_level("WARNING"):
            n = await sync_instruments(db, "tok")

        assert n == 2
        assert len(await _tokens(db)) == 10  # nothing deleted
        assert "sweep SKIPPED" in caplog.text

    async def test_delisted_symbol_drops_out_of_the_worker_join(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both sides of the seam: once a symbol leaves the dump, the
        worker's token_map join must stop producing it — no more doomed
        subscriptions / gap-fills / repairs for instruments Kite no
        longer lists (13 of the 16 failing stocks moved to BSE-only,
        3 delisted outright)."""
        gone = await make_stock(db, symbol="DELISTX")
        stays = await make_stock(db, symbol="ACTIVEX")

        _stub_dump(monkeypatch, [_row(11, "DELISTX"), _row(22, "ACTIVEX")])
        await sync_instruments(db, "tok")
        assert await _build_token_stock_map(db, "tok") == {11: gone.id, 22: stays.id}

        _stub_dump(monkeypatch, [_row(22, "ACTIVEX")])  # DELISTX left the dump
        await sync_instruments(db, "tok")

        assert await _build_token_stock_map(db, "tok") == {22: stays.id}

    async def test_hard_sweep_unwedges_the_fraction_guard(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """bug-hunter MEDIUM (2026-07-17): the single-tier guard counted
        the stale rows in its own denominator, so once stale ≥ live every
        future sync skipped the sweep FOREVER. Rows absent for
        ≥ _HARD_SWEEP_DAYS can't be explained by any truncated download —
        they are deleted BEFORE the guard computes its denominator, even
        on a run whose dump is too small for the young-stale sweep."""
        _stub_dump(monkeypatch, [_row(100 + i, f"WEDGE{i}") for i in range(10)])
        await sync_instruments(db, "tok")
        await db.execute(
            text(
                "UPDATE kite_instruments SET synced_at = synced_at - interval '10 days'"
                " WHERE instrument_token IN (100, 101)"
            )
        )

        _stub_dump(monkeypatch, [_row(102, "WEDGE2")])  # 1 row: young sweep must skip
        await sync_instruments(db, "tok")

        tokens = await _tokens(db)
        assert 100 not in tokens and 101 not in tokens  # hard-swept despite the skip
        assert tokens == set(range(102, 110))  # young stale survived the guard

    async def test_sweep_runs_at_exactly_half(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Boundary pin: the tripwire is a strict < — a dump exactly at
        _SWEEP_MIN_FRACTION of the table sweeps normally."""
        _stub_dump(monkeypatch, [_row(500 + i, f"HALFCO{i}") for i in range(4)])
        await sync_instruments(db, "tok")

        _stub_dump(monkeypatch, [_row(500, "HALFCO0"), _row(501, "HALFCO1")])  # 2 of 4
        await sync_instruments(db, "tok")

        assert await _tokens(db) == {500, 501}

    async def test_surviving_rows_are_refreshed_not_swept(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rows present in consecutive dumps must survive the sweep with
        their fields refreshed (the watermark separates exactly the rows
        the dump did NOT contain)."""
        _stub_dump(monkeypatch, [_row(301, "HOLDCO")])
        await sync_instruments(db, "tok")
        first = (
            await db.execute(text("SELECT synced_at FROM kite_instruments"))
        ).scalar_one()

        rows = [_row(301, "HOLDCO")]
        rows[0]["last_price"] = 111.5
        _stub_dump(monkeypatch, rows)
        await sync_instruments(db, "tok")

        row = (
            await db.execute(
                text("SELECT synced_at, last_price FROM kite_instruments")
            )
        ).one()
        assert row[0] > first  # refreshed, not deleted
        assert float(row[1]) == 111.5


class TestTokenFreeSync:
    """U1 (2026-09-13) — the dump is PUBLIC, and that is what lets it have a
    scheduled owner.

    REGRESSION. `kite_instruments` had exactly one writer, an admin HTTP
    endpoint that requires a Kite access token. Tokens die ~06:00 IST daily
    and are renewable only through an interactive OAuth login, so nothing
    scheduled could ever own this table — which is why it stayed EMPTY for
    five days after the 2026-09-07 dev-DB loss while live_worker logged
    `up: 0 instruments`. Passing no token must take a transport that has no
    token lifetime. These tests fail on the old signature, which required one.
    """

    @staticmethod
    def _csv(rows: list[dict[str, Any]]) -> str:
        cols = list(rows[0].keys())
        body = "\n".join(",".join(str(r[c]) for c in cols) for r in rows)
        return ",".join(cols) + "\n" + body + "\n"

    def _stub_public(
        self, monkeypatch: pytest.MonkeyPatch, rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Stub httpx.get at the module seam; record what was requested."""
        seen: dict[str, Any] = {}

        class _Resp:
            text = self._csv(rows)

            @staticmethod
            def raise_for_status() -> None:
                return None

        def _get(url: str, **kw: Any) -> Any:
            seen["url"] = url
            seen["headers"] = kw.get("headers")
            return _Resp()

        monkeypatch.setattr(kite_client.httpx, "get", _get)

        def _explode(token: str) -> Any:  # pragma: no cover - must not run
            raise AssertionError("build_kite must NOT be called without a token")

        monkeypatch.setattr(kite_client, "build_kite", _explode)
        return seen

    async def test_sync_without_a_token_uses_the_public_dump(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen = self._stub_public(monkeypatch, [_row(301, "PUBCO"), _row(302, "PUBTWO")])

        n = await sync_instruments(db)

        assert n == 2
        assert await _tokens(db) == {301, 302}
        assert seen["url"] == kite_client._INSTRUMENTS_URL
        # No Authorization header: the point is that this path has no token.
        assert not (seen["headers"] or {})

    async def test_public_csv_rows_map_identically_to_the_sdk_shape(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The CSV gives every field as a string; the SDK gives typed values.
        Both must land as the same row, or the two paths would disagree."""
        rows = [_row(401, "SHAPECO")]
        self._stub_public(monkeypatch, rows)
        await sync_instruments(db)
        via_csv = (
            await db.execute(
                text(
                    "SELECT tradingsymbol, exchange, instrument_type, lot_size, tick_size"
                    " FROM kite_instruments WHERE instrument_token = 401"
                )
            )
        ).first()

        await db.execute(text("DELETE FROM kite_instruments"))
        await db.commit()
        _stub_dump(monkeypatch, rows)
        await sync_instruments(db, "tok")
        via_sdk = (
            await db.execute(
                text(
                    "SELECT tradingsymbol, exchange, instrument_type, lot_size, tick_size"
                    " FROM kite_instruments WHERE instrument_token = 401"
                )
            )
        ).first()

        assert via_csv is not None and via_sdk is not None
        assert tuple(via_csv) == tuple(via_sdk)

    async def test_an_http_error_raises_rather_than_emptying_the_table(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failed download must not be read as 'the universe is now empty' —
        that is the sweep's whole hazard, reached by a different door."""
        _stub_dump(monkeypatch, [_row(501, "KEEPCO")])
        await sync_instruments(db, "tok")

        class _Boom:
            text = ""

            @staticmethod
            def raise_for_status() -> None:
                raise RuntimeError("503 from the dump host")

        monkeypatch.setattr(kite_client.httpx, "get", lambda url, **kw: _Boom())

        with pytest.raises(RuntimeError):
            await sync_instruments(db)

        assert await _tokens(db) == {501}


class TestSyncCommits:
    """U1 (2026-09-13) — REGRESSION: the sync did not own its commit.

    `sync_instruments` relied on the caller. Its only caller was the admin
    endpoint, whose `get_db` dependency auto-commits, so the omission was
    invisible for as long as there was exactly one caller. The U1 beat task
    goes through `run_db_task`, which does NOT commit — the first scheduled
    run upserted 57,595 rows, rolled them all back, and logged
    "Kite instruments synced: 57595 rows upserted" on the way out.

    ⚠ This must be asserted from a SEPARATE session. `flush()` makes rows
    visible to THIS session; only `commit()` makes them real
    (.claude/rules/python.md), so a same-session assertion passes vacuously
    on the old code.
    """

    async def test_rows_are_visible_to_another_session(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_dump(monkeypatch, [_row(601, "COMMITCO"), _row(602, "COMMITTWO")])
        await sync_instruments(db, "tok")

        # ⚠ The TEST engine's factory, never `app.db.session.AsyncSessionFactory`.
        # The app engine is a module global shared with `run_db_task`, which
        # disposes it inside its own loop; a connection opened on it here stays
        # bound to this test's loop and makes a LATER test die with "Event loop
        # is closed". Caught by running the suite in a different order.
        from tests.conftest import _SessionFactory

        async with _SessionFactory() as other:
            seen = {
                r[0]
                for r in await other.execute(text("SELECT instrument_token FROM kite_instruments"))
            }
        assert seen == {601, 602}  # old code: set() — rolled back

    async def test_the_sync_leaves_no_open_transaction(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The canary, stated in-process: after the sync there is nothing left
        for a caller to commit OR to roll back. On the old code the session was
        still inside a transaction here, which is exactly how `run_db_task`
        discarded the work."""
        _stub_dump(monkeypatch, [_row(701, "DURABLE")])
        await sync_instruments(db, "tok")

        assert not db.in_transaction()


class TestUnusableDumpRaises:
    """U1 follow-up (bug-hunter, 2026-09-13) — a scheduled sync may not succeed
    silently.

    REGRESSION. `if not rows / if not records: return 0` reported SUCCESS. A dump
    host answering HTTP 200 with a login interstitial or an error page passes
    `raise_for_status()`, parses into junk-keyed rows, and maps to zero kept
    records — so the beat task would log `kite_instruments refreshed: 0 rows` at
    INFO and finish SUCCESS every weekday forever while the table went stale.
    Stale is worse than empty here: it is not a step change, so the live worker's
    COLLAPSE arm never sees it either.
    """

    async def test_an_html_page_raises_instead_of_reporting_zero(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _Html:
            # Multi-line on purpose: DictReader takes line 1 as a header and
            # yields the rest as junk-keyed rows, so this reaches the
            # "parsed N rows but kept 0" arm rather than the empty-body one.
            text = (
                "<html>\n<head><title>Login</title></head>\n"
                "<body>Please log in</body>\n</html>\n"
            )

            @staticmethod
            def raise_for_status() -> None:
                return None

        monkeypatch.setattr(kite_client.httpx, "get", lambda url, **kw: _Html())

        with pytest.raises(RuntimeError, match="not a Kite instruments CSV"):
            await sync_instruments(db)

    async def test_an_empty_dump_raises(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_dump(monkeypatch, [])
        with pytest.raises(RuntimeError, match="empty"):
            await sync_instruments(db, "tok")

    async def test_an_unusable_dump_leaves_existing_rows_untouched(
        self, db: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both checks sit before every write, so a bad dump can neither
        half-apply nor trigger the stale sweep."""
        _stub_dump(monkeypatch, [_row(801, "SAFECO"), _row(802, "SAFETWO")])
        await sync_instruments(db, "tok")

        _stub_dump(monkeypatch, [])
        with pytest.raises(RuntimeError):
            await sync_instruments(db, "tok")

        assert await _tokens(db) == {801, 802}
