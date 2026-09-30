"""CAS (Closing Auction Session) capture — Stage 1 (parse + upsert idempotency + window guard).

Covers: parsing the non-documented Kite /quote auction fields; the upsert that FREEZES the
pre-auction price on the first capture while converging the rest to the final auction print; and the
task's CAS-window self-guard."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

from app.models.stock import CasDaily
from app.services import cas_capture as cc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

D = Decimal
TD = date(2026, 8, 25)


class TestParse:
    def test_full_auction_quote(self) -> None:
        p = cc.parse_cas({
            "last_price": 1317, "indicative_close_price": 1317.5,
            "total_imbalance_qty": -72596, "reference_limit_price": 1310.2,
        })
        assert p is not None
        assert p.last_price == D("1317") and p.indicative_close == D("1317.5")
        assert p.reference_price == D("1310.2") and p.total_imbalance_qty == -72596

    def test_pre_auction_zeros_preserved(self) -> None:
        # Before the auction populates (~15:21) the fields are 0 — kept, not dropped.
        p = cc.parse_cas({"last_price": 1312.7, "indicative_close_price": 0, "total_imbalance_qty": 0})  # noqa: E501
        assert p is not None
        assert p.indicative_close == D("0") and p.total_imbalance_qty == 0
        assert p.reference_price is None  # absent → None

    def test_no_last_price_is_unusable(self) -> None:
        assert cc.parse_cas({"indicative_close_price": 100}) is None
        assert cc.parse_cas(None) is None
        assert cc.parse_cas("nope") is None  # type: ignore[arg-type]

    def test_malformed_imbalance_falls_to_none(self) -> None:
        p = cc.parse_cas({"last_price": 100, "total_imbalance_qty": "x"})
        assert p is not None and p.total_imbalance_qty is None


class _FakeKite:
    def __init__(self, quotes: dict[str, Any]) -> None:
        self._quotes = quotes

    async def quote(self, batch: list[Any]) -> dict[str, Any]:
        return {k: self._quotes[k] for k in batch if k in self._quotes}


def _always_in_session(_ts: datetime) -> bool:
    return True


def _never_in_session(_ts: datetime) -> bool:
    return False


class TestCapture:
    async def test_upsert_freezes_pre_auction_and_converges(self, db: AsyncSession) -> None:
        stock = await make_stock(db, symbol="RELIANCE")
        await db.commit()
        smap = {"NSE:RELIANCE": stock.id}

        # 1) pre-auction poll (~15:15): indicative 0, imbalance 0.
        pre = _FakeKite({"NSE:RELIANCE": {
            "last_price": 1312.7, "indicative_close_price": 0,
            "total_imbalance_qty": 0, "reference_limit_price": 1310,
        }})
        assert await cc.capture_cas(db, pre, smap, trade_date=TD) == 1
        row = (await db.execute(select(CasDaily).where(CasDaily.stock_id == stock.id))).scalar_one()
        assert row.pre_auction_price == D("1312.7") and row.official_close == D("1312.7")
        assert row.indicative_close == D("0") and row.polls == 1

        # 2) post-execution poll (~15:31): auction cleared at 1317.
        post = _FakeKite({"NSE:RELIANCE": {
            "last_price": 1317, "indicative_close_price": 1317,
            "total_imbalance_qty": 0, "reference_limit_price": 1310,
        }})
        assert await cc.capture_cas(db, post, smap, trade_date=TD) == 1
        await db.refresh(row)
        assert row.pre_auction_price == D("1312.7")  # FROZEN — the 3:15 price, not the clear price
        assert row.official_close == D("1317") and row.indicative_close == D("1317")
        assert row.polls == 2  # incremented, one row (idempotent per (stock, date))

    async def test_imbalance_keeps_last_nonzero_not_post_match_zero(self, db: AsyncSession) -> None:
        # Regression (bug-hunter HIGH): a matched auction's final poll reports imbalance 0; that
        # post-execution 0 must NOT clobber the meaningful mid-auction imbalance (the Stage-2
        # predictor). Replays the real HDFCBANK shape: pre-auction 0 → mid −68132 → post-match 0.
        stock = await make_stock(db, symbol="HDFCBANK")
        await db.commit()
        smap = {"NSE:HDFCBANK": stock.id}
        q = lambda last, ind, imb: _FakeKite({  # noqa: E731
            "NSE:HDFCBANK": {"last_price": last, "indicative_close_price": ind,
                             "total_imbalance_qty": imb}})
        await cc.capture_cas(db, q(724, 0, 0), smap, trade_date=TD)          # pre-auction
        await cc.capture_cas(db, q(724, 727, -68132), smap, trade_date=TD)   # mid-auction
        await cc.capture_cas(db, q(727.5, 727.5, 0), smap, trade_date=TD)    # post-match (cleared)
        row = (await db.execute(select(CasDaily).where(CasDaily.stock_id == stock.id))).scalar_one()
        assert row.total_imbalance_qty == -68132  # last NON-ZERO, not the post-match 0
        assert row.official_close == D("727.5") and row.polls == 3

    async def test_skips_symbols_without_a_usable_quote(self, db: AsyncSession) -> None:
        s1 = await make_stock(db, symbol="AAA")
        s2 = await make_stock(db, symbol="BBB")
        await db.commit()
        smap = {"NSE:AAA": s1.id, "NSE:BBB": s2.id}
        kite = _FakeKite({"NSE:AAA": {"last_price": 100, "indicative_close_price": 101,
                                      "total_imbalance_qty": 5}})  # BBB missing from the response
        assert await cc.capture_cas(db, kite, smap, trade_date=TD) == 1
        rows = (await db.execute(select(CasDaily))).scalars().all()
        assert {r.stock_id for r in rows} == {s1.id}


class TestWindowGuard:
    def test_cas_window_bounds(self) -> None:
        from datetime import time

        from app.tasks import cas_tasks
        assert cas_tasks._CAS_START == time(15, 15) and cas_tasks._CAS_END == time(15, 33)
        # _within_cas_window reads the wall clock; just assert it returns a bool without raising.
        assert isinstance(cas_tasks._within_cas_window(), bool)

    def test_capture_mode_routes_each_window(self) -> None:
        from datetime import time

        from app.tasks.cas_tasks import _capture_mode

        assert _capture_mode(time(15, 14, 59)) is None
        assert _capture_mode(time(15, 15)) == "cas"
        assert _capture_mode(time(15, 32, 1)) == "cas"
        assert _capture_mode(time(15, 33, 1)) is None  # the gap between auction and post-close
        assert _capture_mode(time(15, 43, 59)) is None
        assert _capture_mode(time(15, 44)) == "postclose"  # the pre-session baseline poll
        assert _capture_mode(time(16, 4, 3)) == "postclose"  # a late 16:04 poll still counts
        assert _capture_mode(time(16, 5, 1)) is None
        # Real beats land 40–80 ms after the minute, so the inclusive ends never fire: the last
        # CAS poll is 15:32 (18 polls — matching every captured session) and the last post-close
        # poll is 16:04. Pinned so a "harmless" boundary edit cannot silently add or drop a poll.
        assert _capture_mode(time(15, 32, 0, 60_000)) == "cas"
        assert _capture_mode(time(15, 33, 0, 60_000)) is None
        assert _capture_mode(time(16, 4, 0, 60_000)) == "postclose"
        assert _capture_mode(time(16, 5, 0, 60_000)) is None

    def test_postclose_session_is_half_open(self) -> None:
        # SEBI CAS circular 4.2.4: the post-close session is 15:50–16:00. Only polls inside it
        # may record pending interest; a poll at 16:00:00 is after the session.
        from datetime import time

        from app.tasks.cas_tasks import _in_postclose_session

        assert not _in_postclose_session(time(15, 49, 59))
        assert _in_postclose_session(time(15, 50))
        assert _in_postclose_session(time(15, 59, 59))
        assert not _in_postclose_session(time(16, 0))


class TestParsePostClose:
    def test_full_quote(self) -> None:
        p = cc.parse_postclose({
            "last_price": 727.5, "volume": 1_234_567, "buy_quantity": 1500, "sell_quantity": 42_000,
        })
        assert p is not None
        assert p.last_price == D("727.5")
        assert (p.volume, p.buy_quantity, p.sell_quantity) == (1_234_567, 1500, 42_000)

    def test_missing_or_malformed_quantities_are_none_never_zero(self) -> None:
        # A clamp to 0 would invent "no sellers"; unusable must stay distinguishable from zero.
        p = cc.parse_postclose({"last_price": 100, "volume": "x", "sell_quantity": -5})
        assert p is not None
        assert p.volume is None and p.sell_quantity is None and p.buy_quantity is None
        zero = cc.parse_postclose({"last_price": 100, "volume": 0, "sell_quantity": 0})
        assert zero is not None and zero.volume == 0 and zero.sell_quantity == 0

    def test_non_finite_or_out_of_range_is_none_not_a_crash(self) -> None:
        # Regression (bug-hunter LOW-7): "inf" raised OverflowError out of the parser and lost the
        # whole minute's poll; 1e30 parsed and then failed the BIGINT insert for all 210 rows.
        for bad in ("inf", "Infinity", float("inf"), "NaN", 1e30):
            p = cc.parse_postclose({"last_price": 100, "volume": bad, "sell_quantity": bad})
            assert p is not None and p.volume is None and p.sell_quantity is None, bad
        edge = cc.parse_postclose({"last_price": 100, "volume": 9_223_372_036_854_775_807})
        assert edge is not None and edge.volume == 9_223_372_036_854_775_807

    def test_no_last_price_is_unusable(self) -> None:
        assert cc.parse_postclose({"volume": 100}) is None
        assert cc.parse_postclose(None) is None
        assert cc.parse_postclose("nope") is None  # type: ignore[arg-type]


class TestCapturePostClose:
    async def test_baseline_frozen_latest_tracked_peaks_only_in_session(
        self, db: AsyncSession
    ) -> None:
        from app.models.stock import CasPostCloseDaily

        stock = await make_stock(db, symbol="HDFCBANK")
        await db.commit()
        smap = {"NSE:HDFCBANK": stock.id}
        q = lambda vol, buy, sell: _FakeKite({"NSE:HDFCBANK": {  # noqa: E731
            "last_price": 727.5, "volume": vol, "buy_quantity": buy, "sell_quantity": sell}})

        # 15:44 — after the auction, before the session: the baseline. Pending quantities seen
        # OUTSIDE the session must not be recorded as session interest.
        assert await cc.capture_postclose(
            db, q(1_000_000, 900, 800), smap, trade_date=TD, in_session_at=_never_in_session) == 1
        # 15:51 and 15:55 — inside the session: sellers waiting, then some trade.
        await cc.capture_postclose(db, q(1_000_000, 500, 12_000), smap, trade_date=TD,
                                   in_session_at=_always_in_session)
        await cc.capture_postclose(db, q(1_008_000, 0, 4_000), smap, trade_date=TD,
                                   in_session_at=_always_in_session)
        # 16:02 — after the session: final volume; quantities ignored again.
        await cc.capture_postclose(db, q(1_010_000, 99_999, 99_999), smap, trade_date=TD,
                                   in_session_at=_never_in_session)

        row = (await db.execute(
            select(CasPostCloseDaily).where(CasPostCloseDaily.stock_id == stock.id)
        )).scalar_one()
        assert row.volume_after_auction == 1_000_000  # FROZEN at the first poll
        assert row.volume_latest == 1_010_000
        assert row.volume_latest - row.volume_after_auction == 10_000  # post-close volume
        assert row.max_sell_qty == 12_000  # the PEAK inside the session, not the last reading
        assert row.max_buy_qty == 500  # 900 (pre-session) and 99_999 (post-session) excluded
        assert row.last_price_latest == D("727.5") and row.polls == 4

    async def test_timestamps_are_observation_time_first_frozen_latest_advances(
        self, db: AsyncSession, monkeypatch: Any
    ) -> None:
        from app.models.stock import CasPostCloseDaily

        stock = await make_stock(db, symbol="SBIN")
        await db.commit()
        smap = {"NSE:SBIN": stock.id}
        t0 = datetime(2026, 9, 30, 10, 14, 0, 50_000, tzinfo=UTC)  # 15:44:00.05 IST
        seen: list[datetime] = []

        def _in_session(ts: datetime) -> bool:
            seen.append(ts)
            return ts >= t0 + timedelta(minutes=6)  # 15:50 IST onwards

        for minutes, price in ((0, 800), (8, 801.5)):  # 15:44, then 15:52
            monkeypatch.setattr(cc, "_now", lambda m=minutes: t0 + timedelta(minutes=m))
            await cc.capture_postclose(db, _FakeKite({"NSE:SBIN": {
                "last_price": price, "volume": 10, "sell_quantity": 7}}), smap,
                trade_date=TD, in_session_at=_in_session)

        row = (await db.execute(
            select(CasPostCloseDaily).where(CasPostCloseDaily.stock_id == stock.id)
        )).scalar_one()
        assert seen == [t0, t0 + timedelta(minutes=8)]  # decided at the observation instant
        assert row.first_polled_at == t0  # frozen at the FIRST observation
        assert row.captured_at == t0 + timedelta(minutes=8)  # the latest observation, not now()
        assert row.last_price_latest == D("801.5")  # latest price, not the first
        assert row.max_sell_qty == 7  # only the 15:52 poll was in session

    async def test_missing_volume_does_not_erase_the_last_known(self, db: AsyncSession) -> None:
        from app.models.stock import CasPostCloseDaily

        stock = await make_stock(db, symbol="ITC")
        await db.commit()
        smap = {"NSE:ITC": stock.id}
        await cc.capture_postclose(
            db, _FakeKite({"NSE:ITC": {"last_price": 400, "volume": 5_000}}), smap,
            trade_date=TD, in_session_at=_never_in_session)
        await cc.capture_postclose(
            db, _FakeKite({"NSE:ITC": {"last_price": 400}}), smap,  # volume omitted
            trade_date=TD, in_session_at=_always_in_session)
        row = (await db.execute(
            select(CasPostCloseDaily).where(CasPostCloseDaily.stock_id == stock.id)
        )).scalar_one()
        assert row.volume_latest == 5_000 and row.volume_after_auction == 5_000
        assert row.max_sell_qty is None and row.max_buy_qty is None  # nothing seen in session
        assert row.polls == 2

    async def test_never_touches_cas_daily(self, db: AsyncSession) -> None:
        # The auction record is the Stage-2 input; the post-close poll must not rewrite its close.
        stock = await make_stock(db, symbol="RELIANCE")
        await db.commit()
        smap = {"NSE:RELIANCE": stock.id}
        await cc.capture_cas(db, _FakeKite({"NSE:RELIANCE": {
            "last_price": 1317, "indicative_close_price": 1317, "total_imbalance_qty": 0}}),
            smap, trade_date=TD)
        await cc.capture_postclose(db, _FakeKite({"NSE:RELIANCE": {
            "last_price": 1320, "volume": 7, "sell_quantity": 3}}),
            smap, trade_date=TD, in_session_at=_always_in_session)
        auction = (await db.execute(select(CasDaily))).scalar_one()
        assert auction.official_close == D("1317") and auction.polls == 1

    async def test_skips_symbols_without_a_usable_quote(self, db: AsyncSession) -> None:
        from app.models.stock import CasPostCloseDaily

        s1 = await make_stock(db, symbol="AAA")
        s2 = await make_stock(db, symbol="BBB")
        await db.commit()
        kite = _FakeKite({"NSE:AAA": {"last_price": 100, "volume": 10},
                          "NSE:BBB": {"volume": 10}})  # BBB has no last price
        smap = {"NSE:AAA": s1.id, "NSE:BBB": s2.id}
        written = await cc.capture_postclose(
            db, kite, smap, trade_date=TD, in_session_at=_never_in_session
        )
        assert written == 1
        rows = (await db.execute(select(CasPostCloseDaily))).scalars().all()
        assert {r.stock_id for r in rows} == {s1.id}


class TestTaskRoutingSeam:
    """Through `_run_capture_cas` itself (testing.md: test the SEAMS). The window routing, the
    in-session decision and the silent-failure status were all untested before: swapping the two
    branches, or passing in-session always, left the suite green (bug-hunter LOW-8a)."""

    @staticmethod
    def _patch(monkeypatch: Any, ist_hm: tuple[int, int], kite: Any) -> None:
        from types import SimpleNamespace
        from zoneinfo import ZoneInfo

        from app.tasks import cas_tasks

        from tests.conftest import _SessionFactory

        inst = datetime(2026, 9, 30, *ist_hm, 0, 60_000, tzinfo=ZoneInfo("Asia/Kolkata"))

        class _DT(datetime):
            @classmethod
            def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
                return inst if tz is None else inst.astimezone(tz)

        async def _yes(*_a: Any, **_k: Any) -> bool:
            return True

        async def _tok(*_a: Any, **_k: Any) -> str:
            return "tok"

        monkeypatch.setattr(cas_tasks, "datetime", _DT)
        monkeypatch.setattr(cc, "_now", lambda: inst.astimezone(UTC))
        monkeypatch.setattr(cas_tasks, "settings", SimpleNamespace(cas_capture_enabled=True))
        monkeypatch.setattr("app.services.market_calendar.is_trading_day", _yes)
        monkeypatch.setattr("app.services.chain_recorder.get_any_active_admin_token", _tok)
        monkeypatch.setattr("app.broker.kite_rest.ThrottledKite", lambda _token: kite)
        monkeypatch.setattr("app.db.session.AsyncSessionFactory", _SessionFactory)

    async def test_each_window_writes_only_its_own_table(
        self, db: AsyncSession, monkeypatch: Any
    ) -> None:
        from app.models.stock import CasPostCloseDaily
        from app.tasks import cas_tasks

        await make_stock(db, symbol="TCS", is_fno=True)
        await db.commit()
        kite = _FakeKite({"NSE:TCS": {"last_price": 4000, "indicative_close_price": 4001,
                                      "total_imbalance_qty": -50, "volume": 900,
                                      "buy_quantity": 11, "sell_quantity": 22}})
        expected = {
            (15, 20): ("ok", "cas"),
            (15, 38): ("skipped", None),  # between the auction and the post-close window
            (15, 47): ("ok", "postclose"),  # baseline, before the session
            (15, 52): ("ok", "postclose"),  # inside the session
            (16, 0): ("ok", "postclose"),  # after the session
        }
        for hm, (status, mode) in expected.items():
            self._patch(monkeypatch, hm, kite)
            res = await cas_tasks._run_capture_cas()
            assert (res["status"], res.get("mode")) == (status, mode), hm
            if hm == (15, 47):
                pc = (await db.execute(select(CasPostCloseDaily))).scalar_one()
                assert pc.max_sell_qty is None and pc.max_buy_qty is None  # not in session yet
                await db.refresh(pc)

        auction = (await db.execute(select(CasDaily))).scalar_one()
        assert auction.polls == 1 and auction.official_close == D("4000")  # only 15:20 wrote it
        pc = (await db.execute(select(CasPostCloseDaily))).scalar_one()
        await db.refresh(pc)
        assert pc.polls == 3
        assert (pc.max_buy_qty, pc.max_sell_qty) == (11, 22)  # from the 15:52 poll only

    async def test_a_poll_that_writes_nothing_is_empty_not_ok(
        self, db: AsyncSession, monkeypatch: Any
    ) -> None:
        # Regression (bug-hunter MED-3): every /quote batch failing returned {"status": "ok",
        # "written": 0}, which the notifier drops as INFO — a whole post-close session could be
        # lost with no alarm. "empty" is a WARNING, so it is pushed.
        from app.services.notifier import Level
        from app.tasks import cas_tasks

        await make_stock(db, symbol="INFY", is_fno=True)
        await db.commit()

        class _Down:
            async def quote(self, batch: list[Any]) -> dict[str, Any]:
                raise RuntimeError("kite 503")

        self._patch(monkeypatch, (15, 55), _Down())
        res = await cas_tasks._run_capture_cas()
        assert res["status"] == "empty" and res["written"] == 0 and res["mode"] == "postclose"
        level = Level.INFO if res["status"] in ("ok", "skipped") else Level.WARNING
        assert level is Level.WARNING  # the notifier's own policy (notify_task_result)
