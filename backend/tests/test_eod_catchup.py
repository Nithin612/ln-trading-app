"""Self-healing EOD catch-up (services/eod_catchup.py).

Regression suite for the 2026-07-17 incident: EOD ingestion was down
2026-07-03 → 2026-07-17 because the beat never ran and every EOD task
ingested only `today` — one missed evening = one permanent silent hole.
The catch-up functions must heal every missing session in the lookback
window, including interior holes, and skip cleanly when up to date.
"""

from datetime import date
from decimal import Decimal

import pytest
from app.services.bhavcopy_service import ingest_bhavcopy_date
from app.services.eod_catchup import (
    catchup_equities_eod,
    catchup_fii_dii,
    catchup_fo_eod,
    missing_sessions,
)
from app.services.fii_dii_service import FiiDiiRecord
from app.services.fo_bhavcopy_service import ingest_fo_bhavcopy_date
from app.services.market_calendar import trading_days_between
from app.services.vix_service import ingest_vix_date
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tests.helpers import make_stock

# July 2026: 03=Fri, 06=Mon … 10=Fri, 11/12=weekend, 13=Mon, 14=Tue.

_BHAV_HEADER = (
    "SYMBOL,SERIES,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,LAST_PRICE,"
    "PREV_CLOSE,TTL_TRD_QNTY,TURNOVER_LACS,DATE1"
)

_UDIFF_HEADER = (
    "TradDt,BizDt,Sgmt,Src,FinInstrmTp,FinInstrmId,ISIN,TckrSymb,SctySrs,"
    "XpryDt,FininstrmActlXpryDt,StrkPric,OptnTp,FinInstrmNm,OpnPric,HghPric,"
    "LwPric,ClsPric,LastPric,PrvsClsgPric,UndrlygPric,SttlmPric,OpnIntrst,"
    "ChngInOpnIntrst,TtlTradgVol,TtlTrfVal,TtlNbOfTxsExctd,SsnId,NewBrdLotQty"
)


def _bhav_csv(d: date, reliance_open: str = "2900.00", reliance_close: str = "2930.00") -> str:
    ds = d.isoformat()
    return "\n".join(
        [
            _BHAV_HEADER,
            f"RELIANCE,EQ,{reliance_open},2950.00,2880.00,{reliance_close},"
            f"2929.50,2875.00,1234567,360000.00,{ds}",
            f"TCS,EQ,3800.00,3850.00,3770.00,3820.00,3819.00,3760.00,987654,376543.00,{ds}",
        ]
    )


def _udiff_csv(d: date) -> str:
    ds = d.isoformat()
    return "\n".join(
        [
            _UDIFF_HEADER,
            f"{ds},{ds},FO,NSE,IDF,35000,,NIFTY,,2026-07-30,2026-07-30,0,,"
            "NIFTYFUT,24500.5,24620,24480,24600.25,24601,24450,24580.5,24600.25,"
            "14200000,120000,250000,9.9e9,180000,F1,75",
        ]
    )


def _indices_csv(d: date) -> str:
    ds = d.strftime("%d-%m-%Y")
    return "\n".join(
        [
            "Index Name,Index Date,Open Index Value,High Index Value,Low Index Value,"
            "Closing Index Value,Points Change,Change(%),Volume,Turnover (Rs. Cr.),"
            "P/E,P/B,Div Yield",
            f"India VIX,{ds},13.25,14.10,12.90,13.7525,0.50,3.77,0,0,0,0,0",
        ]
    )


async def _seed_holiday(db: AsyncSession, d: date, name: str = "Test Holiday") -> None:
    from app.models.market_calendar import NseHoliday

    db.add(NseHoliday(holiday_date=d, name=name, source="published"))
    await db.commit()


# ── trading_days_between ─────────────────────────────────────────────────────


async def test_trading_days_between_skips_weekends_and_holidays(db: AsyncSession) -> None:
    await _seed_holiday(db, date(2026, 7, 9))
    days = await trading_days_between(db, date(2026, 7, 8), date(2026, 7, 14))
    assert days == [date(2026, 7, 8), date(2026, 7, 10), date(2026, 7, 13), date(2026, 7, 14)]


async def test_trading_days_between_empty_when_start_after_end(db: AsyncSession) -> None:
    assert await trading_days_between(db, date(2026, 7, 14), date(2026, 7, 8)) == []


# ── missing_sessions ─────────────────────────────────────────────────────────


async def test_missing_sessions_rejects_unlisted_table(db: AsyncSession) -> None:
    with pytest.raises(ValueError, match="not an EOD catch-up table"):
        await missing_sessions(db, "stocks; DROP TABLE stocks", date(2026, 7, 14))


async def test_missing_sessions_detects_interior_hole(db: AsyncSession) -> None:
    """max(date)-style detection would miss a hole BETWEEN ingested days —
    presence must be checked per session."""
    await make_stock(db, symbol="RELIANCE", company_name="Reliance Industries")
    await make_stock(db, symbol="TCS", company_name="TCS Ltd")
    await ingest_bhavcopy_date(db, date(2026, 7, 8), csv_text=_bhav_csv(date(2026, 7, 8)))
    await ingest_bhavcopy_date(db, date(2026, 7, 10), csv_text=_bhav_csv(date(2026, 7, 10)))

    missing = await missing_sessions(db, "ohlcv_1d", date(2026, 7, 10), lookback_days=7)
    # start = 07-03 (Fri): sessions 03, 06, 07, 08, 09, 10 minus present {08, 10}
    assert missing == [date(2026, 7, 3), date(2026, 7, 6), date(2026, 7, 7), date(2026, 7, 9)]
    assert date(2026, 7, 9) in missing  # the interior hole


# ── equities catch-up ────────────────────────────────────────────────────────


async def test_eod_outage_multi_day_gap_healed_in_one_run(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for the 2026-07-17 incident: the old task body ingested
    only `today`, so running it once after a 4-session outage recovered
    nothing but today (here: today isn't even published yet → nothing at
    all). The catch-up run must ingest EVERY missing session it can and
    leave only the unpublished day for the next run."""
    await make_stock(db, symbol="RELIANCE", company_name="Reliance Industries")
    await make_stock(db, symbol="TCS", company_name="TCS Ltd")
    await ingest_bhavcopy_date(db, date(2026, 7, 8), csv_text=_bhav_csv(date(2026, 7, 8)))

    published = {d: _bhav_csv(d) for d in (date(2026, 7, 9), date(2026, 7, 10), date(2026, 7, 13))}
    downloads: list[date] = []

    async def fake_download(trade_date: date) -> str | None:
        downloads.append(trade_date)
        return published.get(trade_date)

    monkeypatch.setattr("app.services.bhavcopy_service.download_bhavcopy", fake_download)

    payload = await catchup_equities_eod(db, date(2026, 7, 14), lookback_days=6)

    assert payload["status"] == "ok"
    assert payload["sessions_ingested"] == ["2026-07-09", "2026-07-10", "2026-07-13"]
    assert payload["sessions_skipped"] == ["2026-07-14"]  # not published yet
    assert payload["rows_inserted"] == 6  # 2 stocks × 3 healed sessions

    # Canary (fails on the old ingest-only-today behavior): the FIRST gap
    # day is present with exact prices.
    row = (
        await db.execute(
            text(
                "SELECT o.close FROM ohlcv_1d o JOIN stocks s ON s.id = o.stock_id "
                "WHERE s.symbol = 'RELIANCE' AND o.time::date = '2026-07-09'"
            )
        )
    ).one_or_none()
    assert row is not None
    assert Decimal(row.close) == Decimal("2930.0000")

    # Presence-skip: the already-ingested 07-08 was never re-downloaded.
    assert downloads == [date(2026, 7, 9), date(2026, 7, 10), date(2026, 7, 13), date(2026, 7, 14)]


async def test_catchup_equities_up_to_date_makes_no_downloads(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    await make_stock(db, symbol="RELIANCE", company_name="Reliance Industries")
    await make_stock(db, symbol="TCS", company_name="TCS Ltd")
    await ingest_bhavcopy_date(db, date(2026, 7, 9), csv_text=_bhav_csv(date(2026, 7, 9)))
    await ingest_bhavcopy_date(db, date(2026, 7, 10), csv_text=_bhav_csv(date(2026, 7, 10)))

    async def fail_download(trade_date: date) -> str | None:
        raise AssertionError("up-to-date catch-up must not touch NSE")

    monkeypatch.setattr("app.services.bhavcopy_service.download_bhavcopy", fail_download)

    payload = await catchup_equities_eod(db, date(2026, 7, 10), lookback_days=1)
    assert payload["status"] == "up_to_date"
    assert payload["rows_inserted"] == 0


async def test_network_failure_isolated_to_one_session(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (bug-hunter 2026-07-18 #1): a transport error on one
    session's download aborted the whole catch-up loop — sessions after it
    stayed unhealed and Celery never retried. One bad day must land in
    sessions_skipped while the rest of the run completes."""
    import httpx

    await make_stock(db, symbol="RELIANCE", company_name="Reliance Industries")
    await make_stock(db, symbol="TCS", company_name="TCS Ltd")
    await ingest_bhavcopy_date(db, date(2026, 7, 8), csv_text=_bhav_csv(date(2026, 7, 8)))

    async def flaky_download(trade_date: date) -> str | None:
        if trade_date == date(2026, 7, 9):
            raise httpx.ConnectError("simulated NSE reset")
        if trade_date == date(2026, 7, 14):
            return None  # not published yet
        return _bhav_csv(trade_date)

    monkeypatch.setattr("app.services.bhavcopy_service.download_bhavcopy", flaky_download)

    payload = await catchup_equities_eod(db, date(2026, 7, 14), lookback_days=6)

    # Canary: the old loop raised out of catchup_equities_eod here.
    assert payload["status"] == "ok"
    assert payload["sessions_ingested"] == ["2026-07-10", "2026-07-13"]
    assert sorted(payload["sessions_skipped"]) == ["2026-07-09", "2026-07-14"]


async def test_fo_network_failure_does_not_forfeit_vix(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (bug-hunter 2026-07-18 #1): an fo_bhavcopy transport error
    used to abort catchup_fo_eod entirely, forfeiting the india_vix loop."""
    import httpx

    await ingest_fo_bhavcopy_date(db, date(2026, 7, 3), csv_text=_udiff_csv(date(2026, 7, 3)))
    await ingest_vix_date(db, date(2026, 7, 3), csv_text=_indices_csv(date(2026, 7, 3)))

    async def dead_fo_download(trade_date: date) -> str | None:
        raise httpx.ConnectError("simulated NSE reset")

    async def fake_indices_download(trade_date: date) -> str | None:
        return _indices_csv(trade_date)

    monkeypatch.setattr("app.services.fo_bhavcopy_service.download_fo_bhavcopy", dead_fo_download)
    monkeypatch.setattr("app.services.vix_service.download_indices_csv", fake_indices_download)

    payload = await catchup_fo_eod(db, date(2026, 7, 6), lookback_days=3)

    assert payload["fo_bhavcopy"]["sessions_skipped"] == ["2026-07-06"]
    assert payload["india_vix_daily"]["sessions_ingested"] == ["2026-07-06"]  # canary


async def test_fii_dii_transport_failure_returns_cleanly(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (bug-hunter 2026-07-18 #1): fetch_fii_dii_data degrades to
    [] on non-200/non-JSON but a transport error propagated and failed the
    task with retries inert."""
    import httpx

    async def dead_fetch() -> list[FiiDiiRecord]:
        raise httpx.ConnectError("simulated NSE reset")

    monkeypatch.setattr("app.services.fii_dii_service.fetch_fii_dii_data", dead_fetch)

    payload = await catchup_fii_dii(db, date(2026, 7, 6), lookback_days=3)
    assert payload["status"] == "fetch_failed"
    assert payload["still_missing"] == ["2026-07-03", "2026-07-06"]


async def test_missed_ca_sweep_healed_on_next_run(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (bug-hunter 2026-07-18 #2): bars-commit and CA-sweep are
    separate commits, so a crash between them (or a backfill_eod.py run,
    which never sweeps) left a day present-but-unswept FOREVER — presence-
    based healing skipped it on every later run. The sweep must cover every
    present session in the window, not just sessions healed this run."""
    await make_stock(db, symbol="RELIANCE", company_name="Reliance Industries")
    await make_stock(db, symbol="TCS", company_name="TCS Ltd")
    # Simulate the crash aftermath: both days' bars committed, sweep never ran.
    await ingest_bhavcopy_date(db, date(2026, 7, 9), csv_text=_bhav_csv(date(2026, 7, 9)))
    await ingest_bhavcopy_date(
        db,
        date(2026, 7, 10),
        csv_text=_bhav_csv(date(2026, 7, 10), reliance_open="4500.00", reliance_close="4510.00"),
    )

    async def fail_download(trade_date: date) -> str | None:
        raise AssertionError("table is current — no downloads expected")

    monkeypatch.setattr("app.services.bhavcopy_service.download_bhavcopy", fail_download)

    payload = await catchup_equities_eod(db, date(2026, 7, 10), lookback_days=1)

    # Canary: the old up_to_date early-return did no sweeping at all.
    assert payload["status"] == "up_to_date"
    assert payload["ca_flagged"] == 1
    flagged = (
        (await db.execute(text("SELECT symbol FROM stocks WHERE ca_flagged_at IS NOT NULL")))
        .scalars()
        .all()
    )
    assert list(flagged) == ["RELIANCE"]


async def test_catchup_equities_ca_sweeps_each_healed_session(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A >20% open gap inside the healed window must quarantine the stock,
    exactly as the nightly run would have on that day."""
    await make_stock(db, symbol="RELIANCE", company_name="Reliance Industries")
    await make_stock(db, symbol="TCS", company_name="TCS Ltd")
    await ingest_bhavcopy_date(db, date(2026, 7, 9), csv_text=_bhav_csv(date(2026, 7, 9)))

    gap_csv = _bhav_csv(date(2026, 7, 10), reliance_open="4500.00", reliance_close="4510.00")

    async def fake_download(trade_date: date) -> str | None:
        return gap_csv if trade_date == date(2026, 7, 10) else None

    monkeypatch.setattr("app.services.bhavcopy_service.download_bhavcopy", fake_download)

    payload = await catchup_equities_eod(db, date(2026, 7, 10), lookback_days=1)
    assert payload["ca_flagged"] == 1

    flagged = (
        await db.execute(
            text("SELECT symbol, ca_flag_reason FROM stocks WHERE ca_flagged_at IS NOT NULL")
        )
    ).all()
    assert [r.symbol for r in flagged] == ["RELIANCE"]
    assert "2026-07-10" in flagged[0].ca_flag_reason


# ── F&O + VIX catch-up ───────────────────────────────────────────────────────


async def test_catchup_fo_heals_tables_independently(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """fo_bhavcopy is behind but india_vix_daily is current: only the F&O
    side may hit NSE; the VIX loop must not download anything."""
    await ingest_fo_bhavcopy_date(db, date(2026, 7, 3), csv_text=_udiff_csv(date(2026, 7, 3)))
    await ingest_vix_date(db, date(2026, 7, 3), csv_text=_indices_csv(date(2026, 7, 3)))
    await ingest_vix_date(db, date(2026, 7, 6), csv_text=_indices_csv(date(2026, 7, 6)))

    async def fake_fo_download(trade_date: date) -> str | None:
        return _udiff_csv(trade_date)

    async def fail_indices_download(trade_date: date) -> str | None:
        raise AssertionError("VIX is current — its loop must not download")

    monkeypatch.setattr("app.services.fo_bhavcopy_service.download_fo_bhavcopy", fake_fo_download)
    monkeypatch.setattr("app.services.vix_service.download_indices_csv", fail_indices_download)

    payload = await catchup_fo_eod(db, date(2026, 7, 6), lookback_days=3)

    assert payload["fo_bhavcopy"]["sessions_ingested"] == ["2026-07-06"]
    assert payload["india_vix_daily"]["status"] == "up_to_date"
    count = (
        await db.execute(text("SELECT count(*) FROM fo_bhavcopy WHERE trade_date = '2026-07-06'"))
    ).scalar_one()
    assert count == 1


# ── FII/DII catch-up ─────────────────────────────────────────────────────────


async def test_catchup_fii_dii_up_to_date_makes_no_fetch(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.fii_dii_service import upsert_fii_dii

    await upsert_fii_dii(
        db,
        [
            FiiDiiRecord(
                trade_date=date(2026, 7, 6),
                investor_type="FII",
                segment="futures",
                buy_value_cr=Decimal("100.5"),
                sell_value_cr=Decimal("90.25"),
            )
        ],
    )

    async def fail_fetch() -> list[FiiDiiRecord]:
        raise AssertionError("up-to-date FII/DII catch-up must not hit NSE")

    monkeypatch.setattr("app.services.fii_dii_service.fetch_fii_dii_data", fail_fetch)

    payload = await catchup_fii_dii(db, date(2026, 7, 6), lookback_days=1)
    assert payload["status"] == "up_to_date"


async def test_catchup_fii_dii_heals_from_rolling_window(
    db: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One fetch of NSE's rolling window fills what it covers; sessions the
    window did not reach are reported in still_missing (observable gap)."""

    async def fake_fetch() -> list[FiiDiiRecord]:
        return [
            FiiDiiRecord(
                trade_date=date(2026, 7, 3),
                investor_type="FII",
                segment="futures",
                buy_value_cr=Decimal("100.5"),
                sell_value_cr=Decimal("90.25"),
            ),
            FiiDiiRecord(
                trade_date=date(2026, 7, 3),
                investor_type="DII",
                segment="futures",
                buy_value_cr=Decimal("80.0"),
                sell_value_cr=Decimal("70.0"),
            ),
        ]

    monkeypatch.setattr("app.services.fii_dii_service.fetch_fii_dii_data", fake_fetch)

    payload = await catchup_fii_dii(db, date(2026, 7, 6), lookback_days=3)
    assert payload["status"] == "ok"
    assert payload["inserted"] == 2
    assert payload["still_missing"] == ["2026-07-06"]

    buy = (
        await db.execute(
            text(
                "SELECT buy_value_cr FROM fii_dii_daily "
                "WHERE trade_date = '2026-07-03' AND investor_type = 'FII'"
            )
        )
    ).scalar_one()
    assert Decimal(buy) == Decimal("100.5")
